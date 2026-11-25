-- 03_mart_hub_intermediation_gap.sql
-- Warstwa GOLD: Luka pośrednictwa hubów europejskich (Import wg kraju pochodzenia vs kraju wysyłki + Eksport).
-- Zero magic numbers: wszystkie filtry korzystają z business_code ze słowników ref.*.

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.mv_hub_intermediation_gap AS
WITH flows AS (
    SELECT
        o.period_date,
        o.id_pozycja_2     AS group_pos_id,
        grp.business_code  AS region_group,
        grp.nazwa_pozycja  AS region_name_pl,
        MAX(CASE WHEN v.business_code = 'IMPORT_ORIGIN_GROUPS'      AND m.business_code = 'VALUE_EUR'    THEN o.wartosc END) AS imp_origin_eur,
        MAX(CASE WHEN v.business_code = 'IMPORT_CONSIGNMENT_GROUPS' AND m.business_code = 'VALUE_EUR'    THEN o.wartosc END) AS imp_consign_eur,
        MAX(CASE WHEN v.business_code = 'IMPORT_ORIGIN_GROUPS'      AND m.business_code = 'SHARE_PCT'    THEN o.wartosc END) AS imp_origin_share_pct,
        MAX(CASE WHEN v.business_code = 'IMPORT_CONSIGNMENT_GROUPS' AND m.business_code = 'SHARE_PCT'    THEN o.wartosc END) AS imp_consign_share_pct,
        MAX(CASE WHEN v.business_code = 'EXPORT_GROUPS'             AND m.business_code = 'VALUE_PLN'    THEN o.wartosc END) AS export_pln,
        MAX(CASE WHEN v.business_code = 'EXPORT_GROUPS'             AND m.business_code = 'VALUE_EUR'    THEN o.wartosc END) AS export_eur,
        MAX(CASE WHEN v.business_code = 'EXPORT_GROUPS'             AND m.business_code = 'VALUE_USD'    THEN o.wartosc END) AS export_usd,
        MAX(CASE WHEN v.business_code = 'EXPORT_GROUPS'             AND m.business_code = 'MASS_KG'      THEN o.wartosc END) AS export_mass_kg,
        MAX(CASE WHEN v.business_code = 'EXPORT_GROUPS'             AND m.business_code = 'SHARE_PCT'    THEN o.wartosc END) AS export_share_pct,
        MAX(CASE WHEN v.business_code = 'EXPORT_GROUPS'             AND m.business_code = 'YOY_CURR_100' THEN o.wartosc END) AS export_yoy_pln_idx
    FROM staging.fact_dbw_observation o
    JOIN ref.dim_variable v
      ON v.id_zmienna  = o.id_zmienna
     AND v.id_przekroj = o.id_przekroj
     AND v.business_code IN ('EXPORT_GROUPS', 'IMPORT_ORIGIN_GROUPS', 'IMPORT_CONSIGNMENT_GROUPS')
    JOIN ref.dim_position grp
      ON grp.id_przekroj = o.id_przekroj
     AND grp.id_pozycja  = o.id_pozycja_2
     AND grp.business_code IN ('EU', 'EUROZONE', 'CEE', 'DEVELOPING_ASIA_LATAM', 'DEVELOPED')
    JOIN ref.dim_measure m
      ON m.id_miara = o.id_miara
     AND m.business_code IN ('VALUE_PLN', 'VALUE_EUR', 'VALUE_USD', 'MASS_KG', 'SHARE_PCT', 'YOY_CURR_100')
    WHERE o.is_current = true
    GROUP BY o.period_date, o.id_pozycja_2, grp.business_code, grp.nazwa_pozycja
)
SELECT
    period_date,
    group_pos_id,
    region_group,
    region_name_pl,
    imp_origin_eur,
    imp_consign_eur,
    (imp_consign_eur - imp_origin_eur) AS hub_reexport_balance_eur,
    imp_origin_share_pct,
    imp_consign_share_pct,
    ROUND((imp_consign_share_pct - imp_origin_share_pct)::numeric, 2) AS share_gap_pp,
    ROUND((100.0 * (imp_origin_eur - imp_consign_eur) / NULLIF(imp_origin_eur, 0))::numeric, 2)
        AS indirect_hub_share_pct,
    export_pln,
    export_eur,
    export_usd,
    export_mass_kg,
    export_share_pct,
    ROUND((export_yoy_pln_idx - 100.0)::numeric, 2) AS export_yoy_pln_pct,
    ROUND((export_eur / NULLIF(export_mass_kg, 0))::numeric, 4) AS export_eur_per_kg,
    ROUND((export_pln / NULLIF(export_eur, 0))::numeric, 4) AS implied_eur_pln_rate
FROM flows;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_hub_intermediation_gap
    ON mart.mv_hub_intermediation_gap (group_pos_id, period_date);
