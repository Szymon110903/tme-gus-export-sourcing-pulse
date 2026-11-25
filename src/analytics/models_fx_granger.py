"""Statistical models (OLS FX regression with HAC errors, lead-lag correlations, Granger causality).

Writes BI-ready result tables directly into Supabase PostgreSQL (mart.analytics_fx_regression,
mart.analytics_lead_lag_granger) for Power BI / SAP Analytics Cloud consumption.
"""

from __future__ import annotations

import sys
import warnings
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import pearsonr
from statsmodels.tsa.stattools import grangercausalitytests

from src.core.db import execute_sql_file, get_pg_connection
from src.core.settings import get_settings

warnings.filterwarnings("ignore", category=FutureWarning)


def _safe_float(val: Any, digits: int = 4) -> float | None:
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return None
    return round(float(val), digits)


def fit_fx_regressions(df_tot: pd.DataFrame) -> list[dict[str, Any]]:
    """Estimate OLS with Newey-West HAC standard errors: target ~ const + eur_pln_yoy + usd_pln_yoy."""
    results: list[dict[str, Any]] = []
    targets = [
        ("imp_price_yoy_pct", "Ceny importu r/r"),
        ("exp_price_yoy_pct", "Ceny eksportu r/r"),
        ("implied_tot_yoy", "Terms of Trade"),
    ]

    df = df_tot.copy()
    df["imp_price_yoy_pct"] = df["imp_price_yoy_idx"] - 100.0
    df["exp_price_yoy_pct"] = df["exp_price_yoy_idx"] - 100.0

    for (sector_code, sector_name_pl), grp in df.groupby(["sector_code", "sector_name_pl"]):
        grp = grp.sort_values("period_date")
        for target_col, target_pl in targets:
            sub = grp[[target_col, "eur_pln_yoy_pct", "usd_pln_yoy_pct"]].dropna()
            if len(sub) < 24:
                continue

            X = sm.add_constant(sub[["eur_pln_yoy_pct", "usd_pln_yoy_pct"]].astype(float))
            y = sub[target_col].astype(float)
            model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

            r2 = _safe_float(model.rsquared, 4)
            adj_r2 = _safe_float(model.rsquared_adj, 4)
            b_eur = _safe_float(model.params.get("eur_pln_yoy_pct"), 4)
            p_eur = _safe_float(model.pvalues.get("eur_pln_yoy_pct"), 6)
            b_usd = _safe_float(model.params.get("usd_pln_yoy_pct"), 4)
            p_usd = _safe_float(model.pvalues.get("usd_pln_yoy_pct"), 6)
            f_p = _safe_float(model.f_pvalue, 6)

            sig_parts = []
            if p_eur is not None and p_eur < 0.05:
                sig_parts.append(f"EUR istotny (beta={b_eur:+.2f}, p={p_eur:.3f})")
            if p_usd is not None and p_usd < 0.05:
                sig_parts.append(f"USD istotny (beta={b_usd:+.2f}, p={p_usd:.3f})")
            if not sig_parts:
                interp = f"{target_pl}: kursy EUR/USD nieistotne statystycznie (R²={r2:.2f})."
            else:
                interp = f"{target_pl}: " + "; ".join(sig_parts) + f" (R²={r2:.2f})."

            results.append(
                {
                    "sector_code": str(sector_code),
                    "sector_name_pl": str(sector_name_pl),
                    "target_metric": target_col,
                    "n_obs": int(len(sub)),
                    "r_squared": r2,
                    "adj_r_squared": adj_r2,
                    "beta_eur_yoy": b_eur,
                    "p_val_eur": p_eur,
                    "beta_usd_yoy": b_usd,
                    "p_val_usd": p_usd,
                    "f_pvalue": f_p,
                    "interpretation_pl": interp,
                }
            )
    return results


def compute_lead_lag_and_granger(
    pair_code: str,
    leading_label_pl: str,
    target_label_pl: str,
    df_pair: pd.DataFrame,
    lead_col: str,
    target_col: str,
    max_lag: int = 6,
) -> list[dict[str, Any]]:
    """Compute shifted Pearson correlation (lag 0..max_lag) and Granger causality (lag 1..max_lag)."""
    rows: list[dict[str, Any]] = []
    sub = df_pair[["period_date", lead_col, target_col]].dropna().sort_values("period_date").reset_index(drop=True)
    if len(sub) < 24:
        return rows

    for lag in range(0, max_lag + 1):
        shifted = pd.DataFrame(
            {
                "lead": sub[lead_col].shift(lag).astype(float),
                "target": sub[target_col].astype(float),
            }
        ).dropna()
        if len(shifted) < 20:
            continue

        r_val, p_val = pearsonr(shifted["lead"], shifted["target"])
        g_f: float | None = None
        g_p: float | None = None
        if lag >= 1 and len(sub) >= max(24, lag * 4 + 10):
            try:
                # grangercausalitytests expects [target, predictor]
                gc = grangercausalitytests(
                    sub[[target_col, lead_col]].astype(float),
                    maxlag=[lag],
                    verbose=False,
                )
                f_stat, f_pval, _, _ = gc[lag][0]["ssr_ftest"]
                g_f = _safe_float(f_stat, 4)
                g_p = _safe_float(f_pval, 6)
            except Exception:
                g_f, g_p = None, None

        is_sig = bool(g_p is not None and g_p < 0.05) if lag >= 1 else bool(p_val < 0.05)
        rows.append(
            {
                "pair_code": pair_code,
                "leading_label_pl": leading_label_pl,
                "target_label_pl": target_label_pl,
                "lag_months": lag,
                "n_obs": int(len(shifted)),
                "pearson_r": _safe_float(r_val, 4),
                "pearson_p_value": _safe_float(p_val, 6),
                "granger_f_stat": g_f,
                "granger_p_value": g_p,
                "is_significant": is_sig,
            }
        )
    return rows


def run_models() -> None:
    settings = get_settings()

    with get_pg_connection(settings) as conn:
        execute_sql_file(conn, "05_mart_analytics_tables.sql")
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT period_date, sector_code, sector_name_pl,
                       imp_price_yoy_idx, exp_price_yoy_idx, implied_tot_yoy,
                       eur_pln_yoy_pct, usd_pln_yoy_pct
                FROM mart.mv_electronics_terms_of_trade
                ORDER BY sector_code, period_date;
                """
            )
            tot_cols = [d.name for d in cur.description]
            df_tot = pd.DataFrame(cur.fetchall(), columns=tot_cols)

            cur.execute(
                """
                SELECT period_date, target_market, market_name_pl,
                       sitc7_export_vol_yoy_pct, sitc7_import_vol_yoy_pct,
                       ind_foreign_new_orders_yoy_pct
                FROM mart.mv_export_market_pulse
                ORDER BY target_market, period_date;
                """
            )
            pulse_cols = [d.name for d in cur.description]
            df_pulse = pd.DataFrame(cur.fetchall(), columns=pulse_cols)

        for col in ("imp_price_yoy_idx", "exp_price_yoy_idx", "implied_tot_yoy", "eur_pln_yoy_pct", "usd_pln_yoy_pct"):
            df_tot[col] = pd.to_numeric(df_tot[col], errors="coerce")
        for col in ("sitc7_export_vol_yoy_pct", "sitc7_import_vol_yoy_pct", "ind_foreign_new_orders_yoy_pct"):
            df_pulse[col] = pd.to_numeric(df_pulse[col], errors="coerce")

        # 1. FX Regressions
        fx_rows = fit_fx_regressions(df_tot)

        # 2. Lead-Lag & Granger Causality
        ll_rows: list[dict[str, Any]] = []
        df_p26 = df_tot[df_tot["sector_code"] == "PKWiU_26_ELEKTRONIKA"].copy()
        df_p26["imp_yoy_pct"] = df_p26["imp_price_yoy_idx"] - 100.0
        df_p26["exp_yoy_pct"] = df_p26["exp_price_yoy_idx"] - 100.0

        ll_rows.extend(
            compute_lead_lag_and_granger(
                "USD_TO_PKWIU26_IMP",
                "Kurs USD/PLN r/r",
                "Ceny importu PKWiU 26 (Elektronika) r/r",
                df_p26,
                "usd_pln_yoy_pct",
                "imp_yoy_pct",
            )
        )
        ll_rows.extend(
            compute_lead_lag_and_granger(
                "EUR_TO_PKWIU26_IMP",
                "Kurs EUR/PLN r/r",
                "Ceny importu PKWiU 26 (Elektronika) r/r",
                df_p26,
                "eur_pln_yoy_pct",
                "imp_yoy_pct",
            )
        )
        ll_rows.extend(
            compute_lead_lag_and_granger(
                "EUR_TO_PKWIU26_EXP",
                "Kurs EUR/PLN r/r",
                "Ceny eksportu PKWiU 26 (Elektronika) r/r",
                df_p26,
                "eur_pln_yoy_pct",
                "exp_yoy_pct",
            )
        )
        ll_rows.extend(
            compute_lead_lag_and_granger(
                "PKWIU26_IMP_TO_EXP",
                "Ceny importu PKWiU 26 r/r",
                "Ceny eksportu PKWiU 26 r/r (passthrough)",
                df_p26,
                "imp_yoy_pct",
                "exp_yoy_pct",
            )
        )

        # Foreign new orders -> SITC 7 export volume (if var=815 has enough observations)
        for mkt_code, mkt_pl in (("EU", "UE"), ("CEE", "CEE"), ("TOTAL", "Ogółem")):
            df_m = df_pulse[df_pulse["target_market"] == mkt_code]
            ll_rows.extend(
                compute_lead_lag_and_granger(
                    f"FOREIGN_ORDERS_TO_SITC7_{mkt_code}",
                    "Nowe zamówienia niekrajowe r/r",
                    f"Wolumen eksportu SITC 7 ({mkt_pl}) r/r",
                    df_m,
                    "ind_foreign_new_orders_yoy_pct",
                    "sitc7_export_vol_yoy_pct",
                )
            )

        with conn.cursor() as cur:
            for r in fx_rows:
                cur.execute(
                    """
                    INSERT INTO mart.analytics_fx_regression (
                        sector_code, sector_name_pl, target_metric, n_obs,
                        r_squared, adj_r_squared, beta_eur_yoy, p_val_eur,
                        beta_usd_yoy, p_val_usd, f_pvalue, interpretation_pl, computed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (sector_code, target_metric) DO UPDATE SET
                        sector_name_pl = EXCLUDED.sector_name_pl,
                        n_obs = EXCLUDED.n_obs,
                        r_squared = EXCLUDED.r_squared,
                        adj_r_squared = EXCLUDED.adj_r_squared,
                        beta_eur_yoy = EXCLUDED.beta_eur_yoy,
                        p_val_eur = EXCLUDED.p_val_eur,
                        beta_usd_yoy = EXCLUDED.beta_usd_yoy,
                        p_val_usd = EXCLUDED.p_val_usd,
                        f_pvalue = EXCLUDED.f_pvalue,
                        interpretation_pl = EXCLUDED.interpretation_pl,
                        computed_at = now()
                    """,
                    (
                        r["sector_code"], r["sector_name_pl"], r["target_metric"], r["n_obs"],
                        r["r_squared"], r["adj_r_squared"], r["beta_eur_yoy"], r["p_val_eur"],
                        r["beta_usd_yoy"], r["p_val_usd"], r["f_pvalue"], r["interpretation_pl"],
                    ),
                )

            for r in ll_rows:
                cur.execute(
                    """
                    INSERT INTO mart.analytics_lead_lag_granger (
                        pair_code, leading_label_pl, target_label_pl, lag_months, n_obs,
                        pearson_r, pearson_p_value, granger_f_stat, granger_p_value,
                        is_significant, computed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (pair_code, lag_months) DO UPDATE SET
                        leading_label_pl = EXCLUDED.leading_label_pl,
                        target_label_pl = EXCLUDED.target_label_pl,
                        n_obs = EXCLUDED.n_obs,
                        pearson_r = EXCLUDED.pearson_r,
                        pearson_p_value = EXCLUDED.pearson_p_value,
                        granger_f_stat = EXCLUDED.granger_f_stat,
                        granger_p_value = EXCLUDED.granger_p_value,
                        is_significant = EXCLUDED.is_significant,
                        computed_at = now()
                    """,
                    (
                        r["pair_code"], r["leading_label_pl"], r["target_label_pl"], r["lag_months"],
                        r["n_obs"], r["pearson_r"], r["pearson_p_value"], r["granger_f_stat"],
                        r["granger_p_value"], r["is_significant"],
                    ),
                )
        conn.commit()

    print("=== 1. OLS FX REGRESSION (HAC Newey-West) -> mart.analytics_fx_regression ===")
    for r in fx_rows:
        print(
            f"  {r['sector_code']:22s} | {r['target_metric']:18s} | n={r['n_obs']:2d} | "
            f"R2={r['r_squared']:.3f} | b_EUR={r['beta_eur_yoy']:+.3f} (p={r['p_val_eur']:.4f}) | "
            f"b_USD={r['beta_usd_yoy']:+.3f} (p={r['p_val_usd']:.4f})"
        )

    print("\n=== 2. LEAD-LAG & GRANGER CAUSALITY (best lag per pair) -> mart.analytics_lead_lag_granger ===")
    if ll_rows:
        df_ll = pd.DataFrame(ll_rows)
        for pair_code, grp in df_ll.groupby("pair_code"):
            best = grp.loc[grp["pearson_r"].abs().idxmax()]
            sig_g = grp[grp["granger_p_value"].notna() & (grp["granger_p_value"] < 0.05)]
            g_info = (
                f"Granger sig lags={list(sig_g['lag_months'])}"
                if not sig_g.empty
                else "Granger p>=0.05"
            )
            print(
                f"  {pair_code:32s} | best_lag={int(best['lag_months'])}m | "
                f"r={best['pearson_r']:+.3f} (n={int(best['n_obs'])}) | {g_info}"
            )

    print(
        f"\nOK: Upserted {len(fx_rows)} rows into mart.analytics_fx_regression and "
        f"{len(ll_rows)} rows into mart.analytics_lead_lag_granger."
    )


if __name__ == "__main__":
    try:
        run_models()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

