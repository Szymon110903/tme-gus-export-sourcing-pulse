"""Shared Supabase PostgreSQL 16 connection and SQL script execution helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg

from src.core.settings import SQL_DIR, Settings, get_settings


@contextmanager
def get_pg_connection(
    settings: Settings | None = None,
    autocommit: bool = False,
) -> Iterator[psycopg.Connection]:
    """Open a psycopg connection to Supabase PostgreSQL 16."""
    cfg = settings or get_settings()
    if not cfg.database_url:
        raise ValueError("DATABASE_URL is not configured in .env")
    with psycopg.connect(cfg.psycopg_dsn, autocommit=autocommit) as conn:
        yield conn


def execute_sql_file(conn: psycopg.Connection, filename: str, base_dir: Path | None = None) -> None:
    """Execute a SQL file located under sql/ (or custom base_dir)."""
    sql_path = (base_dir or SQL_DIR) / filename
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))

