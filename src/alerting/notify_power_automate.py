"""Generate and dispatch business alert payloads (Teams Adaptive Card) to Power Automate."""

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
        "hub_gap_latest": None,
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
                        imp_price_yoy_idx,
                        exp_price_yoy_idx,
                        implied_tot_yoy,
                        price_spread_pp,
                        tot_ma3,
                        tot_z36,
                        eur_pln_avg,
                        pricing_status,
                        ROW_NUMBER() OVER (PARTITION BY sector_code ORDER BY period_date DESC) AS rn
                    FROM mart.mv_electronics_terms_of_trade
                    WHERE sector_code IN ('PKWiU_26_ELEKTRONIKA', 'PKWiU_27_ELEKTRYKA', 'PKWiU_28_MASZYNY')
                )
                SELECT
                    period_date::text, sector_code, sector_name_pl,
                    imp_price_yoy_idx, exp_price_yoy_idx, implied_tot_yoy,
                    price_spread_pp, tot_ma3, tot_z36, eur_pln_avg, pricing_status
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
                        "imp_price_yoy_idx": float(row[3]) if row[3] is not None else None,
                        "exp_price_yoy_idx": float(row[4]) if row[4] is not None else None,
                        "implied_tot_yoy": float(row[5]) if row[5] is not None else None,
                        "price_spread_pp": float(row[6]) if row[6] is not None else None,
                        "tot_ma3": float(row[7]) if row[7] is not None else None,
                        "tot_z36": float(row[8]) if row[8] is not None else None,
                        "eur_pln_avg": float(row[9]) if row[9] is not None else None,
                        "pricing_status": row[10],
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
                        sitc7_export_vol_ma3_pct,
                        ind_foreign_new_orders_yoy_pct,
                        market_momentum_status,
                        ROW_NUMBER() OVER (PARTITION BY target_market ORDER BY period_date DESC) AS rn
                    FROM mart.mv_export_market_pulse
                )
                SELECT
                    period_date::text, target_market, market_name_pl,
                    sitc7_export_vol_yoy_pct, sitc7_export_vol_ma3_pct,
                    ind_foreign_new_orders_yoy_pct, market_momentum_status
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
                        "sitc7_export_vol_ma3_pct": float(row[4]) if row[4] is not None else None,
                        "ind_foreign_new_orders_yoy_pct": float(row[5]) if row[5] is not None else None,
                        "market_momentum_status": row[6],
                    }
                )

            # 3. Latest Hub Intermediation Gap (Developing Asia / LatAm)
            cur.execute(
                """
                SELECT
                    period_date::text, region_group, region_name_pl,
                    imp_origin_eur, imp_consign_eur, indirect_hub_share_pct, share_gap_pp
                FROM mart.mv_hub_intermediation_gap
                WHERE region_group = 'DEVELOPING_ASIA_LATAM'
                ORDER BY period_date DESC
                LIMIT 1;
                """
            )
            hub_row = cur.fetchone()
            if hub_row:
                snapshot["hub_gap_latest"] = {
                    "period_date": hub_row[0],
                    "region_group": hub_row[1],
                    "region_name_pl": hub_row[2],
                    "imp_origin_eur": float(hub_row[3]) if hub_row[3] is not None else None,
                    "imp_consign_eur": float(hub_row[4]) if hub_row[4] is not None else None,
                    "indirect_hub_share_pct": float(hub_row[5]) if hub_row[5] is not None else None,
                    "share_gap_pp": float(hub_row[6]) if hub_row[6] is not None else None,
                }

            # 4. Recent GUS revisions logged in audit table
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
    """Evaluate business alert rules for TME Purchasing & Category Management."""
    alerts: list[dict[str, str]] = []

    for row in snapshot.get("tot_latest", []):
        status = row.get("pricing_status")
        sector = row.get("sector_code")
        period = row.get("period_date")
        tot = row.get("implied_tot_yoy")
        spread = row.get("price_spread_pp")
        if status == "MARGIN_SQUEEZE_ALERT":
            alerts.append(
                {
                    "severity": "HIGH",
                    "category": "MARGIN_PRESSURE",
                    "title": f"Presja marżowa ({sector}, {period})",
                    "message": (
                        f"Terms of Trade spadło do {tot:.2f} (spread eksport-import: {spread:+.2f} pp). "
                        "Rekomendacja: przegląd cenników eksportowych i polityki zabezpieczeń EUR/USD."
                    ),
                }
            )
        elif status == "MARGIN_TAILWIND":
            alerts.append(
                {
                    "severity": "INFO",
                    "category": "MARGIN_OPPORTUNITY",
                    "title": f"Korzystne Terms of Trade ({sector}, {period})",
                    "message": (
                        f"Terms of Trade wynosi {tot:.2f} (spread: {spread:+.2f} pp). "
                        "Sprzyjające otoczenie cenowe dla ekspansji wolumenowej."
                    ),
                }
            )

    for row in snapshot.get("market_pulse_latest", []):
        status = row.get("market_momentum_status")
        market = row.get("target_market")
        period = row.get("period_date")
        vol = row.get("sitc7_export_vol_yoy_pct")
        if status == "CONTRACTION":
            alerts.append(
                {
                    "severity": "HIGH",
                    "category": "EXPORT_DEMAND",
                    "title": f"Hamowanie eksportu SITC 7 – rynek {market} ({period})",
                    "message": (
                        f"Wolumen eksportu SITC 7 spadł r/r o {vol:+.2f}%. "
                        "Rekomendacja: ograniczyć ryzyko nadwyżek (overstock) w indeksach wolnorotujących."
                    ),
                }
            )
        elif status == "STRONG_EXPANSION":
            alerts.append(
                {
                    "severity": "MEDIUM",
                    "category": "EXPORT_DEMAND",
                    "title": f"Silna ekspansja eksportu SITC 7 – rynek {market} ({period})",
                    "message": (
                        f"Wolumen eksportu SITC 7 rośnie r/r o {vol:+.2f}%. "
                        "Rekomendacja: podnieść bufor Safety Stock dla kluczowych indeksów grupy A."
                    ),
                }
            )

    hub = snapshot.get("hub_gap_latest")
    if hub and hub.get("indirect_hub_share_pct") is not None and hub["indirect_hub_share_pct"] >= 30.0:
        alerts.append(
            {
                "severity": "MEDIUM",
                "category": "SOURCING_HUB_DEPENDENCY",
                "title": f"Wysoki udział pośrednictwa hubów UE ({hub['period_date']})",
                "message": (
                    f"{hub['indirect_hub_share_pct']:.1f}% importu z krajów rozwijających się (Azja/LatAm) "
                    "trafia do Polski przez huby pośredniczące UE. Warto zweryfikować stawki frachtu bezpośredniego."
                ),
            }
        )

    if not alerts:
        alerts.append(
            {
                "severity": "INFO",
                "category": "STATUS_OK",
                "title": "Brak alertów krytycznych – stabilne otoczenie makro",
                "message": "Wszystkie wskaźniki Terms of Trade oraz dynamika eksportu SITC 7 mieszczą się w pasmach neutralnych.",
            }
        )

    return alerts


def build_power_automate_payload(snapshot: dict[str, Any], alerts: list[dict[str, str]]) -> dict[str, Any]:
    """Build a Power Automate HTTP Webhook payload containing a Teams Adaptive Card v1.4."""
    high_count = sum(1 for a in alerts if a["severity"] == "HIGH")
    overall_severity = "HIGH" if high_count > 0 else ("MEDIUM" if any(a["severity"] == "MEDIUM" for a in alerts) else "INFO")

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

    alert_blocks = [
        {
            "type": "TextBlock",
            "text": f"**[{a['severity']}] {a['title']}** — {a['message']}",
            "wrap": True,
            "spacing": "Small",
        }
        for a in alerts
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
                "text": f"TME Export & Sourcing Pulse – Raport Alertów ({overall_severity})",
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
            {
                "type": "TextBlock",
                "text": "Sygnały decyzyjne dla Zakupów i Category Managementu:",
                "weight": "Bolder",
                "spacing": "Medium",
            },
            *alert_blocks,
        ],
    }

    return {
        "source": "tme-gus-export-sourcing-pulse",
        "generated_at_utc": snapshot["generated_at_utc"],
        "overall_severity": overall_severity,
        "alert_count": len(alerts),
        "high_severity_count": high_count,
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

    print(f"=== POWER AUTOMATE ALERT SUMMARY (overall={payload['overall_severity']}, alerts={len(alerts)}) ===")
    for a in alerts:
        print(f"  [{a['severity']:6s}] {a['title']}: {a['message']}")
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

