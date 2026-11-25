-- dq_checks.sql
-- Bramki jakości danych (Data Quality Gates) dla warstw Silver (ref, staging) i Gold (mart).
-- Każde zapytanie zwraca jednolity kontrakt: (check_name, severity, failed_rows, details).

WITH checks AS (
    -- DQ1: Brak duplikatów aktywnych wersji w tabeli faktów Silver
    SELECT
        'no_duplicate_current_observations'::text AS check_name,
        'CRITICAL'::text                          AS severity,
        COUNT(*)::int                             AS failed_rows,
        'Duplikaty klucza biznesowego z is_current = true w staging.fact_dbw_observation'::text AS details
    FROM (
        SELECT
            id_zmienna, id_przekroj, period_date, id_okres,
            id_pozycja_1, id_pozycja_2, id_pozycja_3, id_pozycja_4, id_miara
        FROM staging.fact_dbw_observation
        WHERE is_current = true
        GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
        HAVING COUNT(*) > 1
    ) dup

    UNION ALL

    -- DQ2: Parzystość par import/eksport w PKWiU (warunek policzenia implied_tot_yoy)
    SELECT
        'pkwiu_import_export_parity',
        'CRITICAL',
        COUNT(*)::int,
        'Wiersze w mart.mv_electronics_terms_of_trade bez pary cen importu i eksportu'
    FROM mart.mv_electronics_terms_of_trade
    WHERE imp_price_yoy_idx IS NULL
       OR exp_price_yoy_idx IS NULL
       OR implied_tot_yoy   IS NULL

    UNION ALL

    -- DQ3: Dodatniość wartości handlowych (PLN, EUR, USD) i masy (kg)
    SELECT
        'positive_trade_values_and_mass',
        'CRITICAL',
        COUNT(*)::int,
        'Niedodatnie wartości eksportu lub masy w mart.mv_hub_intermediation_gap'
    FROM mart.mv_hub_intermediation_gap
    WHERE (export_pln     IS NOT NULL AND export_pln     <= 0)
       OR (export_eur     IS NOT NULL AND export_eur     <= 0)
       OR (export_usd     IS NOT NULL AND export_usd     <= 0)
       OR (export_mass_kg IS NOT NULL AND export_mass_kg <= 0)

    UNION ALL

    -- DQ4: Poprawny zakres kursów walut z API NBP
    SELECT
        'nbp_fx_rates_valid_range',
        'CRITICAL',
        COUNT(*)::int,
        'Kursy EUR/USD w staging.fact_nbp_fx poza zakresem [2.5, 7.0] lub za mało dni sesyjnych (<15)'
    FROM staging.fact_nbp_fx
    WHERE rate_avg < 2.5
       OR rate_avg > 7.0
       OR (obs_days < 15 AND period_date < date_trunc('month', CURRENT_DATE)::date)

    UNION ALL

    -- DQ5: Spójność międzyźródłowa GUS vs NBP (implikowany kurs PLN/EUR z GUS vs średni kurs NBP w tolerancji ±5%)
    SELECT
        'gus_vs_nbp_eur_fx_consistency',
        'WARN',
        COUNT(*)::int,
        'Miesiące z odchyleniem kursu implikowanego GUS (PLN/EUR) względem średniej NBP > 5%'
    FROM mart.mv_hub_intermediation_gap g
    JOIN staging.fact_nbp_fx fx
      ON fx.period_date   = g.period_date
     AND fx.currency_code = 'EUR'
    WHERE g.region_group = 'EU'
      AND g.implied_eur_pln_rate IS NOT NULL
      AND ABS(g.implied_eur_pln_rate - fx.rate_avg) / NULLIF(fx.rate_avg, 0) > 0.05

    UNION ALL

    -- DQ6: Kompletność kodów biznesowych w ref.dim_variable
    SELECT
        'ref_business_codes_complete',
        'CRITICAL',
        CASE WHEN COUNT(*) = 8 THEN 0 ELSE ABS(8 - COUNT(*)) END::int,
        'Oczekiwane dokładnie 8 skonfigurowanych zmiennych z business_code w ref.dim_variable'
    FROM ref.dim_variable
    WHERE business_code IS NOT NULL
      AND id_przekroj   IS NOT NULL

    UNION ALL

    -- DQ7: Audyt istotnych rewizji Intrastat (> 3% zmiany wartości historycznej w ostatnich 30 dniach)
    SELECT
        'large_intrastat_revisions_audit',
        'WARN',
        COUNT(*)::int,
        'Rewizje historycznych danych GUS > 3% wykryte w ostatnich 30 dniach (staging.etl_revision_audit)'
    FROM staging.etl_revision_audit
    WHERE detected_at >= now() - interval '30 days'
      AND ABS(COALESCE(pct_diff, 0)) > 3.0
)
SELECT check_name, severity, failed_rows, details
FROM checks
ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 ELSE 2 END, check_name;

