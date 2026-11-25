# Katalog metadanych GUS DBW (wygenerowany automatycznie)

> **Ostatnia weryfikacja względem API DBW GUS:** `2026-11-25 15:46 UTC`  
> **Źródłowy adres bazowy:** `https://api-dbw.stat.gov.pl/api/1.1.0`  
> **Skrypt generujący:** `python -m src.pipelines.discover_metadata` (na podstawie tabel `ref.*` w Supabase PostgreSQL 16).

Ten dokument stanowi audytowalny dowód pochodzenia każdego identyfikatora użytego w `config/trade_series_config.yml`.

---

## 1. Rozwiązane okresy (`ref.dim_period` ← `/dictionaries/periods-dictionary`)

| `id_okres` | Symbol | Typ okresu | Miesiąc (`month_num`) | Tryb | Oficjalny opis GUS |
|---:|---|---|---:|---|---|
| `247` | `M01` | dane miesięczne | 1 | `monthly` | miesiąc - dane miesięczne - styczeń |
| `248` | `M02` | dane miesięczne | 2 | `monthly` | miesiąc - dane miesięczne - luty |
| `249` | `M03` | dane miesięczne | 3 | `monthly` | miesiąc - dane miesięczne - marzec |
| `250` | `M04` | dane miesięczne | 4 | `monthly` | miesiąc - dane miesięczne - kwiecień |
| `251` | `M05` | dane miesięczne | 5 | `monthly` | miesiąc - dane miesięczne - maj |
| `252` | `M06` | dane miesięczne | 6 | `monthly` | miesiąc - dane miesięczne - czerwiec |
| `253` | `M07` | dane miesięczne | 7 | `monthly` | miesiąc - dane miesięczne - lipiec |
| `254` | `M08` | dane miesięczne | 8 | `monthly` | miesiąc - dane miesięczne - sierpień |
| `255` | `M09` | dane miesięczne | 9 | `monthly` | miesiąc - dane miesięczne - wrzesień |
| `256` | `M10` | dane miesięczne | 10 | `monthly` | miesiąc - dane miesięczne - październik |
| `257` | `M11` | dane miesięczne | 11 | `monthly` | miesiąc - dane miesięczne - listopad |
| `258` | `M12` | dane miesięczne | 12 | `monthly` | miesiąc - dane miesięczne - grudzień |
| `259` | `M01-02` | dane narastające | 2 | `cumulative` | miesiąc - dane narastające - styczeń - luty |
| `260` | `M01-03` | dane narastające | 3 | `cumulative` | miesiąc - dane narastające - styczeń - marzec |
| `261` | `M01-04` | dane narastające | 4 | `cumulative` | miesiąc - dane narastające - styczeń - kwiecień |
| `262` | `M01-05` | dane narastające | 5 | `cumulative` | miesiąc - dane narastające - styczeń - maj |
| `263` | `M01-06` | dane narastające | 6 | `cumulative` | miesiąc - dane narastające - styczeń - czerwiec |
| `264` | `M01-07` | dane narastające | 7 | `cumulative` | miesiąc - dane narastające - styczeń - lipiec |
| `265` | `M01-08` | dane narastające | 8 | `cumulative` | miesiąc - dane narastające - styczeń - sierpień |
| `266` | `M01-09` | dane narastające | 9 | `cumulative` | miesiąc - dane narastające - styczeń - wrzesień |
| `267` | `M01-10` | dane narastające | 10 | `cumulative` | miesiąc - dane narastające - styczeń - październik |
| `268` | `M01-11` | dane narastające | 11 | `cumulative` | miesiąc - dane narastające - styczeń - listopad |
| `269` | `M01-12` | dane narastające | 12 | `cumulative` | miesiąc - dane narastające - styczeń - grudzień |

---

## 2. Zweryfikowane zbiory, pozycje i miary (`config/trade_series_config.yml`)

### `PRICE_IMP_EXP_PKWIU` — Wskaźniki cen importu i eksportu
- **Obszar GUS:** Ceny w handlu zagranicznym · **`id_zmienna`:** `329` · **`id_przekroj`:** `772` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=772&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`direction_dim2`) | `4768413` | `IMPORT` | Import/Eksport: import |
| Pozycja (`direction_dim2`) | `4768414` | `EXPORT` | Import/Eksport: eksport |
| Pozycja (`pkwiu_dim3`) | `5665591` | `PKWiU_26_ELEKTRONIKA` | PKWiU_B-D: 26 - KOMPUTERY, WYROBY ELEKTRONICZNE I OPTYCZNE |
| Pozycja (`pkwiu_dim3`) | `5665642` | `PKWiU_27_ELEKTRYKA` | PKWiU_B-D: 27 - URZĄDZENIA ELEKTRYCZNE |
| Pozycja (`pkwiu_dim3`) | `5665823` | `PKWiU_28_MASZYNY` | PKWiU_B-D: 28 - MASZYNY I URZĄDZENIA, GDZIE INDZIEJ NIESKLASYFIKOWANE |
| Pozycja (`pkwiu_dim3`) | `7124459` | `PKWiU_05_32_OGOLEM` | PKWiU_B-D: GR155939 - Wyroby przemysłowe ogółem (działy 05-32) |
| Miara | `5` | `YOY_100` | analogiczny okres roku poprzedniego=100 [-] [bezwymiarowy] |
| Miara | `2` | `MOM_100` | okres poprzedni=100 [-] [bezwymiarowy] |

### `VOL_EXP_SITC7` — Wskaźnik wolumenu w obrotach handlu zagranicznego w eksporcie
- **Obszar GUS:** Obroty towarowe · **`id_zmienna`:** `227` · **`id_przekroj`:** `789` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=789&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`market_dim2`) | `4768396` | `TOTAL` | Kraje: Ogółem |
| Pozycja (`market_dim2`) | `4768398` | `EU` | Kraje: kraje Unii Europejskiej |
| Pozycja (`market_dim2`) | `4768400` | `CEE` | Kraje: kraje Europy Środkowo-Wschodniej |
| Pozycja (`sitc_dim3`) | `720160` | `SITC_7_MACHINERY_EQUIPMENT` | Sekcja SITC: 7 - Maszyny, urządzenia i sprzęt transportowy |
| Pozycja (`sitc_dim3`) | `6618001` | `SITC_TOTAL` | Sekcja SITC: GR272102 - Ogółem |
| Miara | `5` | `YOY_100_CONST` | analogiczny okres roku poprzedniego=100 [-] [bezwymiarowy] |

### `VOL_IMP_SITC7` — Wskaźnik wolumenu w obrotach handlu zagranicznego w imporcie
- **Obszar GUS:** Obroty towarowe · **`id_zmienna`:** `228` · **`id_przekroj`:** `789` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=789&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`market_dim2`) | `4768396` | `TOTAL` | Kraje: Ogółem |
| Pozycja (`market_dim2`) | `4768398` | `EU` | Kraje: kraje Unii Europejskiej |
| Pozycja (`market_dim2`) | `4768400` | `CEE` | Kraje: kraje Europy Środkowo-Wschodniej |
| Pozycja (`sitc_dim3`) | `720160` | `SITC_7_MACHINERY_EQUIPMENT` | Sekcja SITC: 7 - Maszyny, urządzenia i sprzęt transportowy |
| Pozycja (`sitc_dim3`) | `6618001` | `SITC_TOTAL` | Sekcja SITC: GR272102 - Ogółem |
| Miara | `5` | `YOY_100_CONST` | analogiczny okres roku poprzedniego=100 [-] [bezwymiarowy] |

### `TOT_SITC7` — Wskaźniki cen transakcyjnych w handlu zagranicznym
- **Obszar GUS:** Ceny w handlu zagranicznym · **`id_zmienna`:** `328` · **`id_przekroj`:** `773` · **Tryb okresów:** `cumulative`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=773&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`direction_dim2`) | `4768413` | `IMPORT` | Import/Eksport/Terms of trade: import |
| Pozycja (`direction_dim2`) | `4768414` | `EXPORT` | Import/Eksport/Terms of trade: eksport |
| Pozycja (`direction_dim2`) | `4768415` | `TERMS_OF_TRADE` | Import/Eksport/Terms of trade: terms of trade |
| Pozycja (`market_dim3`) | `4768396` | `TOTAL` | Kraje: Ogółem |
| Pozycja (`market_dim3`) | `4768398` | `EU` | Kraje: kraje Unii Europejskiej |
| Pozycja (`market_dim3`) | `4768400` | `CEE` | Kraje: kraje Europy Środkowo-Wschodniej |
| Pozycja (`sitc_dim4`) | `720160` | `SITC_7_MACHINERY_EQUIPMENT` | Sekcja SITC: 7 - Maszyny, urządzenia i sprzęt transportowy |

### `EXPORT_GROUPS` — Eksport towarów
- **Obszar GUS:** Obroty towarowe · **`id_zmienna`:** `220` · **`id_przekroj`:** `1144` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=1144&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`group_dim2`) | `7556586` | `EU` | Ugrupowania: Unia Europejska |
| Pozycja (`group_dim2`) | `7557142` | `EUROZONE` | Ugrupowania: strefa EURO |
| Pozycja (`group_dim2`) | `7276959` | `CEE` | Ugrupowania: Kraje Europy Środkowo-Wschodniej |
| Pozycja (`group_dim2`) | `7557771` | `DEVELOPING_ASIA_LATAM` | Ugrupowania: Kraje rozwijające się |
| Pozycja (`group_dim2`) | `7557722` | `DEVELOPED` | Ugrupowania: Kraje rozwinięte |
| Miara | `180` | `VALUE_PLN` | [zł] [zł] |
| Miara | `314` | `VALUE_EUR` | [EUR] [EUR] |
| Miara | `315` | `VALUE_USD` | [USD] [USD] |
| Miara | `277` | `MASS_KG` | [kg] [kg] |
| Miara | `99` | `SHARE_PCT` | udział w pozycji ogółem [%] [%] |
| Miara | `6` | `YOY_PLN_100` | analogiczny okres roku poprzedniego=100  [-] [bezwymiarowy] |

### `IMPORT_ORIGIN_GROUPS` — Import towarów wg kraju pochodzenia
- **Obszar GUS:** Obroty towarowe · **`id_zmienna`:** `221` · **`id_przekroj`:** `1144` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=1144&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`group_dim2`) | `7556586` | `EU` | Ugrupowania: Unia Europejska |
| Pozycja (`group_dim2`) | `7557142` | `EUROZONE` | Ugrupowania: strefa EURO |
| Pozycja (`group_dim2`) | `7276959` | `CEE` | Ugrupowania: Kraje Europy Środkowo-Wschodniej |
| Pozycja (`group_dim2`) | `7557771` | `DEVELOPING_ASIA_LATAM` | Ugrupowania: Kraje rozwijające się |
| Pozycja (`group_dim2`) | `7557722` | `DEVELOPED` | Ugrupowania: Kraje rozwinięte |
| Miara | `180` | `VALUE_PLN` | [zł] [zł] |
| Miara | `314` | `VALUE_EUR` | [EUR] [EUR] |
| Miara | `315` | `VALUE_USD` | [USD] [USD] |
| Miara | `277` | `MASS_KG` | [kg] [kg] |
| Miara | `99` | `SHARE_PCT` | udział w pozycji ogółem [%] [%] |
| Miara | `6` | `YOY_PLN_100` | analogiczny okres roku poprzedniego=100  [-] [bezwymiarowy] |

### `IMPORT_CONSIGNMENT_GROUPS` — Import towarów wg kraju wysyłki
- **Obszar GUS:** Obroty towarowe · **`id_zmienna`:** `222` · **`id_przekroj`:** `1144` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=1144&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`group_dim2`) | `7556586` | `EU` | Ugrupowania: Unia Europejska |
| Pozycja (`group_dim2`) | `7557142` | `EUROZONE` | Ugrupowania: strefa EURO |
| Pozycja (`group_dim2`) | `7276959` | `CEE` | Ugrupowania: Kraje Europy Środkowo-Wschodniej |
| Pozycja (`group_dim2`) | `7557771` | `DEVELOPING_ASIA_LATAM` | Ugrupowania: Kraje rozwijające się |
| Pozycja (`group_dim2`) | `7557722` | `DEVELOPED` | Ugrupowania: Kraje rozwinięte |
| Miara | `180` | `VALUE_PLN` | [zł] [zł] |
| Miara | `314` | `VALUE_EUR` | [EUR] [EUR] |
| Miara | `315` | `VALUE_USD` | [USD] [USD] |
| Miara | `277` | `MASS_KG` | [kg] [kg] |
| Miara | `99` | `SHARE_PCT` | udział w pozycji ogółem [%] [%] |
| Miara | `6` | `YOY_PLN_100` | analogiczny okres roku poprzedniego=100  [-] [bezwymiarowy] |

### `NEW_ORDERS_FOREIGN` — Nowe zamówienia w przemyśle
- **Obszar GUS:** Przemysł · **`id_zmienna`:** `815` · **`id_przekroj`:** `828` · **Tryb okresów:** `monthly`
- **Endpoint pozycji:** `https://api-dbw.stat.gov.pl/api/1.1.0/variable/variable-section-position?id-przekroj=828&lang=pl`

| Typ | ID w GUS | Nasz kod biznesowy | Oficjalna nazwa w słowniku GUS |
|---|---:|---|---|
| Pozycja (`order_type_dim2`) | `7232806` | `TOTAL` | Rodzaje nowych zamówień w przemyśle: Ogółem |
| Pozycja (`order_type_dim2`) | `7232807` | `FOREIGN_EXPORT` | Rodzaje nowych zamówień w przemyśle: Niekrajowe |
| Miara | `6` | `YOY_100` | analogiczny okres roku poprzedniego=100  [-] [bezwymiarowy] |
| Miara | `3` | `MOM_100` | okres poprzedni=100  [-] [bezwymiarowy] |
| Miara | `357` | `BASE_2021_100` | przeciętna miesięczna 2021=100 ceny stałe [-] [bezwymiarowy] |
