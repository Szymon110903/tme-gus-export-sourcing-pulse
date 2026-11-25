"""Apache Airflow DAG for chunked GUS DBW + NBP backfill into Supabase."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.core.settings import load_trade_config
from src.pipelines.extract_trade import extract_all

DEFAULT_ARGS = {
    "owner": "tme-data-analytics",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
}


def _run_backfill_chunk() -> None:
    """Run one backfill pass over start_year..end_year.

    Already-fetched months are served from Supabase Bronze S3 (0 GUS calls).
    If the 15-min anonymous rate limit (HTTP 429) is reached, progress is saved
    and the next scheduled run resumes automatically.
    """
    cfg = load_trade_config()
    years = list(range(int(cfg["date_range"]["start_year"]), int(cfg["date_range"]["end_year"]) + 1))
    extract_all(years=years, force_refresh=False)


with DAG(
    dag_id="tme_gus_backfill_chunked",
    description="Automatyczne dociąganie historii 2019-2026 co 20 min z poszanowaniem limitów API GUS",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2025, 1, 1),
    schedule="*/20 * * * *",  
    catchup=False,
    max_active_runs=1,
    tags=["tme", "gus", "nbp", "backfill"],
) as backfill_dag:
    t_backfill = PythonOperator(
        task_id="extract_backfill_chunk",
        python_callable=_run_backfill_chunk,
    )
