"""REST client for GUS DBW API (https://api-dbw.stat.gov.pl/api/1.1.0)."""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.settings import Settings, get_settings


class DBWRateLimitError(Exception):
    """Raised when GUS DBW API returns HTTP 429."""


class DBWServerError(Exception):
    """Raised when GUS DBW API returns HTTP 5xx."""


class DBWClient:
    """Polite, retry-enabled HTTP client for GUS DBW API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.gus_dbw_base_url.rstrip("/")
        self.headers: dict[str, str] = {"Accept": "application/json"}
        if self.settings.gus_dbw_api_key:
            self.headers["X-ClientId"] = self.settings.gus_dbw_api_key
            self._min_interval = 0.14  # < 10 req/s registered limit
        else:
            self._min_interval = 0.28  # < 5 req/s anonymous limit
        self._last_request_ts = 0.0

        ssl_context: Any = True
        try:
            import ssl
            import truststore

            ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except Exception:
            ssl_context = True

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=httpx.Timeout(30.0, connect=15.0),
            verify=ssl_context,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DBWClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_ts = time.monotonic()

    @retry(
        retry=retry_if_exception_type((DBWRateLimitError, DBWServerError, httpx.TimeoutException, httpx.ConnectError)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _get_json(self, path: str, params: dict[str, Any] | None = None, allow_404: bool = False) -> Any:
        self._throttle()
        resp = self._client.get(path, params=params)
        if resp.status_code == 404 and allow_404:
            return None
        if resp.status_code == 429:
            raise DBWRateLimitError(f"HTTP 429 Too Many Requests for {path}")
        if resp.status_code >= 500:
            raise DBWServerError(f"HTTP {resp.status_code} for {path}")
        resp.raise_for_status()
        return resp.json()

    def get_areas(self, lang: str = "pl") -> list[dict[str, Any]]:
        data = self._get_json("/area/area-area", params={"lang": lang})
        return data if isinstance(data, list) else data.get("data", [])

    def get_area_variables(self, id_obszaru: int, lang: str = "pl") -> list[dict[str, Any]]:
        data = self._get_json(
            "/area/area-variable",
            params={"id-obszaru": id_obszaru, "lang": lang},
            allow_404=True,
        )
        if not data:
            return []
        return data if isinstance(data, list) else data.get("data", [])

    def _get_paginated_dict(self, path: str, page_size: int = 500, lang: str = "pl") -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = self._get_json(
                path,
                params={"page": page, "page-size": page_size, "lang": lang},
                allow_404=True,
            )
            if not payload:
                break
            batch = payload.get("data", []) if isinstance(payload, dict) else payload
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return rows

    def get_periods_dictionary(self, lang: str = "pl") -> list[dict[str, Any]]:
        return self._get_paginated_dict("/dictionaries/periods-dictionary", page_size=500, lang=lang)

    def get_measures_dictionary(self, lang: str = "pl") -> list[dict[str, Any]]:
        return self._get_paginated_dict("/dictionaries/way-of-presentation", page_size=500, lang=lang)

    def get_flags_dictionary(self, lang: str = "pl") -> list[dict[str, Any]]:
        return self._get_paginated_dict("/dictionaries/flag-dictionary", page_size=200, lang=lang)

    def get_section_positions(self, id_przekroj: int, lang: str = "pl") -> list[dict[str, Any]]:
        data = self._get_json(
            "/variable/variable-section-position",
            params={"id-przekroj": id_przekroj, "lang": lang},
            allow_404=True,
        )
        if not data:
            return []
        return data if isinstance(data, list) else data.get("data", [])

    def get_variable_data_section(
        self,
        id_zmienna: int,
        id_przekroj: int,
        year: int,
        id_okres: int,
        page_size: int = 5000,
        lang: str = "pl",
    ) -> dict[str, Any]:
        """Fetch all pages of a DBW variable-data-section slice."""
        all_rows: list[dict[str, Any]] = []
        page_num = 0
        while True:
            payload = self._get_json(
                "/variable/variable-data-section",
                params={
                    "id-zmienna": id_zmienna,
                    "id-przekroj": id_przekroj,
                    "id-rok": year,
                    "id-okres": id_okres,
                    "ile-na-stronie": page_size,
                    "numer-strony": page_num,
                    "lang": lang,
                },
                allow_404=True,
            )
            if not payload or not isinstance(payload, dict):
                break
            batch = payload.get("data") or []
            all_rows.extend(batch)
            page_count = int(payload.get("page-count") or 0)
            if page_num >= page_count or len(batch) < page_size:
                break
            page_num += 1

        return {
            "meta": {
                "id_zmienna": id_zmienna,
                "id_przekroj": id_przekroj,
                "year": year,
                "id_okres": id_okres,
                "row_count": len(all_rows),
            },
            "data": all_rows,
        }

