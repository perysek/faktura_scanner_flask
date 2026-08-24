# Plan: migracja GUI z Flask/Jinja2/vanilla JS na React (big-bang)

**Data:** 2026-08-14 (ostatnia aktualizacja statusu: 2026-08-24)
**Status:** Faza 0 (fundamenty) i Faza 1 (pilot: Klienci) zaimplementowane, ręcznie przetestowane
i **zatwierdzone przez użytkownika 2026-08-17** — szczegóły weryfikacji w `implementation-log.md`.
Faza 2 (rollout pozostałych modułów) **w toku** — Dashboard, Sprzedawcy, Usługi, Pracownicy,
Faktury (częściowo), Wizyty+Kalendarz (częściowo), Ustawienia e-mail/SMS, Bilanse urlopowe,
Nieobecności (częściowo), Użytkownicy+Role (RBAC), Analityka/KPI (częściowo — tylko macierz
wskaźników), i Import danych (caldis.pl) zbudowane. Pierwszy ręczny click-through Faktur/Wizyt
(2026-08-19) znalazł 12 usterek UI w dwóch rundach — **wszystkie naprawione i zatwierdzone przez
użytkownika tego samego dnia**. **2026-08-24: wszystkie 7 modułów z listy "Wymaga audytu" w
`module-inventory.md` domknięte** (jeden przebieg, autonomiczny, bez przystanków — użytkownik
świadomie zwolnił z zasady "pytaj przy niejasności" na czas tego przebiegu). Pełny opis każdej
decyzji w `implementation-log.md`.
**Następny krok dla świeżej sesji, do wyboru przez użytkownika (żaden nie priorytetowy z góry):**
(a) świadomie odłożone kawałki nowo zbudowanych modułów — główny dashboard Analityki (10 wykresów
Chart.js + heatmapa szczytów, `/analiza-biznesowa`) + nowo odkryta strona `/income`, tab Kategorie
+ per-konflikt reassign/reschedule w Nieobecnościach (patrz gotowe prompty w
`module-inventory.md`); (b) świadomie odłożone kawałki Faktur/Wizyt z wcześniejszych sesji
(import/OCR staging, `/historia`, `/ustawienia/email` już zbudowane — sprawdź aktualny status w
`module-inventory.md`, integracja Wizyt z Nieobecnościami, SMS na widoku szczegółów, "Rozlicz
przeszłe wizyty"); (c) **żadna ręczna weryfikacja wizualna żadnego z modułów zbudowanych w tej
sesji jeszcze się nie odbyła** (brak narzędzi przeglądarkowych w środowisku, patrz
`implementation-log.md` — pierwszy realny click-through to naturalny następny krok, wzorem tego co
znalazło 12 usterek przy Fakturach/Wizytach). Szczegółowy status per moduł w
`module-inventory.md`.
**Reguły docelowego stacku:** `DESIGN.md` (React 18 + TS + Vite + React Router, tokeny/komponenty
opisane tam §0–§19) — **traktowany jako źródło prawdy dla tego, JAK ma wyglądać i działać nowy
frontend**, nie dla tego, co dziś istnieje w backendzie (to ten dokument, `plan.md`, ustala).
**Decyzje wejściowe (zatwierdzone przez użytkownika):**
1. Strategia: **big-bang** — nowy frontend budowany równolegle, jedno przełączenie na koniec, bez
   długiego współistnienia obu stacków na produkcji.
2. Warstwa API: **w zakresie tego planu** — każda strona musi mieć backend zwracający JSON zanim
   React ją skonsumuje.
3. Format dokumentacji: konwencja repo (`plans/<data>-<temat>/`), bez wdrażania ai-devkit.
4. Zakres pierwszego przebiegu: **pilot na module Klienci** (średnia złożoność, dobry wzorzec),
   plus checklist do powielenia na resztę (`module-inventory.md`).

---

## 0. Najważniejsze ustalenie audytu — zmienia szacunek pracy

**To NIE jest migracja "od zera przepisz backend na API".** `routes/api_routes.py` (4589 linii) ma
już pełne, dojrzałe CRUD-y JSON dla większości modułów danych:

| Moduł | Endpointy JSON już istnieją? |
|---|---|
| Klienci | **Tak, kompletnie** — GET lista+staty, GET pojedynczy, duplicate-check, POST, PUT, DELETE, restore, activate/deactivate, bulk-update-preferences, visit-trends, statistics, birthdays (13 endpointów) |
| Sprzedawcy | **Tak, kompletnie** — GET/POST/PUT/DELETE + bulk-update, conflicts, sync (3 warianty), check-duplicate, seller-passwords CRUD |
| Usługi + kategorie | **Tak, kompletnie** — CRUD usług, price-history, statistics, CRUD kategorii |
| Pracownicy | **Tak, kompletnie** — CRUD, mobile-pin (get/reset/put), permanent-delete, statistics, positions, bulk-update-services, direct-reports; + formy-zatrudnienia CRUD osobno |
| Faktury | **Tak, kompletnie** — GET/POST/PUT/DELETE/restore, seller-sync-check/apply, confirm-seller, statistics, PDF, export, email import/test/folders/settings |
| Dashboard | **Tak** — recent-invoices, upcoming-payments, overdue-payments, top-sellers, monthly-totals |
| Wizyty/appointments | **Prawdopodobnie tak w większości** — `appointment_routes.py`: 35× `jsonify`, **0× `render_template`** (czysty JSON blueprint) |
| Analityka | **Prawdopodobnie tak w większości** — `analytics_routes.py`: 44× `jsonify`, 0× `render_template` |
| Nieobecności (wnioski) | **Prawdopodobnie tak w większości** — `absence_routes.py`: 40× `jsonify`, tylko 2× `render_template` |
| Bilanse urlopowe | **Prawdopodobnie tak w większości** — `absence_balance_routes.py`: 39× `jsonify`, 1× `render_template` |
| Użytkownicy / Role (RBAC) | **Częściowo** — `users/routes.py`: 6 jsonify / 4 render; `roles/routes.py`: 4/4 — mieszane, wymaga audytu przed budową |
| Rezerwacje (booking) | **Częściowo** — `booking_routes.py`: 12 jsonify / 1 render, ale to strona **publiczna, bez logowania** — nie jest jasne, czy w ogóle wchodzi w zakres DESIGN.md (patrz §5 "Otwarte pytania") |
| **Autentykacja** | **NIE — to jedyna prawdziwa luka.** `routes/auth/routes.py` to klasyczny `request.form` + redirect/render, zero JSON. Musi powstać nowa JSON-owa ścieżka logowania zanim React będzie mógł się zalogować (Faza 0, patrz `phase-00-foundations.md`). |

**Wniosek:** największy realny nakład pracy backendowej to (a) dobudowanie JSON-owego auth,
(b) audyt i domknięcie luk w RBAC/booking, (c) ewentualne dodanie paginacji/filtrów tam, gdzie
dzisiejsze endpointy zwracają "wszystko naraz" (obecny `GET /api/clients` zwraca całą listę + staty
w jednym payloadzie — dziś to OK, bo `clients/list.html` **już renderuje tabelę po stronie klienta
w JS** z tego samego endpointu, więc port na React tej konkretnej strony jest bliżej "przepisania
istniejącej logiki fetch+render na JSX" niż projektowania czegokolwiek od nowa).

## 0.1 Rozbieżności DESIGN.md względem obecnego stanu — do świadomej decyzji, nie automatu

`DESIGN.md` (target) różni się od tego, co dziś naprawdę istnieje w `input.css`, w kilku punktach,
które są **decyzjami projektowymi, nie neutralnym portem**:

1. **Font: Inter → Geist Variable.** To widoczna zmiana identyfikacji wizualnej, nie techniczny
   detal. Potwierdź świadomie, że to zamierzone (a nie np. artefakt tego, że DESIGN.md został
   wygenerowany bez pełnej wiedzy o obecnym foncie).
2. **Nowy formalny ramp cieni** (`--shadow-xs` … `--shadow-xl`, `--shadow-focus`,
   `--shadow-sidebar`, tinted `rgba(26,20,12,…)`). Obecny `input.css` **nie ma tokenów cienia w
   ogóle** — cienie są dziś hardcodowane inline per-klasa (`box-shadow: 0 1px 3px rgba(0,0,0,.04)`,
   czarne, nie brązowe). To realne ulepszenie systemu, ale oznacza, że **każdy istniejący cień w
   `input.css` trzeba świadomie przemapować** na nowy ramp podczas portu tokenów (Faza 0) — nie ma
   1:1 automatycznego mapowania.
3. **Drugi, równoległy system ikon nawigacyjnych** (`NavIcon`, viewBox `0 0 24 24`, stroke) —
   dzisiejszy `icons.html`/`icons.js` ma tylko jeden system (`0 -960 960 960`, filled). Sidebar dziś
   przyjmuje surowy `svg_path_d` per link w makrze — **nie ma gotowego źródła 24×24 stroke-path'ów**
   do skopiowania; trzeba je dobrać (DESIGN.md sugeruje Heroicons-outline jako konwencję źródłową).
4. **`--color-orange`/`--color-pink` jako nazwane tokeny semantyczne** — dziś te kolory istnieją
   tylko jako wartości chart-palette (`--color-chart-orange`/`-pink`) i ad-hoc literały
   (`#c2410c` w kilku miejscach `input.css` dla `.stat-icon.orange`/`.status-badge.on-leave`).
   Konsolidacja w nazwane tokeny semantyczne jest dobra, ale trzeba przejrzeć każde dzisiejsze
   użycie `#c2410c`/podobnych i zdecydować, czy faktycznie znaczy "orange" semantycznie, czy to był
   przypadek.
5. **Motywy w DESIGN.md mają inne wartości niż `input.css`** dla surface/border w kilku miejscach
   (np. `--color-surface-warm: #f2f0ea` vs obecne `#f7f6f3`; `--color-surface-elevated: #fdfcfa` vs
   obecne `#ffffff`). To subtelna, ale realna zmiana palety — port tokenów w Fazie 0 musi używać
   **wartości z DESIGN.md**, nie z `input.css`, tam gdzie się różnią (DESIGN.md jest tu źródłem
   prawdy per ustalenie na starcie tej rozmowy), ale ktoś świadomie powinien to zobaczyć zestawione
   obok siebie przed wdrożeniem, żeby nie było niespodzianki na zrzucie ekranu.

Rekomendacja: **Faza 0 kończy się krótkim diffem tokenów "input.css → tokens.css" do jednorazowej
akceptacji wzrokowej**, zanim ruszy budowa jakiejkolwiek strony — żeby te 5 punktów nie wypłynęły
dopiero przy review pilota.

---

## 1. Strategia — co znaczy "big-bang" konkretnie

- Nowy frontend (`frontend/` — katalog nie istnieje jeszcze w repo, tworzony od zera) rośnie
  równolegle na osobnej gałęzi/gałęziach, **niepodłączony do ruchu produkcyjnego** przez cały czas
  budowy.
- Backend Flask **żyje przez cały czas budowy bez przerwy** — obecne strony Jinja dalej obsługują
  produkcję; zmiany backendowe tego planu (nowe/uzupełnione endpointy JSON) są **addytywne**, nie
  usuwają ani nie psują istniejących tras `render_template` po drodze.
- Warunek przełączenia (cutover, Faza 4): **parytet funkcjonalny 100% modułów** z checklisty
  `module-inventory.md` + zielone testy E2E na krytycznych ścieżkach (logowanie, faktury, wizyty,
  klienci) + jeden zamrożony tydzień bez zmian w Jinja UI przed cutover, żeby nie gonić ruchomego
  celu.
- Po cutover: okres karencji (proponowane 2–4 tygodnie) z Jinja-em zdeployowanym, ale nieużywanym
  (rollback path), zanim szablony/`input.css`/stare JS zostaną fizycznie usunięte (Faza 5).
- **Ryzyko big-bangu, świadomie zaakceptowane:** cały wysiłek buforowany do jednego dużego
  przełączenia. Mitigacja = Faza 1 (pilot) musi realnie przejść przez React w warunkach zbliżonych
  do produkcyjnych (prawdziwe logowanie, prawdziwe dane) zanim ruszy powielanie na 14 pozostałych
  modułów — nie zgadujemy wzorca, tylko go raz porządnie sprawdzamy.

## 2. Fazy

| Faza | Plik | Zawartość | Status | Blokuje |
|---|---|---|---|---|
| **0 — Fundamenty** | `phase-00-foundations.md` | Vite scaffold, port tokenów, JSON auth, `AuthContext`/`ProtectedRoute`, shell/sidebar/routing, theming, oba systemy ikon, `ToastProvider`/`ConfirmProvider` | ✅ Zakończona | Wszystko poniżej |
| **1 — Pilot: Klienci** | `phase-01-pilot-clients.md` | Pełna migracja jednego modułu średniej złożoności jako wzorzec + walidacja API | ✅ **Zakończona i zatwierdzona (2026-08-17)** | Fazę 2 |
| **2 — Rollout pozostałych modułów** | `module-inventory.md` (checklist) | Powielenie wzorca z Fazy 1 na ~14 pozostałych modułów, moduł po module, wg tabeli gotowości API | ⏳ Nierozpoczęta | Fazę 3 |
| **3 — QA / parytet** | *(do napisania po Fazie 2)* | E2E per moduł, porównanie z Jinja side-by-side, a11y re-audit (DESIGN.md §11/§19), test 4 motywów | ⏳ Nierozpoczęta | Fazę 4 |
| **4 — Cutover** | *(do napisania bliżej terminu)* | Przełączenie ruchu, plan rollback, komunikacja | ⏳ Nierozpoczęta | Fazę 5 |
| **5 — Sprzątanie** | *(po okresie karencji)* | Usunięcie `templates/`, `input.css`, starych `static/js/*`, tras `render_template` z `main_routes.py` | ⏳ Nierozpoczęta | — |

Ten dokument zawiera na razie **Fazę 0 i Fazę 1** w pełnym detalu (to był zakres zaakceptowany na
starcie) + `module-inventory.md` jako checklistę/szablon do powielenia. Fazy 3–5 rozpisujemy po
zamknięciu pilota — pisanie ich szczegółowo teraz byłoby zgadywaniem na podstawie nieistniejącego
jeszcze doświadczenia z Fazy 1.

## 3. Otwarte pytania — nie zgaduję, zostawiam do decyzji

1. **Booking (`booking_routes.py`, `templates/booking/`) i strony publiczne
   (`templates/public/`, `templates/landing/`)** — to prawdopodobnie strony **bez logowania**,
   part­nersko/klient-facing, nie "aplikacja wewnętrzna". `DESIGN.md` opisuje wyłącznie: (a) shell
   uwierzytelnionej aplikacji, (b) trzy ekrany auth. **Nie opisuje żadnego layoutu dla stron
   publicznych.** Decyzja do podjęcia: czy booking/landing/public wchodzą w tę migrację w ogóle,
   czy zostają na Jinja na stałe (zupełnie zasadny wybór — publiczna strona rezerwacji nie musi być
   SPA), czy dostają osobny, jeszcze nienapisany rozdział DESIGN.md.
2. **`routes/mobile_routes.py`** — 15× `jsonify`, 0 `render_template`, ale nie znalazłem
   odpowiadającego katalogu `templates/mobile/` w drzewie szablonów. Podejrzewam, że to API dla
   osobnej aplikacji mobilnej (naive JS PWA czy coś zewnętrznego), **nie** część tej migracji GUI —
   do potwierdzenia, żeby nie próbować "migrować" czegoś, co nie jest tym samym frontendem.
3. **RBAC (`users/routes.py`, `roles/routes.py`)** — miks JSON/Jinja, w tym prawdopodobnie
   `.permission-tile` (wspomniany w `DESIGN.md` §6 przy okazji `.btn-press`) sugerujący siatkę
   uprawnień, której jeszcze nie widziałem w kodzie. Wymaga własnego głębokiego audytu przed
   Fazą 2 dla tego modułu — nie jest tak prosty jak Klienci.

---

## 4. Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Auth JSON-owy wprowadza regresję w dzisiejszym logowaniu Jinja (bo dotyka tego samego `routes/auth/routes.py`) | Nowe endpointy JSON obsługują żądanie tylko gdy jest nagłówek `X-Requested-With` (wzorzec już opisany w DESIGN.md §15.1) — istniejąca ścieżka form-POST zostaje nietknięta |
| 5 rozbieżności z §0.1 wypłyną dopiero na produkcji jako "coś wygląda inaczej niż miało" | Diff tokenów do jednorazowej akceptacji na końcu Fazy 0 (patrz §0.1) |
| Big-bang = długi czas bez wglądu w postęp na żywym ruchu | Pilot (Faza 1) wdrożony za feature-flagiem/na subdomenie staging z prawdziwym logowaniem, nie tylko lokalnie |
| RBAC/booking/mobile mają nieznaną głębię pracy (brak audytu) | Nie szacujemy ich teraz na sztywno — `module-inventory.md` oznacza je jako "wymaga audytu" zamiast zgadywać liczbę dni |
| Rozjazd między `NavLinkConfig.visible` a rzeczywistą regułą backendu (dokładnie ostrzeżenie z DESIGN.md §13.5) | Dla każdego modułu w Fazie 2: zanotować w checklist dokładny warunek backendowy (`@module_permission_required('x')` / rola) obok predykatu frontendowego, review 1:1 |

---

## 5. Pliki tego planu

- `plan.md` — ten dokument
- `phase-00-foundations.md` — fundamenty przed jakąkolwiek stroną
- `phase-01-pilot-clients.md` — pełny pilot na module Klienci
- `module-inventory.md` — tabela wszystkich modułów + gotowe prompty do przekazania innej sesji
  agenta dla modułów, których jeszcze nie audytowałem w głąb (kalendarz wizyt, RBAC, analityka,
  nieobecności, booking, import/OCR)
