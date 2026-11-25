"""Integration tests verifying Supabase Gold marts and Data Quality Gates."""

from __future__ import annotations

import pytest

from src.core.db import get_pg_connection
from src.core.settings import get_settings
from src.quality.run_dq import run_data_quality_checks

pytestmark = pytest.mark.skipif(
    not get_settings().database_url,
    reason="DATABASE_URL not configured; skipping live Supabase integration tests.",
)


def test_gold_marts_are_populated() -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for mv in (
                "mart.mv_electronics_terms_of_trade",
                "mart.mv_hub_intermediation_gap",
                "mart.mv_export_market_pulse",
            ):
                cur.execute(f"SELECT COUNT(*) FROM {mv};")
                count = cur.fetchone()[0]
                assert count > 0, f"Expected populated Gold mart {mv}, got 0 rows"


def test_all_critical_data_quality_gates_pass() -> None:
    results = run_data_quality_checks()
    assert len(results) >= 6
    critical_failures = [r for r in results if r.severity == "CRITICAL" and r.failed_rows > 0]
    assert not critical_failures, f"Critical DQ failures: {critical_failures}"

