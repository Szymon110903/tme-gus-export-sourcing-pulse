"""Production monthly Apache Airflow DAG for TME Export & Sourcing Pulse."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator

DEFAULT_ARGS = {
    "owner": "tme-data-analytics",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}


# Lazy task callables (Airflow best practice: keep DAG parsing lightweight and fast)
def _task_init_db() -> None:
    from src.pipelines.init_db import run_db_init

    run_db_init()


def _task_sync_dictionaries() -> None:
    from src.pipelines.sync_dictionaries import sync_all_dictionaries

    sync_all_dictionaries()


def _task_discover_metadata() -> None:
    from src.pipelines.discover_metadata import generate_metadata_catalog

    generate_metadata_catalog()


def _task_extract_recent_window() -> None:
    """Extract current + previous calendar year (catches new months & GUS revisions)."""
    from src.pipelines.extract_trade import extract_all

    current_year = datetime.now(timezone.utc).year
    extract_all(years=[current_year - 1, current_year], force_refresh=False)


def _task_build_marts() -> None:
    from src.pipelines.build_marts import build_and_refresh_marts

    build_and_refresh_marts()


def _task_run_dq_gates() -> None:
    """Execute SQL Data Quality Gates and fail the DAG if any CRITICAL check fails."""
    from src.quality.run_dq import run_data_quality_checks

    results = run_data_quality_checks()
    critical_failures = [r for r in results if r.status == "FAIL"]
    for r in results:
        print(f"[{r.status:4s}] ({r.severity:8s}) {r.check_name}: failed_rows={r.failed_rows} ({r.details})")
    if critical_failures:
        names = ", ".join(r.check_name for r in critical_failures)
        raise RuntimeError(f"DQ GATE FAILED: Critical violations detected in: {names}")


def _task_run_statistical_models() -> None:
    from src.analytics.models_fx_granger import run_models

    run_models()


def _task_generate_html_report() -> None:
    from src.analytics.generate_report import generate_reports

    generate_reports()


def _task_notify_power_automate() -> None:
    from src.alerting.notify_power_automate import dispatch_alerts

    dispatch_alerts()


with DAG(
    dag_id="tme_gus_export_sourcing_monthly",
    description="Docelowy potok miesięczny: GUS DBW + NBP -> Supabase (Bronze/Silver/Gold) -> DQ -> Modele -> HTML -> Power Automate",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2025, 1, 1),
    schedule="0 6 22 * *",
    catchup=False,
    max_active_runs=1,
    tags=["tme", "gus", "nbp", "production", "monthly"],
) as monthly_dag:
    t_init_db = PythonOperator(task_id="init_db", python_callable=_task_init_db)
    t_sync_dicts = PythonOperator(task_id="sync_dictionaries", python_callable=_task_sync_dictionaries)
    t_discover = PythonOperator(task_id="discover_metadata", python_callable=_task_discover_metadata)
    t_extract = PythonOperator(task_id="extract_recent_window", python_callable=_task_extract_recent_window)
    t_marts = PythonOperator(task_id="build_marts", python_callable=_task_build_marts)
    t_dq = PythonOperator(task_id="run_dq_gates", python_callable=_task_run_dq_gates)
    t_models = PythonOperator(task_id="run_statistical_models", python_callable=_task_run_statistical_models)
    t_report = PythonOperator(task_id="generate_html_report", python_callable=_task_generate_html_report)
    t_notify = PythonOperator(task_id="notify_power_automate", python_callable=_task_notify_power_automate)

    (
        t_init_db
        >> t_sync_dicts
        >> t_discover
        >> t_extract
        >> t_marts
        >> t_dq
        >> t_models
        >> t_report
        >> t_notify
    )

