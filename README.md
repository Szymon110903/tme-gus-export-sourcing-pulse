# TME Export & Sourcing Pulse

Automatyczny potok analityczny (**Python 3.12 w Dockerze + Supabase PostgreSQL 16 + Supabase S3 Storage + Apache Airflow + Power Automate / Power Apps**) monitorujący handel zagraniczny i presję marżową w branży elektronicznej dla **Transfer Multisort Elektronik (TME)** w oparciu o oficjalne **API DBW GUS** oraz **API NBP**.

## Architektura danych (Medallion na Supabase Free Tier)
- **Bronze (Supabase Storage – S3, bucket `gus-bronze`):** surowe, skompresowane pliki `.json.gz` pobierane z GUS DBW i NBP tylko raz dla okresów historycznych (ochrona przed limitami API).
- **Silver (Supabase PostgreSQL 16 – schematy `ref`, `staging`):** uniwersalny model gwiazdy (*Star Schema*) z partycjonowaną tabelą faktów, słownikami GUS oraz wersjonowaniem rewizji Intrastat (`id_flaga`, `is_current`).
- **Gold (Supabase PostgreSQL 16 – schemat `mart`):** widoki analityczne i zmaterializowane tabele dla BI oraz systemu alertów.

Szczegółowe diagramy modelu gwiazdy i przepływu danych: [docs/data_model_and_cloud_storage.md](docs/data_model_and_cloud_storage.md).

## Szybki start (wydzielone środowisko w Dockerze)
```bash
cp .env.example .env            # uzupełnij DATABASE_URL oraz klucze S3 z Supabase
docker compose build            # buduje obraz Python 3.12 z wszystkimi zależnościami

# Krok 1: Inicjalizacja schematów w Supabase PostgreSQL 16 + test połączenia z S3
docker compose run --rm etl python -m src.db_init

# Krok 2: Synchronizacja słowników GUS i wygenerowanie katalogu metadanych
docker compose run --rm etl python -m src.sync_dictionaries
docker compose run --rm etl python -m src.discover_metadata

# Krok 3: Pobranie historii 2019-2026 (Bronze S3 -> Silver -> Gold)
docker compose run --rm etl python -m src.extract_trade --backfill

# Krok 4: Analiza statystyczna, raport HTML/XLSX i testy
docker compose run --rm etl python -m src.models_fx_granger
docker compose run --rm etl python -m src.generate_report
docker compose run --rm etl pytest -v
```

## Atrybucja danych
*Źródło danych: Główny Urząd Statystyczny – Dziedzinowe Bazy Wiedzy (https://api-dbw.stat.gov.pl/, licencja CC BY 4.0) oraz Narodowy Bank Polski (https://api.nbp.pl/).*
