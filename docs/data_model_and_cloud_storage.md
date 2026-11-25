# Model danych (Star Schema) i architektura chmurowa (Supabase Free Tier)

Ten dokument opisuje, jak ułożone są dane z **API DBW GUS** oraz **API NBP** w uniwersalnym modelu gwiazdy oraz jak działają w chmurze na bazie **Supabase Free Tier** (chmurowy **PostgreSQL 16** + **S3-compatible Storage** w jednym darmowym projekcie).

---

## 1. Graf modelu danych (Model Gwiazdy – Star Schema)

W API DBW GUS główna tabela z danymi liczbowymi (`FACT_DBW_OBSERVATION`) nie zawiera nazw tekstowych — przechowuje wyłącznie klucze obce (`id_*`), które łączą się ze słownikami wymiarów (`DIM_*`). Ten sam schemat obsługuje **wszystkie** zmienne i sektory w GUS DBW (handel zagraniczny, przemysł, budownictwo, energetykę, B+R) bez dodawania nowych tabel faktów.

```mermaid
erDiagram
    FACT_DBW_OBSERVATION {
        int id_zmienna FK
        int id_przekroj FK
        date period_date FK
        int id_okres FK
        bigint id_pozycja_1 FK
        bigint id_pozycja_2 FK
        bigint id_pozycja_3 FK
        bigint id_pozycja_4 FK
        int id_miara FK
        int id_flaga FK
        numeric wartosc
        timestamptz load_ts
        boolean is_current
    }

    DIM_VARIABLE {
        int id_zmienna PK
        int id_obszaru
        text nazwa_zmienna
        text obszar_tematyczny
    }

    DIM_PERIOD {
        int id_okres PK
        varchar symbol
        varchar nazwa_typ
        int month_num
        boolean is_cumulative
    }

    DIM_POSITION {
        int id_przekroj PK
        int id_wymiar PK
        bigint id_pozycja PK
        text nazwa_wymiar
        text nazwa_pozycja
        varchar business_code
    }

    DIM_MEASURE {
        int id_miara PK
        text nazwa_miary
        varchar jednostka
        text sposob_prezentacji
    }

    DIM_FLAG {
        int id_flaga PK
        varchar oznaczenie
        text opis_flagi
    }

    DIM_DATE {
        date period_date PK
        int year
        int quarter
        int month
    }

    FACT_NBP_FX {
        date period_date FK
        varchar currency_code PK
        numeric rate_avg
        numeric rate_stddev
        numeric rate_yoy_pct
    }

    DIM_VARIABLE ||--o{ FACT_DBW_OBSERVATION : "zmienna (np. 329, 227, 221)"
    DIM_PERIOD   ||--o{ FACT_DBW_OBSERVATION : "okres (M01..M12 lub narastajaco)"
    DIM_DATE     ||--o{ FACT_DBW_OBSERVATION : "os czasu"
    DIM_POSITION ||--o{ FACT_DBW_OBSERVATION : "wymiary (PKWiU, SITC, UE/CEE)"
    DIM_MEASURE  ||--o{ FACT_DBW_OBSERVATION : "jednostka (PLN, EUR, kg, r/r=100)"
    DIM_FLAG     ||--o{ FACT_DBW_OBSERVATION : "status rewizji (wstepne/skorygowane)"
    DIM_DATE     ||--o{ FACT_NBP_FX          : "kursy miesieczne USD i EUR"
```

---

## 2. Architektura chmurowa Medallion na Supabase (Bronze → Silver → Gold)

Dane przepływają przez 3 warstwy w jednym projekcie **Supabase**:

```mermaid
flowchart LR
    subgraph EXT["Zrodla zewnetrzne (limity API)"]
        GUS["GUS API DBW (JSON)"]
        NBP["NBP API (JSON)"]
    end

    subgraph BRONZE["BRONZE - Supabase Storage (S3, bucket: gus-bronze)"]
        B1["gus_dbw/var={id}/sec={id}/year={y}/period={p}/payload.json.gz"]
        B2["gus_dbw/dictionaries/{dict}/latest.json.gz"]
        B3["nbp/currency={cur}/year={y}/rates.json.gz"]
    end

    subgraph SILVER["SILVER - Supabase PostgreSQL 16 (schematy: ref, staging)"]
        S1["staging.fact_dbw_observation (partycjonowana po roku + rewizje)"]
        S2["ref.dim_variable, dim_period, dim_position, dim_measure, dim_flag"]
        S3["staging.fact_nbp_fx"]
    end

    subgraph GOLD["GOLD - Supabase PostgreSQL 16 (schemat: mart)"]
        G1["Domena 1 (TME): Handel Zagraniczny (ToT PKWiU 26-28, SITC 7, Hub Gap)"]
        G2["Domena 2 (skalowalna): Przemysl i Koniunktura (PKD 26-28)"]
        G3["Domena 3 (skalowalna): Inne sektory GUS (nowy wpis w YAML)"]
    end

    subgraph CONS["Odbiorcy i Automatyzacja"]
        BI["Raport HTML/XLSX / Power BI (docelowo SAP Analytics Cloud)"]
        AL["Power Automate + Power Apps (docelowo SAP BPA)"]
    end

    GUS -->|"pobierane RAZ"| B1
    GUS -->|"sync slownikow"| B2
    NBP --> B3
    B1 --> S1
    B2 --> S2
    B3 --> S3
    S1 --> G1
    S2 --> G1
    S3 --> G1
    S1 -. "te same tabele, nowy wpis w YAML" .-> G2
    S1 -. "te same tabele, nowy wpis w YAML" .-> G3
    G1 --> BI
    G1 --> AL
```

### Jak ta architektura chroni przed limitami i zapewnia skalowalność?
1. **Brak marnowania limitów API GUS:** Ekstraktor przed wywołaniem GUS sprawdza, czy dany plik istnieje już w buckecie `gus-bronze` w **Supabase Storage**. Historyczne lata (`2019–2024`) pobierane są **dokładnie raz**. Przy cyklicznym odświeżaniu pobierany jest tylko najnowszy miesiąc oraz ostatnie 3 miesiące (z uwagi na rewizje danych wstępnych Intrastat, `id_flaga = 31 → 32`).
2. **Skalowalność na inne sektory GUS:** Dodanie nowego obszaru (np. *Koniunktury PKD 26/27/28*, *Budownictwa* czy *B+R*) polega wyłącznie na dopisaniu nowego bloku w [trade_series_config.yml](../config/trade_series_config.yml) i utworzeniu widoku biznesowego w schemacie `mart`. Warstwy **Bronze** (Supabase Storage) i **Silver** (`ref.*`, `staging.*`) działają bez żadnych zmian w schemacie.

---

## 3. Uzasadnienie wyboru technologii i mapowanie na środowisko TME (SAP)

- **Dlaczego Supabase Free Tier (PostgreSQL 16 + S3 Storage)?**
  - **Koszt 0 zł i brak karty kredytowej:** jedno darmowe konto daje **500 MB** zarządzanego **PostgreSQL 16** (cała historia 2019–2026 zajmuje <15 MB) oraz **1 GB** obiektowego **Storage zgodnego z S3** na warstwę Bronze.
  - **Łatwa prezentacja i audyt:** wbudowany panel webowy (*Storage Browser*, *Table Editor*, *SQL Editor*) pozwala na żywo pokazać surowe pliki z GUS, strukturę gwiazdy i wyniki zapytań SQL z dowolnego komputera.
  - **Brak vendor lock-in:** cały kod korzysta wyłącznie ze standardowych protokołów (**PostgreSQL / SQLAlchemy** oraz **S3 / boto3**).

- **Mapowanie na docelowy stack produkcyjny w TME:**

| Warstwa w projekcie (MVP) | Docelowy odpowiednik w środowisku TME |
|---|---|
| **Supabase Storage (S3)** – warstwa `Bronze` | **Azure Data Lake Storage Gen2 / Azure Blob** |
| **Supabase PostgreSQL 16** – warstwy `Silver` (`ref`, `staging`) i `Gold` (`mart`) | **SAP HANA / SAP Datasphere** |
| **Raport HTML/XLSX / Power BI** | **SAP Analytics Cloud (SAC)** + **Analysis for Office** |
| **Apache Airflow** | **Apache Airflow** |
| **Microsoft Power Automate + Power Apps** | **Power Automate**, **Power Apps** oraz **SAP Build Process Automation** |

---

## 4. Konfiguracja Supabase (2 minuty)

1. Utwórz darmowy projekt na https://supabase.com/ (region np. *Central EU – Frankfurt*).
2. W **Project Settings → Database → Connection string** skopiuj adres PostgreSQL (URI, tryb *Session pooler* lub *Direct*) i wklej jako `DATABASE_URL` w pliku `.env`.
3. W **Storage → New bucket** utwórz prywatny bucket o nazwie **`gus-bronze`**.
4. W **Project Settings → Storage → S3 Access Keys** wygeneruj parę kluczy (`Access Key ID` i `Secret Access Key`) oraz skopiuj `Endpoint` i `Region` do `.env`.
