"""REST client for NBP Exchange Rates API (https://api.nbp.pl/api/exchangerates)."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.settings import Settings, get_settings


class NBPClient:
    """Fetches daily Table A mid-rates from NBP API and aggregates to monthly stats."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.nbp_api_base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Accept": "application/json"},
            timeout=httpx.Timeout(25.0, connect=10.0),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NBPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def get_yearly_rates(self, currency: str, year: int) -> dict[str, Any]:
        """Fetch Table A daily rates for one calendar year (<= 366 days, fits NBP limit)."""
        start = date(year, 1, 1)
        today = date.today()
        end = min(date(year, 12, 31), today)
        if start > today:
            return {"code": currency.upper(), "rates": []}

        path = f"/rates/a/{currency.lower()}/{start.isoformat()}/{end.isoformat()}/"
        resp = self._client.get(path, params={"format": "json"})
        if resp.status_code == 404:
            return {"code": currency.upper(), "rates": []}
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def aggregate_monthly(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Aggregate NBP daily rates JSON into monthly avg/min/max/stddev rows."""
        rates = payload.get("rates") or []
        if not rates:
            return []
        currency = str(payload.get("code", "")).upper()
        df = pd.DataFrame(rates)
        df["effectiveDate"] = pd.to_datetime(df["effectiveDate"])
        df["period_date"] = df["effectiveDate"].dt.to_period("M").dt.to_timestamp().dt.date
        df["mid"] = pd.to_numeric(df["mid"], errors="coerce")
        df = df.dropna(subset=["mid"])

        grouped = (
            df.groupby("period_date", as_index=False)["mid"]
            .agg(
                rate_avg="mean",
                rate_min="min",
                rate_max="max",
                rate_stddev="std",
                obs_days="count",
            )
        )
        records: list[dict[str, Any]] = []
        for row in grouped.to_dict(orient="records"):
            stddev_val = None if pd.isna(row["rate_stddev"]) else round(float(row["rate_stddev"]), 6)
            records.append(
                {
                    "period_date": row["period_date"],
                    "currency_code": currency,
                    "rate_avg": round(float(row["rate_avg"]), 6),
                    "rate_min": round(float(row["rate_min"]), 6),
                    "rate_max": round(float(row["rate_max"]), 6),
                    "rate_stddev": stddev_val,
                    "obs_days": int(row["obs_days"]),
                }
            )
        return records

