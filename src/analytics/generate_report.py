"""Generate interactive HTML (Plotly) report from Supabase Gold (mart.*) tables."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go

from src.core.db import get_pg_connection
from src.core.settings import REPORTS_DIR, get_settings


def _load_df(conn, query: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    for col in df.columns:
        if col.endswith(("_idx", "_pct", "_yoy", "_ma3", "_z36", "_avg", "_eur", "_pln", "_usd", "_kg", "_pp", "_rate", "_r", "_value", "_stat", "_squared")):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _chart_tot_timeseries(df_tot: pd.DataFrame) -> str:
    fig = go.Figure()
    palette = {
        "PKWiU_26_ELEKTRONIKA": "#0f62fe",
        "PKWiU_27_ELEKTRYKA": "#198038",
        "PKWiU_28_MASZYNY": "#8a3ffc",
        "PKWiU_05_32_OGOLEM": "#6f6f6f",
    }
    labels = {
        "PKWiU_26_ELEKTRONIKA": "PKWiU 26 – Elektronika i optyka",
        "PKWiU_27_ELEKTRYKA": "PKWiU 27 – Urządzenia elektryczne",
        "PKWiU_28_MASZYNY": "PKWiU 28 – Maszyny i urządzenia",
        "PKWiU_05_32_OGOLEM": "Przemysł ogółem (05–32)",
    }
    for code in ("PKWiU_26_ELEKTRONIKA", "PKWiU_27_ELEKTRYKA", "PKWiU_28_MASZYNY", "PKWiU_05_32_OGOLEM"):
        sub = df_tot[df_tot["sector_code"] == code].sort_values("period_date")
        if sub.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["period_date"],
                y=sub["implied_tot_yoy"],
                mode="lines",
                name=labels.get(code, code),
                line=dict(
                    color=palette.get(code, "#333"),
                    width=3 if code == "PKWiU_26_ELEKTRONIKA" else 1.8,
                    dash="dot" if code == "PKWiU_05_32_OGOLEM" else "solid",
                ),
            )
        )
    fig.add_hline(y=100, line_dash="dash", line_color="#444", annotation_text="Neutralne (100)")
    fig.add_hrect(y0=88, y1=97.5, fillcolor="rgba(218, 30, 40, 0.08)", line_width=0, annotation_text="Strefa Margin Squeeze (<97.5)")
    fig.update_layout(
        title="Sektorowe Terms of Trade (P_eksport / P_import × 100) – PKWiU 26/27/28",
        xaxis_title="Okres",
        yaxis_title="Implied Terms of Trade (r/r)",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=50, r=20, t=55, b=70),
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def _chart_pkwiu26_vs_fx(df_tot: pd.DataFrame) -> str:
    sub = df_tot[df_tot["sector_code"] == "PKWiU_26_ELEKTRONIKA"].sort_values("period_date").copy()
    sub["imp_yoy_pct"] = sub["imp_price_yoy_idx"] - 100.0
    sub["exp_yoy_pct"] = sub["exp_price_yoy_idx"] - 100.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sub["period_date"], y=sub["imp_yoy_pct"], mode="lines",
            name="Ceny importu PKWiU 26 (r/r %)", line=dict(color="#da1e28", width=2.6),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sub["period_date"], y=sub["exp_yoy_pct"], mode="lines",
            name="Ceny eksportu PKWiU 26 (r/r %)", line=dict(color="#0f62fe", width=2.2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sub["period_date"], y=sub["eur_pln_yoy_pct"], mode="lines",
            name="Kurs EUR/PLN (r/r %, NBP)", line=dict(color="#f1c21b", width=2.2, dash="dash"),
        )
    )
    fig.add_hline(y=0, line_color="#888", line_width=1)
    fig.update_layout(
        title="Elektronika (PKWiU 26): Ceny importu i eksportu vs kurs EUR/PLN (r/r %)",
        xaxis_title="Okres",
        yaxis_title="Zmiana r/r [%]",
        template="plotly_white",
        height=400,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=50, r=20, t=55, b=70),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_sitc7_markets(df_pulse: pd.DataFrame) -> str:
    fig = go.Figure()
    styles = {
        "EU": ("Unia Europejska (MA3)", "#0f62fe", 2.8, "solid"),
        "CEE": ("Europa Śr.-Wsch. (MA3)", "#da1e28", 2.4, "solid"),
        "TOTAL": ("Ogółem (MA3)", "#525252", 1.8, "dot"),
    }
    for code, (name, color, width, dash) in styles.items():
        sub = df_pulse[df_pulse["target_market"] == code].sort_values("period_date")
        if sub.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["period_date"],
                y=sub["sitc7_export_vol_ma3_pct"],
                mode="lines",
                name=name,
                line=dict(color=color, width=width, dash=dash),
            )
        )
    fig.add_hline(y=0, line_color="#666", line_width=1)
    fig.update_layout(
        title="Wolumen eksportu maszyn i urządzeń (SITC 7) – UE vs Europa Śr.-Wsch. (3M średnia krocząca r/r %)",
        xaxis_title="Okres",
        yaxis_title="Dynamika wolumenu r/r [%]",
        template="plotly_white",
        height=400,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=50, r=20, t=55, b=70),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_fx_r2_bars(df_fx: pd.DataFrame) -> str:
    sub = df_fx[df_fx["target_metric"].isin(["imp_price_yoy_pct", "exp_price_yoy_pct"])].copy()
    fig = go.Figure()
    for metric, label, color in (
        ("imp_price_yoy_pct", "Ceny importu (R²)", "#da1e28"),
        ("exp_price_yoy_pct", "Ceny eksportu (R²)", "#0f62fe"),
    ):
        m_df = sub[sub["target_metric"] == metric].sort_values("sector_code")
        fig.add_trace(
            go.Bar(
                x=m_df["sector_code"],
                y=(m_df["r_squared"] * 100.0).round(1),
                name=label,
                marker_color=color,
                text=(m_df["r_squared"] * 100.0).round(1).astype(str) + "%",
                textposition="outside",
            )
        )
    fig.update_layout(
        title="Jaki % zmienności cen tłumaczą kursy EUR/USD? (OLS R² wg działów PKWiU)",
        yaxis_title="R² [%]",
        yaxis=dict(range=[0, 100]),
        barmode="group",
        template="plotly_white",
        height=380,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(l=50, r=20, t=55, b=70),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def generate_reports() -> None:
    settings = get_settings()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with get_pg_connection(settings) as conn:
        df_tot = _load_df(conn, "SELECT * FROM mart.mv_electronics_terms_of_trade ORDER BY period_date, sector_code;")
        df_pulse = _load_df(conn, "SELECT * FROM mart.mv_export_market_pulse ORDER BY period_date, target_market;")
        df_fx = _load_df(conn, "SELECT * FROM mart.analytics_fx_regression ORDER BY sector_code, target_metric;")

    # Build Executive KPI snapshot (latest month per key indicator)
    latest_tot_date = df_tot["period_date"].max()
    latest_p26 = df_tot[(df_tot["period_date"] == latest_tot_date) & (df_tot["sector_code"] == "PKWiU_26_ELEKTRONIKA")].iloc[0]

    latest_pulse_date = df_pulse["period_date"].max()
    latest_eu = df_pulse[(df_pulse["period_date"] == latest_pulse_date) & (df_pulse["target_market"] == "EU")].iloc[0]
    latest_cee = df_pulse[(df_pulse["period_date"] == latest_pulse_date) & (df_pulse["target_market"] == "CEE")].iloc[0]

    fx_p26_imp = df_fx[(df_fx["sector_code"] == "PKWiU_26_ELEKTRONIKA") & (df_fx["target_metric"] == "imp_price_yoy_pct")].iloc[0]

    kpi_rows = [
        {"KPI": "PKWiU 26 Elektronika – Terms of Trade", "Okres": str(latest_tot_date), "Wartość": f"{latest_p26['implied_tot_yoy']:.2f}", "Status / Kontekst": str(latest_p26["pricing_status"])},
        {"KPI": "PKWiU 26 Elektronika – R² wpływu EUR/USD na import", "Okres": f"n={int(fx_p26_imp['n_obs'])} mies.", "Wartość": f"{fx_p26_imp['r_squared']*100:.1f}%", "Status / Kontekst": f"beta_EUR={fx_p26_imp['beta_eur_yoy']:+.2f} (p={fx_p26_imp['p_val_eur']:.4f})"},
        {"KPI": "Wolumen eksportu SITC 7 – Unia Europejska (r/r)", "Okres": str(latest_pulse_date), "Wartość": f"{latest_eu['sitc7_export_vol_yoy_pct']:+.1f}%", "Status / Kontekst": str(latest_eu["market_momentum_status"])},
        {"KPI": "Wolumen eksportu SITC 7 – Europa Śr.-Wsch. (r/r)", "Okres": str(latest_pulse_date), "Wartość": f"{latest_cee['sitc7_export_vol_yoy_pct']:+.1f}%", "Status / Kontekst": str(latest_cee["market_momentum_status"])},
    ]
    kpi_df = pd.DataFrame(kpi_rows)

    # Latest sector ToT HTML table
    latest_tot_tbl = (
        df_tot[df_tot["period_date"] == latest_tot_date][
            ["sector_name_pl", "imp_price_yoy_idx", "exp_price_yoy_idx", "implied_tot_yoy", "tot_ma3", "pricing_status"]
        ]
        .rename(
            columns={
                "sector_name_pl": "Dział PKWiU",
                "imp_price_yoy_idx": "Import r/r",
                "exp_price_yoy_idx": "Eksport r/r",
                "implied_tot_yoy": "Terms of Trade",
                "tot_ma3": "ToT MA3",
                "pricing_status": "Status Pricingu",
            }
        )
        .to_html(index=False, classes="data-table")
    )

    fx_tbl = (
        df_fx[["sector_code", "target_metric", "n_obs", "r_squared", "beta_eur_yoy", "p_val_eur", "beta_usd_yoy", "p_val_usd", "interpretation_pl"]]
        .rename(
            columns={
                "sector_code": "Sektor",
                "target_metric": "Zmienna celu",
                "n_obs": "n",
                "r_squared": "R²",
                "beta_eur_yoy": "β EUR",
                "p_val_eur": "p (EUR)",
                "beta_usd_yoy": "β USD",
                "p_val_usd": "p (USD)",
                "interpretation_pl": "Interpretacja",
            }
        )
        .to_html(index=False, classes="data-table")
    )

    chart1 = _chart_tot_timeseries(df_tot)
    chart2 = _chart_pkwiu26_vs_fx(df_tot)
    chart3 = _chart_sitc7_markets(df_pulse)
    chart4 = _chart_fx_r2_bars(df_fx)

    kpi_cards_html = "".join(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{r['KPI']}</div>
            <div class="kpi-value">{r['Wartość']}</div>
            <div class="kpi-sub">{r['Okres']} · {r['Status / Kontekst']}</div>
        </div>
        """
        for r in kpi_rows
    )

    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>TME Export &amp; Sourcing Pulse – Raport Analityczny</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #f4f6f9; color: #161616; }}
  header {{ background: #0f172a; color: #fff; padding: 28px 40px; }}
  header h1 {{ margin: 0 0 6px 0; font-size: 24px; }}
  header p {{ margin: 0; color: #cbd5e1; font-size: 14px; }}
  main {{ max-width: 1280px; margin: 24px auto; padding: 0 24px 48px 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .kpi-card {{ background: #fff; border-radius: 10px; padding: 18px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 4px solid #0f62fe; }}
  .kpi-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.4px; color: #525252; margin-bottom: 8px; }}
  .kpi-value {{ font-size: 28px; font-weight: 700; color: #0f172a; }}
  .kpi-sub {{ font-size: 12px; color: #64748b; margin-top: 6px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 20px 24px; margin-bottom: 22px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .card h2 {{ margin-top: 0; font-size: 18px; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .data-table th {{ background: #f1f5f9; text-align: left; padding: 9px 10px; border-bottom: 2px solid #cbd5e1; }}
  .data-table td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
  footer {{ text-align: center; color: #64748b; font-size: 12px; margin-top: 32px; }}
</style>
</head>
<body>
<header>
  <h1>TME Export &amp; Sourcing Pulse — Raport Analityczny</h1>
  <p>Monitoring cen importu/eksportu elektroniki (PKWiU 26/27/28), rynków eksportowych (SITC 7) i wrażliwości kursowej (NBP) · Wygenerowano: {generated_at}</p>
</header>
<main>
  <section class="kpi-grid">{kpi_cards_html}</section>

  <section class="card">
    <h2>1. Najnowszy odczyt Terms of Trade i statusów Pricingu ({latest_tot_date})</h2>
    {latest_tot_tbl}
  </section>

  <section class="card">
    <h2>2. Sektorowe Terms of Trade w czasie (2019–2026)</h2>
    {chart1}
  </section>

  <section class="card">
    <h2>3. Elektronika (PKWiU 26): transmisja kursu EUR/PLN na ceny importu i eksportu</h2>
    {chart2}
  </section>

  <section class="card">
    <h2>4. Chłonność rynków eksportowych SITC 7 (UE vs Europa Środkowo-Wschodnia)</h2>
    {chart3}
  </section>

  <section class="card">
    <h2>5. Wyniki regresji OLS (Newey-West HAC): siła wpływu kursów EUR i USD</h2>
    {chart4}
    {fx_tbl}
  </section>

  <footer>
    Źródło danych: Główny Urząd Statystyczny – Dziedzinowe Bazy Wiedzy (api-dbw.stat.gov.pl, licencja CC BY 4.0) oraz Narodowy Bank Polski (api.nbp.pl).
  </footer>
</main>
</body>
</html>
"""

    html_path = REPORTS_DIR / "tme_export_sourcing_report.html"
    html_path.write_text(html, encoding="utf-8")

    print(f"OK: Generated HTML report -> {html_path} ({html_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    try:
        generate_reports()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
