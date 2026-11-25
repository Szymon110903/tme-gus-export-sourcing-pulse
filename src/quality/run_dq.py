"""Execute SQL Data Quality Gates against Supabase PostgreSQL 16."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from src.core.db import get_pg_connection
from src.core.settings import DATA_QUALITY_DIR, get_settings


@dataclass(frozen=True)
class DQResult:
    check_name: str
    severity: str
    failed_rows: int
    details: str

    @property
    def status(self) -> str:
        if self.failed_rows == 0:
            return "PASS"
        return "FAIL" if self.severity == "CRITICAL" else "WARN"


def run_data_quality_checks() -> list[DQResult]:
    settings = get_settings()
    sql_path = DATA_QUALITY_DIR / "dq_checks.sql"
    query = sql_path.read_text(encoding="utf-8")

    results: list[DQResult] = []
    with get_pg_connection(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            for check_name, severity, failed_rows, details in cur.fetchall():
                results.append(
                    DQResult(
                        check_name=str(check_name),
                        severity=str(severity),
                        failed_rows=int(failed_rows),
                        details=str(details),
                    )
                )
    return results


def main() -> None:
    results = run_data_quality_checks()
    print("=== DATA QUALITY GATES REPORT ===")
    critical_failures = 0
    warnings = 0
    for r in results:
        print(f"  [{r.status:4s}] ({r.severity:8s}) {r.check_name:35s} | failed_rows={r.failed_rows:4d} | {r.details}")
        if r.status == "FAIL":
            critical_failures += 1
        elif r.status == "WARN":
            warnings += 1

    print(f"Summary: total={len(results)}, critical_failures={critical_failures}, warnings={warnings}")
    if critical_failures > 0:
        print("DQ GATE FAILED: Critical data quality violations detected.", file=sys.stderr)
        sys.exit(1)
    print("OK: All critical Data Quality Gates passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

