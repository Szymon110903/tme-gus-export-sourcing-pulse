-- 04_mart_export_market_pulse.sql
-- Warstwa GOLD: Impuls popytu eksportowego wg kierunków (UE vs CEE, Sekcja SITC 7) + nowe zamówienia niekrajowe.
-- Zero magic numbers: wszystkie filtry korzystają z business_code ze słowników ref.*.

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mv_export_market_pulse AS
WITH sitc7_volumes AS (
    SELECT
        o.period_date,
        o.id_pozycja_2     AS market_pos_id,
        mkt.business_code  AS target_market,
        mkt.nazwa_pozycja  AS market_name_pl,
        MAX(CASE WHEN v.business_code = 'VOL_EXP_SITC7' THEN ROUND((o.wartosc - 100.0)::numeric, 2) END)
            AS sitc7_export_vol_yoy_pct,
        MAX(CASE WHEN v.business_code = 'VOL_IMP_SITC7' THEN ROUND((o.wartosc - 100.0)::numeric, 2) END)
            AS sitc7_import_vol_yoy_pct
    FROM staging.fact_dbw_observation o
    JOIN ref.dim_variable v
      ON v.id_zmienna  = o.id_zmienna
     AND v.id_przekroj = o.id_przekroj
     AND v.business_code IN ('VOL_EXP_SITC7', 'VOL_IMP_SITC7')
    JOIN ref.dim_position mkt
      ON mkt.id_przekroj = o.id_przekroj
     AND mkt.id_pozycja  = o.id_pozycja_2
     AND mkt.business_code IN ('TOTAL', 'EU', 'CEE')
    JOIN ref.dim_position sitc
      ON sitc.id_przekroj = o.id_przekroj
     AND sitc.id_pozycja  = o.id_pozycja_3
     AND sitc.business_code = 'SITC_7_MACHINERY_EQUIPMENT'
    JOIN ref.dim_measure m
      ON m.id_miara = o.id_miara
     AND m.business_code = 'YOY_100'
    WHERE o.is_current = true
    GROUP BY o.period_date, o.id_pozycja_2, mkt.business_code, mkt.nazwa_pozycja
),
new_orders AS (
    SELECT
        o.period_date,
        MAX(CASE WHEN ord.business_code = 'FOREIGN_EXPORT' THEN ROUND((o.wartosc - 100.0)::numeric, 2) END)
            AS ind_foreign_new_orders_yoy_pct,
        MAX(CASE WHEN ord.business_code = 'TOTAL'          THEN ROUND((o.wartosc - 100.0)::numeric, 2) END)
            AS ind_total_new_orders_yoy_pct
    FROM staging.fact_dbw_observation o
    JOIN ref.dim_variable v
      ON v.id_zmienna  = o.id_zmienna
     AND v.id_przekroj = o.id_przekroj
     AND v.business_code = 'NEW_ORDERS_FOREIGN'
    JOIN ref.dim_position ord
      ON ord.id_przekroj = o.id_przekroj
     AND ord.id_pozycja  = o.id_pozycja_2
     AND ord.business_code IN ('FOREIGN_EXPORT', 'TOTAL')
    JOIN ref.dim_measure m
      ON m.id_miara = o.id_miara
     AND m.business_code = 'YOY_CURR_100'
    WHERE o.is_current = true
    GROUP BY o.period_date
),
base AS (
    SELECT
        s.period_date,
        s.market_pos_id,
        s.target_market,
        s.market_name_pl,
        s.sitc7_export_vol_yoy_pct,
        s.sitc7_import_vol_yoy_pct,
        n.ind_foreign_new_orders_yoy_pct,
        n.ind_total_new_orders_yoy_pct
    FROM sitc7_volumes s
    LEFT JOIN new_orders n
      ON n.period_date = s.period_date
)
SELECT
    period_date,
    market_pos_id,
    target_market,
    market_name_pl,
    sitc7_export_vol_yoy_pct,
    sitc7_import_vol_yoy_pct,
    ROUND(AVG(sitc7_export_vol_yoy_pct) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)::numeric, 2)
        AS sitc7_export_vol_ma3_pct,
    ind_foreign_new_orders_yoy_pct,
    ind_total_new_orders_yoy_pct,
    ROUND(AVG(ind_foreign_new_orders_yoy_pct) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)::numeric, 2)
        AS ind_foreign_orders_ma3_pct,
    CASE
        WHEN sitc7_export_vol_yoy_pct >= 8.0  THEN 'STRONG_EXPANSION'
        WHEN sitc7_export_vol_yoy_pct >= 2.0  THEN 'GROWTH'
        WHEN sitc7_export_vol_yoy_pct <= -5.0 THEN 'CONTRACTION'
        ELSE 'STAGNATION'
    END AS market_momentum_status
FROM base
WINDOW w AS (PARTITION BY market_pos_id ORDER BY period_date);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_export_market_pulse
    ON mart.mv_export_market_pulse (market_pos_id, period_date);
