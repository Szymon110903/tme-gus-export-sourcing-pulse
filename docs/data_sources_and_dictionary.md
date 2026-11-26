# Źródła danych i znaczenie zbiorów

Zwięzły przegląd pochodzenia danych w projekcie, ich zawartości oraz znaczenia poszczególnych wskaźników.

---

## 1. Skąd pobierane są dane?

Projekt korzysta wyłącznie z **2 oficjalnych, darmowych źródeł publicznych (REST API)**:

| Źródło | Co stamtąd bierzemy | Zakres | Częstotliwość | Licencja |
|---|---|---|---|---|
| **GUS – Dziedzinowe Bazy Wiedzy (DBW)** (`api-dbw.stat.gov.pl`) | 8 zbiorów dot. handlu zagranicznego, cen w handlu i nowych zamówień w przemyśle | `2019–2026` | Miesięczna | CC BY 4.0 |
| **Narodowy Bank Polski (NBP)** (`api.nbp.pl`) | Dzienne kursy średnie **EUR/PLN** i **USD/PLN** (Tabela A), uśredniane do miesięcy | `2018–2026` *(2018 jako rok bazowy dla r/r)* | Dzienna → miesięczna | Dane publiczne |

---

## 2. Co znajduje się w każdym zbiorze i co to oznacza?

### A. Ceny i opłacalność handlu (GUS)

1. **Wskaźniki cen importu i eksportu wg PKWiU** *(miesięczne)*
   - **Co zawiera:** Miesięczną dynamikę cen w imporcie i eksporcie (r/r oraz m/m) dla 3 kluczowych działów przemysłu: **elektronika i optyka (PKWiU 26)**, **urządzenia elektryczne (PKWiU 27)**, **maszyny i urządzenia (PKWiU 28)** oraz dla **przemysłu ogółem (PKWiU 05–32)**.
   - **Co oznacza:** Pokazuje, czy towary z branży elektronicznej i automatyki drożeją czy tanieją w zakupie (import) oraz w sprzedaży za granicę (eksport). Porównanie eksportu do importu pokazuje, czy rynek daje przestrzeń do utrzymania marży (*Terms of Trade*).

2. **Wskaźniki cen transakcyjnych i Terms of Trade – Sekcja SITC 7** *(narastające od początku roku)*
   - **Co zawiera:** Oficjalny wskaźnik cen importu, eksportu oraz gotowy wskaźnik *Terms of Trade* dla maszyn i urządzeń (**SITC 7**) w podziale na kierunki: **Ogółem**, **Unia Europejska (UE)** oraz **Europa Środkowo-Wschodnia (CEE)**.
   - **Co oznacza:** Daje ujęcie narastające (YTD) oraz podział geograficzny — pozwala sprawdzić, czy presja cenowa jest silniejsza w handlu z UE czy z rynkami CEE.

---

### B. Realny popyt i zamówienia (GUS)

3. **Wskaźnik wolumenu eksportu – Sekcja SITC 7** *(miesięczne)*
   - **Co zawiera:** Roczną dynamikę (r/r) **wolumenu** eksportu maszyn, urządzeń i sprzętu transportowego (**SITC 7**) oraz eksportu ogółem, w podziale na: **Ogółem**, **UE** i **CEE**.
   - **Co oznacza:** W przeciwieństwie do wartości w złotówkach czy euro, **wolumen jest oczyszczony z wpływu cen i kursów walut** — mierzy realną zmianę fizycznej ilości wywożonych towarów (prawdziwy popyt na rynkach zagranicznych).

4. **Wskaźnik wolumenu importu – Sekcja SITC 7** *(miesięczne)*
   - **Co zawiera:** Analogiczną dynamikę wolumenu (r/r) po stronie **importu** dla **SITC 7** i ogółem (`Ogółem`, `UE`, `CEE`).
   - **Co oznacza:** Mierzy realny (ilościowy) napływ komponentów, maszyn i urządzeń do Polski. Zestawienie z wolumenem eksportu pomaga odróżnić słabszy popyt od braków podażowych.

5. **Nowe zamówienia w przemyśle (ogółem i niekrajowe)** *(miesięczne)*
   - **Co zawiera:** Dynamikę nowych zamówień w polskim przemyśle (r/r, m/m oraz względem bazy `2021 = 100`) w podziale na **Ogółem** i **Niekrajowe** (zamówienia od klientów zagranicznych).
   - **Co oznacza:** To klasyczny **wskaźnik wyprzedzający** — firmy przemysłowe najpierw zbierają nowe zamówienia eksportowe, a dopiero później zamawiają podzespoły i realizują fizyczne wysyłki.

---

### C. Struktura wartościowa, walutowa i logistyczna handlu (GUS)

6. **Eksport towarów wg ugrupowań gospodarczych** *(miesięczne)*
   - **Co zawiera:** Wartość eksportu w **PLN, EUR i USD**, masę w **kg**, udział procentowy w eksporcie ogółem oraz dynamikę r/r dla ugrupowań: **UE**, **Strefa Euro**, **CEE**, **Kraje rozwinięte** i **Kraje rozwijające się (m.in. Azja, Ameryka Łacińska)**.
   - **Co oznacza:** Pokazuje pełną skalę i strukturę geograficzną eksportu. Z relacji `EUR / kg` można dodatkowo oszacować „gęstość wartościową” wysyłanych towarów, a z `PLN / EUR` zweryfikować spójność przeliczeń GUS z kursami NBP.

7. **Import towarów wg kraju pochodzenia** *(miesięczne)*
   - **Co zawiera:** Te same miary (PLN, EUR, USD, kg, udział %, r/r) i ugrupowania co wyżej, ale liczone według **kraju pochodzenia**.
   - **Co oznacza:** Mówi, **gdzie towar został faktycznie wyprodukowany** (np. w Chinach czy na Tajwanie), niezależnie od tego, przez jaki kraj po drodze przyjechał do Polski.

8. **Import towarów wg kraju wysyłki** *(miesięczne)*
   - **Co zawiera:** Identyczne miary i ugrupowania, ale liczone według **kraju wysyłki**.
   - **Co oznacza:** Mówi, **skąd towar bezpośrednio przyjechał do Polski** (np. z magazynu/portu w Niemczech lub Holandii). Różnica między *importem wg pochodzenia* a *importem wg wysyłki* (zwłaszcza dla krajów rozwijających się / Azji) pokazuje **skalę pośrednictwa europejskich hubów logistycznych**.

---

### D. Waluty (NBP)

9. **Kursy średnie walut EUR/PLN i USD/PLN (Tabela A)** *(dzienne → miesięczne)*
   - **Co zawiera:** Miesięczną **średnią**, **minimum**, **maksimum**, **odchylenie standardowe** (zmienność w miesiącu) oraz liczbę dni roboczych dla kursów `EUR/PLN` i `USD/PLN`.
   - **Co oznacza:** Kursy walut są kluczowym czynnikiem wpływającym na ceny w handlu zagranicznym. Pozwalają oddzielić efekt wahań walutowych od realnych zmian cen towarów u producentów.

---

## 3. Krótka ściąga z pojęć

- **Indeks `analogiczny okres roku poprzedniego = 100` (r/r):** `100` oznacza brak zmian; `104.5` to wzrost o **+4,5% r/r**, a `96.0` to spadek o **-4,0% r/r**. Porównanie do tego samego miesiąca rok wcześniej eliminuje sezonowość.
- **PKWiU vs SITC:** Dwie różne klasyfikacje statystyczne. **PKWiU** pozwala bardzo precyzyjnie wyodrębnić ceny elektroniki (`26`), elektryki (`27`) i maszyn (`28`). **SITC (Sekcja 7)** jest szersza, ale daje miesięczne **wolumeny ilościowe** w podziale na rynki `UE` i `CEE`.
- **Terms of Trade (relacja cen eksportu do importu):** Jeśli jest **powyżej 100**, ceny sprzedaży rosną szybciej niż zakupu (korzystne dla marży). Jeśli spada **poniżej 100**, koszty importu rosną szybciej niż ceny w eksporcie (presja marżowa).
- **Kraj pochodzenia vs Kraj wysyłki:** Towar wyprodukowany w Azji i przywieziony do Polski przez port w Rotterdamie w statystyce *pochodzenia* widnieje jako Azja, a w statystyce *wysyłki* jako UE. Różnica mierzy uzależnienie od hubów pośredniczących.
- **Rewizje Intrastat:** GUS publikuje wstępne dane o handlu zagranicznym i koryguje je w ciągu kolejnych 1–3 miesięcy (gdy spłyną spóźnione deklaracje firm).
