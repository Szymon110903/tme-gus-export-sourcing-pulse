"""Unit tests for Power Automate alert evaluation and Adaptive Card payload builder."""

from src.alerting.notify_power_automate import (
    build_power_automate_payload,
    evaluate_alerts,
)


def test_evaluate_alerts_detects_high_margin_squeeze_and_contraction():
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
        "hub_gap_latest": {
            "period_date": "2026-09-01",
            "region_group": "DEVELOPING_ASIA_LATAM",
            "indirect_hub_share_pct": 34.5,
        },
        "revisions_last_30d": 12,
    }

    alerts = evaluate_alerts(snapshot)
    severities = [a["severity"] for a in alerts]
    categories = {a["category"] for a in alerts}

    assert severities.count("HIGH") == 2
    assert "MARGIN_PRESSURE" in categories
    assert "EXPORT_DEMAND" in categories
    assert "SOURCING_HUB_DEPENDENCY" in categories

    payload = build_power_automate_payload(snapshot, alerts)
    assert payload["overall_severity"] == "HIGH"
    assert payload["high_severity_count"] == 2
    assert payload["teams_adaptive_card"]["type"] == "AdaptiveCard"
    assert payload["teams_adaptive_card"]["version"] == "1.4"


def test_evaluate_alerts_returns_info_when_all_neutral():
    snapshot = {
        "generated_at_utc": "2026-11-25T18:00:00Z",
        "tot_latest": [
            {
                "period_date": "2026-09-01",
                "sector_code": "PKWiU_26_ELEKTRONIKA",
                "implied_tot_yoy": 100.2,
                "price_spread_pp": 0.2,
                "pricing_status": "NEUTRAL",
            }
        ],
        "market_pulse_latest": [
            {
                "period_date": "2026-08-01",
                "target_market": "EU",
                "sitc7_export_vol_yoy_pct": 1.5,
                "market_momentum_status": "STAGNATION",
            }
        ],
        "hub_gap_latest": {
            "period_date": "2026-09-01",
            "region_group": "DEVELOPING_ASIA_LATAM",
            "indirect_hub_share_pct": 18.0,
        },
        "revisions_last_30d": 0,
    }

    alerts = evaluate_alerts(snapshot)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "INFO"
    assert alerts[0]["category"] == "STATUS_OK"

    payload = build_power_automate_payload(snapshot, alerts)
    assert payload["overall_severity"] == "INFO"
    assert payload["high_severity_count"] == 0

