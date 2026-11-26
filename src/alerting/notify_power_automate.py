"""Generate and dispatch lean MVP business alerts (Teams Adaptive Card) to Power Automate."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

from src.core.db import get_pg_connection
from src.core.settings import REPORTS_DIR, get_settings


def fetch_latest_alert_snapshot() -> dict[str, Any]:
    """Query latest Gold mart statuses and recent GUS revisions from Supabase."""
    settings = get_settings()
    snapshot: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tot_latest": [],
        "market_pulse_latest": [],
        "revisions_last_30d": 0,
    }

    with get_pg_connection(settings) as conn:
        with conn.cursor() as cur:
            # 1. Latest Terms of Trade per sector (PKWiU 26, 27, 28)
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        period_date,
                        sector_code,
                        sector_name_pl,
                        implied_tot_yoy,
                        price_spread_pp,
                        pricing_status,
                        ROW_NUMBER() OVER (PARTITION BY sector_code ORDER BY period_date DESC) AS rn
                    FROM mart.mv_electronics_terms_of_trade
                    WHERE sector_code IN ('PKWiU_26_ELEKTRONIKA', 'PKWiU_27_ELEKTRYKA', 'PKWiU_28_MASZYNY')
                )
                SELECT period_date::text, sector_code, sector_name_pl, implied_tot_yoy, price_spread_pp, pricing_status
                FROM ranked
                WHERE rn = 1
                ORDER BY sector_code;
                """
            )
            for row in cur.fetchall():
                snapshot["tot_latest"].append(
                    {
                        "period_date": row[0],
                        "sector_code": row[1],
                        "sector_name_pl": row[2],
                        "implied_tot_yoy": float(row[3]) if row[3] is not None else None,
                        "price_spread_pp": float(row[4]) if row[4] is not None else None,
                        "pricing_status": row[5],
                    }
                )

            # 2. Latest Export Market Pulse (UE, CEE, TOTAL)
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        period_date,
                        target_market,
                        market_name_pl,
                        sitc7_export_vol_yoy_pct,
                        market_momentum_status,
                        ROW_NUMBER() OVER (PARTITION BY target_market ORDER BY period_date DESC) AS rn
                    FROM mart.mv_export_market_pulse
                )
                SELECT period_date::text, target_market, market_name_pl, sitc7_export_vol_yoy_pct, market_momentum_status
                FROM ranked
                WHERE rn = 1
                ORDER BY target_market;
                """
            )
            for row in cur.fetchall():
                snapshot["market_pulse_latest"].append(
                    {
                        "period_date": row[0],
                        "target_market": row[1],
                        "market_name_pl": row[2],
                        "sitc7_export_vol_yoy_pct": float(row[3]) if row[3] is not None else None,
                        "market_momentum_status": row[4],
                    }
                )

            # 3. Recent GUS revisions logged in audit table
            cur.execute(
                """
                SELECT COUNT(*)
                FROM staging.etl_revision_audit
                WHERE detected_at >= now() - INTERVAL '30 days';
                """
            )
            snapshot["revisions_last_30d"] = int(cur.fetchone()[0])

    return snapshot


def evaluate_alerts(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    """Evaluate lean MVP critical rules only (margin squeeze & export contraction)."""
    alerts: list[dict[str, str]] = []

    for row in snapshot.get("tot_latest", []):
        if row.get("pricing_status") == "MARGIN_SQUEEZE_ALERT":
            alerts.append(
                {
                    "category": "MARGIN_PRESSURE",
                    "title": f"Presja marżowa ({row['sector_code']}, {row['period_date']})",
                    "message": (
                        f"Terms of Trade spadło do {row['implied_tot_yoy']:.2f} "
                        f"(spread eksport-import: {row['price_spread_pp']:+.2f} pp). "
                        "Rekomendacja: przegląd cenników eksportowych i zabezpieczeń EUR/USD."
                    ),
                }
            )

    for row in snapshot.get("market_pulse_latest", []):
        if row.get("market_momentum_status") == "CONTRACTION":
            alerts.append(
                {
                    "category": "EXPORT_DEMAND",
                    "title": f"Hamowanie eksportu SITC 7 – rynek {row['target_market']} ({row['period_date']})",
                    "message": (
                        f"Wolumen eksportu SITC 7 spadł r/r o {row['sitc7_export_vol_yoy_pct']:+.2f}%. "
                        "Rekomendacja: ograniczyć ryzyko nadwyżek (overstock) w indeksach wolnorotujących."
                    ),
                }
            )

    return alerts


def build_power_automate_payload(snapshot: dict[str, Any], alerts: list[dict[str, str]]) -> dict[str, Any]:
    """Build a lean Power Automate HTTP Webhook payload with a Teams Adaptive Card v1.4."""
    has_alerts = len(alerts) > 0
    status_label = "ALERT" if has_alerts else "OK"

    facts = []
    for row in snapshot.get("tot_latest", []):
        facts.append(
            {
                "title": f"{row['sector_code']} ({row['period_date']})",
                "value": f"ToT={row['implied_tot_yoy']} | {row['pricing_status']}",
            }
        )
    for row in snapshot.get("market_pulse_latest", []):
        facts.append(
            {
                "title": f"SITC 7 {row['target_market']} ({row['period_date']})",
                "value": f"Vol YoY={row['sitc7_export_vol_yoy_pct']:+.2f}% | {row['market_momentum_status']}",
            }
        )
    facts.append({"title": "Rewizje GUS (30 dni)", "value": str(snapshot.get("revisions_last_30d", 0))})

    if has_alerts:
        alert_blocks = [
            {
                "type": "TextBlock",
                "text": f"**{a['title']}** — {a['message']}",
                "wrap": True,
                "spacing": "Small",
            }
            for a in alerts
        ]
    else:
        alert_blocks = [
            {
                "type": "TextBlock",
                "text": "Brak alertów krytycznych — brak presji marżowej i brak hamowania eksportu SITC 7.",
                "wrap": True,
                "spacing": "Small",
            }
        ]

    adaptive_card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"TME Export & Sourcing Pulse – Status: {status_label}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Wygenerowano: {snapshot['generated_at_utc']} | Źródło: GUS DBW + NBP (Supabase Gold)",
                "isSubtle": True,
                "spacing": "None",
                "wrap": True,
            },
            {"type": "FactSet", "facts": facts},
            *alert_blocks,
        ],
    }

    return {
        "source": "tme-gus-export-sourcing-pulse",
        "generated_at_utc": snapshot["generated_at_utc"],
        "status": status_label,
        "has_alerts": has_alerts,
        "alert_count": len(alerts),
        "alerts": alerts,
        "snapshot": snapshot,
        "teams_adaptive_card": adaptive_card,
    }


def dispatch_alerts(dry_run: bool = False) -> dict[str, Any]:
    """Fetch latest Gold snapshot, build payload, save artifact, and optionally POST to Power Automate."""
    settings = get_settings()
    snapshot = fetch_latest_alert_snapshot()
    alerts = evaluate_alerts(snapshot)
    payload = build_power_automate_payload(snapshot, alerts)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "last_power_automate_payload.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== POWER AUTOMATE ALERT SUMMARY (status={payload['status']}, alerts={len(alerts)}) ===")
    if alerts:
        for a in alerts:
            print(f"  [ALERT] {a['title']}: {a['message']}")
    else:
        print("  [OK] Brak alertów krytycznych.")
    print(f"Saved payload snapshot -> {out_path}")

    webhook_url = settings.pa_webhook_url.strip()
    if dry_run or not webhook_url:
        reason = "--dry-run flag" if dry_run else "PA_WEBHOOK_URL is not configured in .env"
        print(f"[DRY-RUN] Skipping HTTP POST to Power Automate ({reason}).")
        return payload

    response = httpx.post(webhook_url, json=payload, timeout=15.0)
    response.raise_for_status()
    print(f"OK: Dispatched alert payload to Power Automate (HTTP {response.status_code}).")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Gold mart alerts and dispatch to Power Automate.")
    parser.add_argument("--dry-run", action="store_true", help="Build and save payload without sending HTTP request.")
    args = parser.parse_args()
    try:
        dispatch_alerts(dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
