"""Unit tests for parsers, NBP aggregation, S3 key conventions, and YAML configuration."""

from __future__ import annotations

from datetime import date

from src.clients.nbp_client import NBPClient
from src.core.settings import load_trade_config
from src.core.storage_s3 import BronzeStorageClient
from src.pipelines.sync_dictionaries import parse_period_flags


def test_parse_period_flags_accepts_monthly_only() -> None:
    # Standard monthly period (id=247, M01, Miesiąc)
    assert parse_period_flags(
        {
            "id-okres": 247,
            "symbol": "M01",
            "opis": "miesiąc - dane miesięczne - styczeń",
            "nazwa-typ": "dane miesięczne",
            "nazwa-czestotliwosc": "Miesiąc",
        }
    ) == (1, True, False)

    # Regression test: quarterly period sharing M01 symbol (id=341) MUST be rejected
    assert parse_period_flags(
        {
            "id-okres": 341,
            "symbol": "M01",
            "opis": "kwartał - dane miesięczne - styczeń",
            "nazwa-typ": "dane miesięczne",
            "nazwa-czestotliwosc": "Kwartał",
        }
    ) == (None, False, False)


def test_parse_period_flags_cumulative_periods() -> None:
    # Cumulative M01-09 (id=266, Miesiąc) -> month 9, is_cumulative=True
    assert parse_period_flags(
        {
            "id-okres": 266,
            "symbol": "M01-09",
            "opis": "miesiąc - dane narastające - styczeń - wrzesień",
            "nazwa-typ": "dane narastające",
            "nazwa-czestotliwosc": "Miesiąc",
        }
    ) == (9, False, True)

    # M01-01 (id=340) is excluded because cumulative series use id=247 for January
    assert parse_period_flags(
        {
            "id-okres": 340,
            "symbol": "M01-01",
            "opis": "miesiąc - dane narastające - styczeń",
            "nazwa-typ": "dane narastające",
            "nazwa-czestotliwosc": "Miesiąc",
        }
    ) == (None, False, False)


def test_nbp_aggregate_monthly() -> None:
    sample = {
        "code": "EUR",
        "rates": [
            {"effectiveDate": "2025-09-01", "mid": 4.20},
            {"effectiveDate": "2025-09-02", "mid": 4.30},
            {"effectiveDate": "2025-10-01", "mid": 4.40},
        ],
    }
    agg = NBPClient.aggregate_monthly(sample)
    assert len(agg) == 2
    assert agg[0]["period_date"] == date(2025, 9, 1)
    assert agg[0]["currency_code"] == "EUR"
    assert agg[0]["rate_avg"] == 4.25
    assert agg[0]["rate_min"] == 4.20
    assert agg[0]["rate_max"] == 4.30
    assert agg[0]["obs_days"] == 2
    assert agg[1]["period_date"] == date(2025, 10, 1)
    assert agg[1]["rate_stddev"] is None


def test_nbp_aggregate_empty_returns_empty_list() -> None:
    assert NBPClient.aggregate_monthly({"code": "USD", "rates": []}) == []


def test_bronze_s3_key_conventions() -> None:
    assert BronzeStorageClient.dbw_data_key(329, 772, 2025, 255) == (
        "gus_dbw/var=329/sec=772/year=2025/period=255/payload.json.gz"
    )
    assert BronzeStorageClient.dbw_dict_key("periods") == "gus_dbw/dictionaries/periods/latest.json.gz"
    assert BronzeStorageClient.nbp_rates_key("eur", 2025) == "nbp/currency=EUR/year=2025/rates.json.gz"


def test_trade_series_config_integrity() -> None:
    cfg = load_trade_config()
    datasets = cfg["dbw_datasets"]
    assert len(datasets) == 8
    codes = [d["code"] for d in datasets]
    assert len(set(codes)) == 8
    for ds in datasets:
        assert ds["period_mode"] in {"monthly", "cumulative"}
        assert isinstance(ds["id_zmienna"], int)
        assert isinstance(ds["id_przekroj"], int)
        assert ds.get("positions")

