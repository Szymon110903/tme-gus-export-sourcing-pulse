# TME Export & Sourcing Pulse

Automatyczny, produkcyjny potok analityczny (**Python 3.12 w Dockerze + Supabase PostgreSQL 16 + Supabase S3 Storage + Apache Airflow + Power BI / Plotly HTML + Power Automate / Power Apps**) zaprojektowany dla **Transfer Multisort Elektronik (TME)** — globalnego dystrybutora i eksportera komponentów elektronicznych oraz automatyki przemysłowej.

Rozwiązanie łączy oficjalne dane **API DBW GUS** (handel zagraniczny, ceny importu/eksportu wg PKWiU, wolumeny SITC 7, zamówienia eksportowe) z kursami walut **API NBP (EUR/PLN, USD/PLN)**, aby wcześnie wykrywać **presję marżową (*Terms of Trade*)**, **zmiany chłonności rynków eksportowych (UE vs CEE)** oraz **zależność sourcingową od hubów europejskich**.

---

## 1. Kluczowe wyniki empiryczne (szereg czasowy 2019–2026)

Na podstawie rzeczywistych danych GUS DBW i NBP załadowanych do warstwy Gold (`mart.*`) w Supabase (regresja OLS z odpornymi błędami standardowymi **Newey-West HAC** oraz testy korelacji z przesunięciem czasowym i przyczynowości **Grangera**):

- **Asymetryczna transmisja kursu EUR/PLN w elektronice (`PKWiU 26`):**
  - Kursy walut (`EUR/PLN`, `USD/PLN`) wyjaśniają **`R² = 0.737`** zmienności cen importu elektroniki r/r (`β_EUR = +0.584`, `p < 0.0001`, korelacja `r = +0.831` przy opóźnieniu `lag = 0 m`), podczas gdy w cenach eksportu elektroniki dopasowanie wynosi tylko **`R² = 0.312`** (`β_EUR = +0.286`).
  - Przekłada się to na statystycznie istotny **ścisk marżowy (*Terms of Trade*)** przy osłabieniu złotego (`β_EUR = -0.309`, `p = 0.041`).
- **Różnice sektorowe (`PKWiU 28` – Maszyny i automatyka):**
  - W segmencie maszyn/automatyki transmisja kursowa w eksporcie jest znacznie silniejsza (`R² = 0.707`), a wskaźnik *Terms of Trade* pozostaje statystycznie neutralny względem wahań kursu (`p = 0.298`).
- **Kontrola Jakości Danych (DQ Gates):**
  - 7 reguł SQL w [dq_checks.sql](data_quality/dq_checks.sql) (5 `CRITICAL` — 100% `PASS`, 0 błędnych wierszy; automatyczna detekcja rewizji GUS w `staging.etl_revision_audit`).

---

## 2. Architektura danych (Medallion na Supabase Free Tier)

- **Bronze (Supabase Storage – S3, bucket `gus-bronze`):** surowe, skompresowane pliki `.json.gz` w strukturze Hive (`gus_dbw/var={id}/sec={id}/year={y}/period={p}/payload.json.gz`), chroniące przed limitami zapytań GUS DBW.
- **Silver (Supabase PostgreSQL 16 – schematy `ref`, `staging`):** model gwiazdy (*Star Schema*) z tabelą faktów partycjonowaną po roku (`2019–2026`), indeksami częściowymi (`WHERE is_current = true`), pełnym słownikiem `business_code` (zero *magic numbers* w SQL) oraz audytem rewizji GUS (`staging.etl_revision_audit`).
- **Gold (Supabase PostgreSQL 16 – schemat `mart`):**
  - `mart.mv_electronics_terms_of_trade` — sektorowe *Terms of Trade*, `MA3`, `Z-score 36m`, status `pricing_status`,
  - `mart.mv_hub_intermediation_gap` — import wg kraju pochodzenia vs kraju wysyłki (luka pośrednictwa hubów UE),
  - `mart.mv_export_market_pulse` — dynamika wolumenów eksportu/importu SITC 7 (UE vs CEE) + zamówienia zagraniczne,
  - `mart.analytics_fx_regression` oraz `mart.analytics_lead_lag_granger` — gotowe tabele wyników statystycznych do bezpośredniego podpięcia pod **Power BI Desktop / SAP Analytics Cloud**.

### Dokumentacja techniczna
- Model danych i architektura chmurowa (ERD + Medallion): [docs/data_model_and_cloud_storage.md](docs/data_model_and_cloud_storage.md)
- Automatycznie zweryfikowany katalog metadanych GUS DBW: [docs/gus_metadata_catalog.md](docs/gus_metadata_catalog.md)
- Mapowanie na **Power Automate, Power Apps i ekosystem SAP (Datasphere / SAC / AfO / SBPA)**: [docs/power_platform_sap_mapping.md](docs/power_platform_sap_mapping.md)

---

## 3. Szybki start (Docker)

```bash
cp .env.example .env            # uzupełnij DATABASE_URL oraz klucze S3 z Supabase
docker compose build            # buduje obraz Python 3.12 z wszystkimi zależnościami

# 1. Inicjalizacja schematów w Supabase PostgreSQL 16 + test S3
docker compose run --rm etl python -m src.pipelines.init_db

# 2. Synchronizacja słowników GUS i katalog metadanych
docker compose run --rm etl python -m src.pipelines.sync_dictionaries
docker compose run --rm etl python -m src.pipelines.discover_metadata

# 3. Ekstrakcja danych (Bronze S3 -> Silver) i budowa warstwy Gold
docker compose run --rm etl python -m src.pipelines.extract_trade --backfill
docker compose run --rm etl python -m src.pipelines.build_marts

# 4. Data Quality Gates, modele statystyczne, raport HTML i alerting (dry-run)
docker compose run --rm etl python -m src.quality.run_dq
docker compose run --rm etl python -m src.analytics.models_fx_granger
docker compose run --rm etl python -m src.analytics.generate_report
docker compose run --rm etl python -m src.alerting.notify_power_automate --dry-run

# 5. Testy jednostkowe i integracyjne (Supabase)
docker compose run --rm etl pytest -v
```

### Orkiestracja (Apache Airflow)
```bash
docker compose --profile airflow up -d --build
# Panel WWW: http://localhost:8080 (admin / admin)
```
Dostępne DAG-i w [dags/tme_gus_export_sourcing_pulse.py](dags/tme_gus_export_sourcing_pulse.py):
- **`tme_gus_export_sourcing_monthly`** (`0 6 22 * *`) — docelowy potok produkcyjny uruchamiany 22. dnia miesiąca po publikacji biuletynu GUS (`init_db → sync_dictionaries → discover_metadata → extract_recent_window → build_marts → run_dq_gates → run_statistical_models → generate_html_report → notify_power_automate`).
- **`tme_gus_backfill_chunked`** (`*/20 * * * *`, domyślnie zapauzowany) — bezpieczne dociąganie wieloletniej historii z poszanowaniem limitów API GUS.

---

## 4. Struktura repozytorium

```text
├── config/
│   └── trade_series_config.yml         # Centralny rejestr zmiennych, przekrojów i business_code
├── dags/
│   └── tme_gus_export_sourcing_pulse.py # DAG produkcyjny (miesięczny) + DAG backfill
├── data_quality/
│   └── dq_checks.sql                   # 7 reguł jakości danych (CRITICAL / WARN)
├── docs/
│   ├── data_model_and_cloud_storage.md # ERD (Mermaid) + Medallion na Supabase
│   ├── gus_metadata_catalog.md         # Auto-generowany słownik metadanych GUS DBW
│   └── power_platform_sap_mapping.md   # Power Automate, Power Apps i mapowanie na SAP
├── reports/
│   └── tme_export_sourcing_report.html # Interaktywny raport zarządczy (Plotly)
├── sql/
│   ├── 00_schemas_and_dicts.sql        # Schematy ref/staging/mart + wymiary
│   ├── 01_staging_partitioned.sql      # Partycjonowana tabela faktów + audyt rewizji
│   ├── 02_mart_electronics_tot.sql     # Gold: sektorowe Terms of Trade (PKWiU 26–28)
│   ├── 03_mart_hub_intermediation_gap.sql # Gold: luka pośrednictwa hubów UE
│   ├── 04_mart_export_market_pulse.sql # Gold: popyt eksportowy SITC 7 (UE vs CEE)
│   └── 05_mart_analytics_tables.sql    # Gold: tabele wyników OLS HAC i Grangera
├── src/
│   ├── alerting/notify_power_automate.py # Reguły alarmowe + payload Teams Adaptive Card
│   ├── analytics/                      # Modele OLS/Granger + generator raportu HTML
│   ├── clients/                        # Klienci HTTP GUS DBW (retry/throttling) i NBP
│   ├── core/                           # Ustawienia, połączenie PostgreSQL, S3 Bronze
│   ├── pipelines/                      # Init DB, słowniki, ekstraktor, Gold marts
│   └── quality/run_dq.py               # Runner SQL Data Quality Gates
└── tests/                              # Testy jednostkowe i integracyjne (pytest)
```

## Atrybucja danych
*Źródło danych: Główny Urząd Statystyczny – Dziedzinowe Bazy Wiedzy (https://api-dbw.stat.gov.pl/, licencja CC BY 4.0) oraz Narodowy Bank Polski (https://api.nbp.pl/).*
