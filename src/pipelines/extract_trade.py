"""Extract GUS DBW trade datasets & NBP FX rates into Supabase Bronze (S3) and Silver (PostgreSQL)."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import psycopg

from src.clients.dbw_client import DBWClient
from src.clients.nbp_client import NBPClient
from src.core.db import get_pg_connection
from src.core.settings import get_settings, load_trade_config
from src.core.storage_s3 import BronzeStorageClient


def get_period_ids_by_mode(conn: psycopg.Connection) -> dict[str, dict[int, int]]:
    """Return {'monthly': {id_okres: month_num}, 'cumulative': {id_okres: month_num}} from ref.dim_period."""
    modes: dict[str, dict[int, int]] = {"monthly": {}, "cumulative": {}}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id_okres, month_num, is_monthly, is_cumulative
            FROM ref.dim_period
            WHERE month_num IS NOT NULL AND (is_monthly = true OR is_cumulative = true)
            ORDER BY month_num, id_okres;
            """
        )
        for id_okres, month_num, is_monthly, is_cumulative in cur.fetchall():
            if is_monthly:
                modes["monthly"][int(id_okres)] = int(month_num)
                if int(month_num) == 1:
                    modes["cumulative"][int(id_okres)] = 1
            if is_cumulative:
                modes["cumulative"][int(id_okres)] = int(month_num)
    return modes


def is_within_recheck_window(year: int, month_num: int, recheck_months: int) -> bool:
    today = date.today()
    diff = (today.year - year) * 12 + (today.month - month_num)
    return diff <= recheck_months


def upsert_dbw_slice(
    conn: psycopg.Connection,
    rows: list[dict[str, Any]],
    period_month_map: dict[int, int],
    bronze_key: str,
    load_ts: datetime,
) -> tuple[int, int]:
    """Batched versioned upsert into staging.fact_dbw_observation with revision audit logging."""
    if not rows:
        return 0, 0

    parsed_rows: list[tuple[Any, ...]] = []
    slice_keys: set[tuple[int, int, date, int]] = set()
    for item in rows:
        val_raw = item.get("wartosc")
        if val_raw is None:
            continue
        id_zmienna = int(item["id-zmienna"])
        id_przekroj = int(item["id-przekroj"])
        id_okres = int(item["id-okres"])
        year = int(item["id-daty"])
        month_num = period_month_map.get(id_okres)
        if not month_num:
            continue

        period_date = date(year, month_num, 1)
        p1 = int(item.get("id-pozycja-1") or 0)
        p2 = int(item.get("id-pozycja-2") or 0)
        p3 = int(item.get("id-pozycja-3") or 0)
        p4 = int(item.get("id-pozycja-4") or 0)
        id_miara = int(item["id-sposob-prezentacji-miara"])
        id_flaga = int(item["id-flaga"]) if item.get("id-flaga") is not None else None
        wartosc = Decimal(str(val_raw)).quantize(Decimal("0.00001"))

        slice_keys.add((id_zmienna, id_przekroj, period_date, id_okres))
        parsed_rows.append(
            (id_zmienna, id_przekroj, period_date, id_okres, p1, p2, p3, p4, id_miara, id_flaga, wartosc)
        )

    if not parsed_rows:
        return 0, 0

    existing_map: dict[tuple[Any, ...], tuple[Decimal, int | None]] = {}
    with conn.cursor() as cur:
        for id_zmienna, id_przekroj, period_date, id_okres in slice_keys:
            cur.execute(
                """
                SELECT id_zmienna, id_przekroj, period_date, id_okres,
                       id_pozycja_1, id_pozycja_2, id_pozycja_3, id_pozycja_4, id_miara,
                       wartosc, id_flaga
                FROM staging.fact_dbw_observation
                WHERE id_zmienna = %s AND id_przekroj = %s AND period_date = %s AND id_okres = %s
                  AND is_current = true
                """,
                (id_zmienna, id_przekroj, period_date, id_okres),
            )
            for r in cur.fetchall():
                existing_map[r[:9]] = (r[9], r[10])

        to_retire: list[tuple[Any, ...]] = []
        to_audit: list[tuple[Any, ...]] = []
        to_insert: list[tuple[Any, ...]] = []

        for rec in parsed_rows:
            key = rec[:9]
            id_flaga, wartosc = rec[9], rec[10]
            prev = existing_map.get(key)
            if prev is not None:
                old_val, old_flaga = prev
                if old_val == wartosc and old_flaga == id_flaga:
                    continue
                to_retire.append(key)
                pct_diff = None
                if old_val and old_val != 0:
                    pct_diff = round(float((wartosc - old_val) / abs(old_val) * Decimal("100")), 4)
                to_audit.append(
                    (
                        key[0], key[1], key[2], key[3],
                        key[5], key[6], key[8],
                        old_val, wartosc, old_flaga, id_flaga, pct_diff,
                    )
                )
            to_insert.append((*key, id_flaga, wartosc, bronze_key, load_ts))

        if to_retire:
            cur.executemany(
                """
                UPDATE staging.fact_dbw_observation
                SET is_current = false
                WHERE id_zmienna = %s AND id_przekroj = %s AND period_date = %s AND id_okres = %s
                  AND id_pozycja_1 = %s AND id_pozycja_2 = %s AND id_pozycja_3 = %s AND id_pozycja_4 = %s
                  AND id_miara = %s AND is_current = true
                """,
                to_retire,
            )
        if to_audit:
            cur.executemany(
                """
                INSERT INTO staging.etl_revision_audit (
                    id_zmienna, id_przekroj, period_date, id_okres,
                    id_pozycja_2, id_pozycja_3, id_miara,
                    old_value, new_value, old_flaga, new_flaga, pct_diff
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                to_audit,
            )
        if to_insert:
            cur.executemany(
                """
                INSERT INTO staging.fact_dbw_observation (
                    id_zmienna, id_przekroj, period_date, id_okres,
                    id_pozycja_1, id_pozycja_2, id_pozycja_3, id_pozycja_4,
                    id_miara, id_flaga, wartosc, bronze_key, load_ts, is_current
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                ON CONFLICT DO NOTHING
                """,
                to_insert,
            )

    return len(to_insert), len(to_audit)


def extract_all(years: list[int], force_refresh: bool = False) -> None:
    settings = get_settings()
    config = load_trade_config()
    storage = BronzeStorageClient(settings)
    recheck_months = int(config["date_range"].get("recheck_recent_months", 3))
    today = date.today()
    load_ts = datetime.now(timezone.utc)

    with get_pg_connection(settings) as conn:
        period_modes = get_period_ids_by_mode(conn)
        if not period_modes["monthly"]:
            raise RuntimeError("ref.dim_period is empty. Run 'python -m src.pipelines.sync_dictionaries' first.")

        print(f"[1/2] Extracting GUS DBW datasets for years={years} (force_refresh={force_refresh})...")
        api_calls = 0
        cache_hits = 0
        total_inserted = 0
        total_revised = 0

        with DBWClient(settings) as dbw:
            rate_limited = False
            for ds in config["dbw_datasets"]:
                if rate_limited:
                    break
                code = ds["code"]
                var_id = int(ds["id_zmienna"])
                sec_id = int(ds["id_przekroj"])
                mode = ds["period_mode"]
                p_map = period_modes[mode]

                ds_inserted = 0
                ds_revised = 0
                for year in years:
                    if rate_limited:
                        break
                    for id_okres, month_num in sorted(p_map.items(), key=lambda kv: kv[1]):
                        if date(year, month_num, 1) > today:
                            continue

                        bronze_key = storage.dbw_data_key(var_id, sec_id, year, id_okres)
                        should_fetch = force_refresh or not storage.exists(bronze_key) or is_within_recheck_window(
                            year, month_num, recheck_months
                        )

                        if should_fetch:
                            try:
                                payload = dbw.get_variable_data_section(var_id, sec_id, year, id_okres)
                            except Exception as exc:
                                if "429" in str(exc):
                                    print(
                                        f"      [WARN] GUS DBW 15-min rate limit reached at {code} {year}-{month_num:02d}. "
                                        "Progress saved in Supabase Bronze S3 & Silver; re-run to resume."
                                    )
                                    rate_limited = True
                                    break
                                raise
                            api_calls += 1
                            if payload["data"]:
                                storage.put_json_gz(bronze_key, payload)
                        else:
                            payload = storage.get_json_gz(bronze_key)
                            cache_hits += 1

                        ins, rev = upsert_dbw_slice(conn, payload.get("data", []), p_map, bronze_key, load_ts)
                        conn.commit()
                        ds_inserted += ins
                        ds_revised += rev

                total_inserted += ds_inserted
                total_revised += ds_revised
                print(f"      {code:26s} -> inserted={ds_inserted:5d}, revised={ds_revised:3d}")

        print(
            f"      DBW summary: api_calls={api_calls}, bronze_cache_hits={cache_hits}, "
            f"inserted={total_inserted}, revised={total_revised}"
        )

        print(f"[2/2] Extracting NBP FX rates ({config['nbp_currencies']}) for years={years}...")
        fx_rows_total = 0
        with NBPClient(settings) as nbp:
            for currency in config["nbp_currencies"]:
                for year in years:
                    if year > today.year:
                        continue
                    bronze_key = storage.nbp_rates_key(currency, year)
                    should_fetch = force_refresh or (year == today.year) or not storage.exists(bronze_key)
                    if should_fetch:
                        payload = nbp.get_yearly_rates(currency, year)
                        if payload.get("rates"):
                            storage.put_json_gz(bronze_key, payload)
                    else:
                        payload = storage.get_json_gz(bronze_key)

                    monthly = nbp.aggregate_monthly(payload)
                    with conn.cursor() as cur:
                        for m in monthly:
                            cur.execute(
                                """
                                INSERT INTO staging.fact_nbp_fx (
                                    period_date, currency_code, rate_avg, rate_min, rate_max,
                                    rate_stddev, obs_days, bronze_key, updated_at
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                                ON CONFLICT (period_date, currency_code) DO UPDATE SET
                                    rate_avg = EXCLUDED.rate_avg,
                                    rate_min = EXCLUDED.rate_min,
                                    rate_max = EXCLUDED.rate_max,
                                    rate_stddev = EXCLUDED.rate_stddev,
                                    obs_days = EXCLUDED.obs_days,
                                    bronze_key = EXCLUDED.bronze_key,
                                    updated_at = now()
                                """,
                                (
                                    m["period_date"],
                                    m["currency_code"],
                                    m["rate_avg"],
                                    m["rate_min"],
                                    m["rate_max"],
                                    m["rate_stddev"],
                                    m["obs_days"],
                                    bronze_key,
                                ),
                            )
                    fx_rows_total += len(monthly)
            conn.commit()
        print(f"      NBP summary: upserted {fx_rows_total} monthly FX rows into staging.fact_nbp_fx")

    print("OK: Extraction completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract GUS DBW & NBP data into Supabase Bronze + Silver.")
    parser.add_argument("--backfill", action="store_true", help="Extract full start_year..end_year from YAML config.")
    parser.add_argument("--years", type=int, nargs="+", help="Specific years to extract (e.g. --years 2025).")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore Bronze S3 cache and re-fetch from API.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = load_trade_config()
    if args.years:
        target_years = sorted(set(args.years))
    elif args.backfill:
        target_years = list(range(int(cfg["date_range"]["start_year"]), int(cfg["date_range"]["end_year"]) + 1))
    else:
        cur_y = date.today().year
        target_years = [cur_y - 1, cur_y]

    try:
        extract_all(target_years, force_refresh=args.force_refresh)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

