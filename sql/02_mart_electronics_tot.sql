-- 02_mart_electronics_tot.sql
-- Warstwa GOLD: Sektorowe Terms of Trade i presja marżowa w elektronice, elektryce i maszynach (PKWiU 26, 27, 28).
-- Zero magic numbers: wszystkie filtry korzystają z business_code ze słowników ref.* (źródło: config/trade_series_config.yml).

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mv_electronics_terms_of_trade AS
WITH fx_yoy AS (
    SELECT
        period_date,
        MAX(CASE WHEN currency_code = 'EUR' THEN rate_avg END) AS eur_pln_avg,
        MAX(CASE WHEN currency_code = 'USD' THEN rate_avg END) AS usd_pln_avg
    FROM staging.fact_nbp_fx
    GROUP BY period_date
),
fx_features AS (
    SELECT
        period_date,
        eur_pln_avg,
        usd_pln_avg,
        ROUND((100.0 * (eur_pln_avg / NULLIF(LAG(eur_pln_avg, 12) OVER (ORDER BY period_date), 0) - 1))::numeric, 2)
            AS eur_pln_yoy_pct,
        ROUND((100.0 * (usd_pln_avg / NULLIF(LAG(usd_pln_avg, 12) OVER (ORDER BY period_date), 0) - 1))::numeric, 2)
            AS usd_pln_yoy_pct
    FROM fx_yoy
),
prices AS (
    SELECT
        o.period_date,
        o.id_pozycja_3        AS pkwiu_pos_id,
        sec.business_code     AS sector_code,
        sec.nazwa_pozycja     AS sector_name_pl,
        MAX(CASE WHEN dir.business_code = 'IMPORT' AND m.business_code = 'YOY_100' THEN o.wartosc END) AS imp_price_yoy_idx,
        MAX(CASE WHEN dir.business_code = 'EXPORT' AND m.business_code = 'YOY_100' THEN o.wartosc END) AS exp_price_yoy_idx,
        MAX(CASE WHEN dir.business_code = 'IMPORT' AND m.business_code = 'MOM_100' THEN o.wartosc END) AS imp_price_mom_idx,
        MAX(CASE WHEN dir.business_code = 'EXPORT' AND m.business_code = 'MOM_100' THEN o.wartosc END) AS exp_price_mom_idx
    FROM staging.fact_dbw_observation o
    JOIN ref.dim_variable v
      ON v.id_zmienna  = o.id_zmienna
     AND v.id_przekroj = o.id_przekroj
     AND v.business_code = 'PRICE_IMP_EXP_PKWIU'
    JOIN ref.dim_position dir
      ON dir.id_przekroj = o.id_przekroj
     AND dir.id_pozycja  = o.id_pozycja_2
     AND dir.business_code IN ('IMPORT', 'EXPORT')
    JOIN ref.dim_position sec
      ON sec.id_przekroj = o.id_przekroj
     AND sec.id_pozycja  = o.id_pozycja_3
     AND sec.business_code IN ('PKWiU_26_ELEKTRONIKA', 'PKWiU_27_ELEKTRYKA', 'PKWiU_28_MASZYNY', 'PKWiU_05_32_OGOLEM')
    JOIN ref.dim_measure m
      ON m.id_miara = o.id_miara
     AND m.business_code IN ('YOY_100', 'MOM_100')
    WHERE o.is_current = true
    GROUP BY o.period_date, o.id_pozycja_3, sec.business_code, sec.nazwa_pozycja
),
enriched AS (
    SELECT
        p.period_date,
        p.pkwiu_pos_id,
        p.sector_code,
        p.sector_name_pl,
        p.imp_price_yoy_idx,
        p.exp_price_yoy_idx,
        p.imp_price_mom_idx,
        p.exp_price_mom_idx,
        ROUND((100.0 * p.exp_price_yoy_idx / NULLIF(p.imp_price_yoy_idx, 0))::numeric, 2) AS implied_tot_yoy,
        ROUND((p.exp_price_yoy_idx - p.imp_price_yoy_idx)::numeric, 2)                    AS price_spread_pp,
        fx.eur_pln_avg,
        fx.usd_pln_avg,
        fx.eur_pln_yoy_pct,
        fx.usd_pln_yoy_pct
    FROM prices p
    LEFT JOIN fx_features fx
      ON fx.period_date = p.period_date
)
SELECT
    period_date,
    pkwiu_pos_id,
    sector_code,
    sector_name_pl,
    imp_price_yoy_idx,
    exp_price_yoy_idx,
    imp_price_mom_idx,
    exp_price_mom_idx,
    implied_tot_yoy,
    price_spread_pp,
    ROUND(AVG(implied_tot_yoy) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)::numeric, 2) AS tot_ma3,
    ROUND((
        (implied_tot_yoy - AVG(implied_tot_yoy) OVER (w ROWS BETWEEN 35 PRECEDING AND CURRENT ROW))
        / NULLIF(STDDEV_SAMP(implied_tot_yoy) OVER (w ROWS BETWEEN 35 PRECEDING AND CURRENT ROW), 0)
    )::numeric, 2) AS tot_z36,
    eur_pln_avg,
    usd_pln_avg,
    eur_pln_yoy_pct,
    usd_pln_yoy_pct,
    CASE
        WHEN implied_tot_yoy < 97.5 THEN 'MARGIN_SQUEEZE_ALERT'
        WHEN implied_tot_yoy > 102.0 THEN 'MARGIN_TAILWIND'
        ELSE 'NEUTRAL'
    END AS pricing_status
FROM enriched
WINDOW w AS (PARTITION BY pkwiu_pos_id ORDER BY period_date);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_electronics_tot
    ON mart.mv_electronics_terms_of_trade (pkwiu_pos_id, period_date);
