-- 00_schemas_and_dicts.sql
-- Schematy warstw Silver (ref, staging) i Gold (mart) oraz tabele wymiarów (Star Schema).

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

-- 1. Wymiar zmiennych GUS DBW
CREATE TABLE IF NOT EXISTS ref.dim_variable (
    id_zmienna         int          PRIMARY KEY,
    id_obszaru         int,
    nazwa_zmienna      text         NOT NULL,
    obszar_tematyczny  text,
    updated_at         timestamptz  NOT NULL DEFAULT now()
);

-- 2. Wymiar okresów GUS DBW (rozwiązywany dynamicznie z /dictionaries/periods-dictionary)
CREATE TABLE IF NOT EXISTS ref.dim_period (
    id_okres           int          PRIMARY KEY,
    symbol             varchar(32),
    opis               text,
    id_czestotliwosc   int,
    nazwa_czestotliwosc varchar(64),
    id_typ             int,
    nazwa_typ          varchar(64),
    month_num          int          CHECK (month_num IS NULL OR month_num BETWEEN 1 AND 12),
    is_monthly         boolean      NOT NULL DEFAULT false,
    is_cumulative      boolean      NOT NULL DEFAULT false,
    updated_at         timestamptz  NOT NULL DEFAULT now()
);

-- 3. Wymiar pozycji przekrojów GUS DBW (PKWiU, SITC, Ugrupowania, Import/Eksport, itp.)
CREATE TABLE IF NOT EXISTS ref.dim_position (
    id_przekroj        int          NOT NULL,
    id_wymiar          int          NOT NULL,
    id_pozycja         bigint       NOT NULL,
    nazwa_wymiar       text         NOT NULL,
    nazwa_pozycja      text         NOT NULL,
    business_code      varchar(64),
    updated_at         timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (id_przekroj, id_wymiar, id_pozycja)
);

-- 4. Wymiar miar i sposobów prezentacji GUS DBW
CREATE TABLE IF NOT EXISTS ref.dim_measure (
    id_miara           int          PRIMARY KEY,
    nazwa_miary        text         NOT NULL,
    sposob_prezentacji text,
    oznaczenie_jedn    varchar(64),
    nazwa_jedn         varchar(128),
    updated_at         timestamptz  NOT NULL DEFAULT now()
);

-- 5. Wymiar flag jakości i rewizji GUS DBW (np. 31 = dane wstępne, 32 = dane skorygowane)
CREATE TABLE IF NOT EXISTS ref.dim_flag (
    id_flaga           int          PRIMARY KEY,
    oznaczenie         varchar(16),
    opis_flagi         text         NOT NULL,
    updated_at         timestamptz  NOT NULL DEFAULT now()
);

-- 6. Wymiar czasu (kalendarz miesięczny 2018-2027)
CREATE TABLE IF NOT EXISTS ref.dim_date (
    period_date        date         PRIMARY KEY,
    year               int          NOT NULL,
    quarter            int          NOT NULL,
    month              int          NOT NULL,
    year_month         char(7)      NOT NULL
);

INSERT INTO ref.dim_date (period_date, year, quarter, month, year_month)
SELECT
    d::date AS period_date,
    EXTRACT(YEAR FROM d)::int AS year,
    EXTRACT(QUARTER FROM d)::int AS quarter,
    EXTRACT(MONTH FROM d)::int AS month,
    to_char(d, 'YYYY-MM') AS year_month
FROM generate_series('2018-01-01'::date, '2027-12-01'::date, interval '1 month') AS d
ON CONFLICT (period_date) DO NOTHING;

