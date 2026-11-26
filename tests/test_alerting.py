"""Unit tests for lean MVP Power Automate alert evaluation and Adaptive Card builder."""

from src.alerting.notify_power_automate import (
    build_power_automate_payload,
    evaluate_alerts,
)


def test_evaluate_alerts_detects_margin_squeeze_and_contraction():
    snapshot = {
        "generated_at_utc": "2026-11-25T18:00:00Z",
        "tot_latest": [
            {
                "period_date": "2026-09-01",
                "sector_code": "PKWiU_26_ELEKTRONIKA",
                "implied_tot_yoy": 96.4,
                "price_spread_pp": -3.6,
                "pricing_status": "MARGIN_SQUEEZE_ALERT",
            }
        ],
        "market_pulse_latest": [
            {
                "period_date": "2026-08-01",
                "target_market": "EU",
                "sitc7_export_vol_yoy_pct": -6.2,
                "market_momentum_status": "CONTRACTION",
            }
        ],
        "revisions_last_30d": 12,
    }

    alerts = evaluate_alerts(snapshot)
    categories = {a["category"] for a in alerts}

    assert len(alerts) == 2
    assert categories == {"MARGIN_PRESSURE", "EXPORT_DEMAND"}

    payload = build_power_automate_payload(snapshot, alerts)
    assert payload["status"] == "ALERT"
    assert payload["has_alerts"] is True
    assert payload["alert_count"] == 2
    assert payload["teams_adaptive_card"]["type"] == "AdaptiveCard"
    assert payload["teams_adaptive_card"]["version"] == "1.4"


def test_evaluate_alerts_returns_empty_and_ok_when_no_critical_breach():
    snapshot = {
        "generated_at_utc": "2026-11-25T18:00:00Z",
        "tot_latest": [
            {
                "period_date": "2026-09-01",
                "sector_code": "PKWiU_26_ELEKTRONIKA",
                "implied_tot_yoy": 103.12,
                "price_spread_pp": 3.2,
                "pricing_status": "MARGIN_TAILWIND",
            }
        ],
        "market_pulse_latest": [
            {
                "period_date": "2026-08-01",
                "target_market": "EU",
                "sitc7_export_vol_yoy_pct": 13.1,
                "market_momentum_status": "STRONG_EXPANSION",
            }
        ],
        "revisions_last_30d": 0,
    }

    alerts = evaluate_alerts(snapshot)
    assert alerts == []

    payload = build_power_automate_payload(snapshot, alerts)
    assert payload["status"] == "OK"
    assert payload["has_alerts"] is False
    assert payload["alert_count"] == 0
