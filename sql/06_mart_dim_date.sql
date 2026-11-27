-- 06_mart_dim_date.sql
-- Warstwa GOLD: Wymiar kalendarza dla Power BI (1:* do wszystkich widokow mart.mv_*).

CREATE OR REPLACE VIEW mart.dim_date AS
SELECT
    period_date,
    year,
    quarter,
    month,
    year_month,
    (year::text || '-Q' || quarter::text) AS year_quarter,
    CASE month
        WHEN 1  THEN 'Styczeń'
        WHEN 2  THEN 'Luty'
        WHEN 3  THEN 'Marzec'
        WHEN 4  THEN 'Kwiecień'
        WHEN 5  THEN 'Maj'
        WHEN 6  THEN 'Czerwiec'
        WHEN 7  THEN 'Lipiec'
        WHEN 8  THEN 'Sierpień'
        WHEN 9  THEN 'Wrzesień'
        WHEN 10 THEN 'Październik'
        WHEN 11 THEN 'Listopad'
        WHEN 12 THEN 'Grudzień'
    END AS month_name_pl,
    CASE month
        WHEN 1  THEN 'Sty'
        WHEN 2  THEN 'Lut'
        WHEN 3  THEN 'Mar'
        WHEN 4  THEN 'Kwi'
        WHEN 5  THEN 'Maj'
        WHEN 6  THEN 'Cze'
        WHEN 7  THEN 'Lip'
        WHEN 8  THEN 'Sie'
        WHEN 9  THEN 'Wrz'
        WHEN 10 THEN 'Paź'
        WHEN 11 THEN 'Lis'
        WHEN 12 THEN 'Gru'
    END AS month_short_pl
FROM ref.dim_date
WHERE year BETWEEN 2019 AND 2026;

-- Cienkie widoki standardowe (VIEW) dla konektora Power BI PostgreSQL
-- (Power BI Desktop nie importuje bezposrednio MATERIALIZED VIEW z listy Nawigatora).
CREATE OR REPLACE VIEW mart.v_electronics_terms_of_trade AS
SELECT * FROM mart.mv_electronics_terms_of_trade;

CREATE OR REPLACE VIEW mart.v_hub_intermediation_gap AS
SELECT * FROM mart.mv_hub_intermediation_gap;

CREATE OR REPLACE VIEW mart.v_export_market_pulse AS
SELECT * FROM mart.mv_export_market_pulse;


