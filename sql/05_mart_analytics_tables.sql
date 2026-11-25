-- 05_mart_analytics_tables.sql
-- Warstwa GOLD (BI-ready): Tabele wyników analizy statystycznej (regresja FX oraz korelacje lead-lag + test Grangera)
-- Gotowe do bezpośredniego podpięcia w Power BI / SAP Analytics Cloud.

CREATE TABLE IF NOT EXISTS mart.analytics_fx_regression (
    sector_code        varchar(64)    NOT NULL,
    sector_name_pl     text           NOT NULL,
    target_metric      varchar(32)    NOT NULL,
    n_obs              int            NOT NULL,
    r_squared          numeric(8,4),
    adj_r_squared      numeric(8,4),
    beta_eur_yoy       numeric(10,4),
    p_val_eur          numeric(10,6),
    beta_usd_yoy       numeric(10,4),
    p_val_usd          numeric(10,6),
    f_pvalue           numeric(10,6),
    interpretation_pl  text,
    computed_at        timestamptz    NOT NULL DEFAULT now(),
    PRIMARY KEY (sector_code, target_metric)
);

CREATE TABLE IF NOT EXISTS mart.analytics_lead_lag_granger (
    pair_code          varchar(64)    NOT NULL,
    leading_label_pl   text           NOT NULL,
    target_label_pl    text           NOT NULL,
    lag_months         int            NOT NULL CHECK (lag_months BETWEEN 0 AND 12),
    n_obs              int            NOT NULL,
    pearson_r          numeric(8,4),
    pearson_p_value    numeric(10,6),
    granger_f_stat     numeric(10,4),
    granger_p_value    numeric(10,6),
    is_significant     boolean        NOT NULL DEFAULT false,
    computed_at        timestamptz    NOT NULL DEFAULT now(),
    PRIMARY KEY (pair_code, lag_months)
);

