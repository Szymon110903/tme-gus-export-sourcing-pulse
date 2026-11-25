"""Initialize Supabase PostgreSQL 16 schemas/tables and verify Supabase S3 Bronze bucket."""

from __future__ import annotations

import sys
from urllib.parse import urlparse

from src.core.db import execute_sql_file, get_pg_connection
from src.core.settings import get_settings
from src.core.storage_s3 import BronzeStorageClient

INIT_SQL_FILES = [
    "00_schemas_and_dicts.sql",
    "01_staging_partitioned.sql",
]


def run_db_init() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not configured in .env")

    parsed = urlparse(settings.psycopg_dsn)
    print(f"[1/2] Connecting to Supabase PostgreSQL at {parsed.hostname}:{parsed.port or 5432}...")
    with get_pg_connection(settings, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            pg_version = cur.fetchone()[0]
            print(f"      Connected: {pg_version.split(',')[0]}")

        for filename in INIT_SQL_FILES:
            print(f"      Executing {filename}...")
            execute_sql_file(conn, filename)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ref.dim_date;")
            date_rows = cur.fetchone()[0]
            print(f"      Verified ref.dim_date rows: {date_rows}")

    print("[2/2] Checking Supabase S3 Bronze storage bucket...")
    storage = BronzeStorageClient(settings)
    storage.check_bucket_access()
    print(f"      Connected to bucket: {storage.bucket} (region: {settings.supabase_s3_region})")
    print("OK: Supabase PostgreSQL 16 + S3 Bronze storage initialized successfully.")


if __name__ == "__main__":
    try:
        run_db_init()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

