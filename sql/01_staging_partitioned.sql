-- 01_staging_partitioned.sql
-- Uniwersalna, partycjonowana tabela faktów GUS DBW (Silver), tabela kursów NBP oraz audyt rewizji.

CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation (
    id_zmienna      int            NOT NULL,
    id_przekroj     int            NOT NULL,
    period_date     date           NOT NULL,
    id_okres        int            NOT NULL,
    id_pozycja_1    bigint         NOT NULL DEFAULT 0,
    id_pozycja_2    bigint         NOT NULL DEFAULT 0,
    id_pozycja_3    bigint         NOT NULL DEFAULT 0,
    id_pozycja_4    bigint         NOT NULL DEFAULT 0,
    id_miara        int            NOT NULL,
    id_flaga        int,
    wartosc         numeric(20,5)  NOT NULL,
    bronze_key      text,
    load_ts         timestamptz    NOT NULL DEFAULT now(),
    is_current      boolean        NOT NULL DEFAULT true,
    PRIMARY KEY (
        id_zmienna, id_przekroj, period_date, id_okres,
        id_pozycja_1, id_pozycja_2, id_pozycja_3, id_pozycja_4,
        id_miara, load_ts
    )
) PARTITION BY RANGE (period_date);

-- Partycje roczne 2019-2026 + partycja domyślna dla przyszłych lat
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2019
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2020
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2021
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2022
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2023
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2024
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2025
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_2026
    PARTITION OF staging.fact_dbw_observation FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE IF NOT EXISTS staging.fact_dbw_observation_default
    PARTITION OF staging.fact_dbw_observation DEFAULT;

-- Indeks złożony częściowy przyspieszający zapytania na aktywnej wersji danych
CREATE INDEX IF NOT EXISTS idx_fact_dbw_current_lookup
    ON staging.fact_dbw_observation (id_zmienna, id_przekroj, id_pozycja_2, id_pozycja_3, id_miara, period_date)
    INCLUDE (id_pozycja_4, wartosc, id_flaga)
    WHERE is_current = true;

-- Audyt rewizji danych wstępnych GUS (Intrastat / Extrastat)
CREATE TABLE IF NOT EXISTS staging.etl_revision_audit (
    audit_id        bigserial      PRIMARY KEY,
    id_zmienna      int            NOT NULL,
    id_przekroj     int            NOT NULL,
    period_date     date           NOT NULL,
    id_okres        int            NOT NULL,
    id_pozycja_2    bigint,
    id_pozycja_3    bigint,
    id_miara        int            NOT NULL,
    old_value       numeric(20,5),
    new_value       numeric(20,5)  NOT NULL,
    old_flaga       int,
    new_flaga       int,
    pct_diff        numeric(10,4),
    detected_at     timestamptz    NOT NULL DEFAULT now()
);

-- Tabela faktów kursów walut z API NBP (agregacja miesięczna)
CREATE TABLE IF NOT EXISTS staging.fact_nbp_fx (
    period_date     date           NOT NULL REFERENCES ref.dim_date(period_date),
    currency_code   varchar(3)     NOT NULL,
    rate_avg        numeric(12,6)  NOT NULL,
    rate_min        numeric(12,6)  NOT NULL,
    rate_max        numeric(12,6)  NOT NULL,
    rate_stddev     numeric(12,6),
    obs_days        int            NOT NULL,
    bronze_key      text,
    updated_at      timestamptz    NOT NULL DEFAULT now(),
    PRIMARY KEY (period_date, currency_code)
);

