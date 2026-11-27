"""Create and concurrently refresh Gold materialized views in Supabase PostgreSQL 16 (mart.*)."""

from __future__ import annotations

import argparse
import sys

from src.core.db import execute_sql_file, get_pg_connection
from src.core.settings import get_settings

MART_SQL_FILES = [
    ("02_mart_electronics_tot.sql", "mart.mv_electronics_terms_of_trade"),
    ("03_mart_hub_intermediation_gap.sql", "mart.mv_hub_intermediation_gap"),
    ("04_mart_export_market_pulse.sql", "mart.mv_export_market_pulse"),
]


def build_and_refresh_marts(recreate: bool = False) -> None:
    settings = get_settings()
    with get_pg_connection(settings, autocommit=True) as conn:
        for sql_file, mv_name in MART_SQL_FILES:
            if recreate:
                with conn.cursor() as cur:
                    cur.execute(f"DROP MATERIALIZED VIEW IF EXISTS {mv_name};")
            print(f"[GOLD] Ensuring {mv_name} ({sql_file})...")
            execute_sql_file(conn, sql_file)
            with conn.cursor() as cur:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name};")
                cur.execute(
                    f"SELECT COUNT(*), MIN(period_date), MAX(period_date) FROM {mv_name};"
                )
                cnt, min_d, max_d = cur.fetchone()
                print(f"       Refreshed {mv_name}: rows={cnt}, range={min_d}..{max_d}")

        print("[GOLD] Ensuring mart.dim_date (06_mart_dim_date.sql)...")
        execute_sql_file(conn, "06_mart_dim_date.sql")

    print("OK: All Gold marts built and refreshed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build and refresh Gold materialized views.")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate materialized views from SQL.")
    args = parser.parse_args()
    try:
        build_and_refresh_marts(recreate=args.recreate)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

