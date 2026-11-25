# TME Export & Sourcing Pulse

Automatyczny potok analityczny (Python + PostgreSQL 16 + Apache Airflow + Power Automate / Power Apps) monitorujący handel zagraniczny i presję marżową w branży elektronicznej dla **Transfer Multisort Elektronik (TME)** w oparciu o oficjalne **API DBW GUS** oraz **API NBP**.

## Główne obszary analizy
1. **Sektorowe *Terms of Trade* elektroniki (`PKWiU 26, 27, 28`)** — relacja miesięcznych wskaźników cen eksportu i importu (`id-zmienna=329, id-przekroj=772`) oraz wrażliwość na kursy `EUR/PLN` i `USD/PLN` (API NBP).
2. **Chłonność rynków eksportowych (`UE` vs `CEE`, sekcja `SITC 7`)** — fizyczny wolumen eksportu i importu maszyn i urządzeń (`id-zmienna=227, 228, id-przekroj=789`) zestawiony z nowymi zamówieniami niekrajowymi (`id-zmienna=815, id-przekroj=828`).
3. **Luka pośrednictwa hubów europejskich** — porównanie importu wg *kraju pochodzenia* (`id-zmienna=221`) oraz *kraju wysyłki* (`id-zmienna=222`) dla krajów rozwijających się i UE (`id-przekroj=1144`).

## Szybki start (po konfiguracji środowiska)
```bash
cp .env.example .env
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d
```

## Atrybucja danych
*Źródło danych: Główny Urząd Statystyczny – Dziedzinowe Bazy Wiedzy (`https://api-dbw.stat.gov.pl/`, licencja CC BY 4.0) oraz Narodowy Bank Polski (`https://api.nbp.pl/`).*
