# Inwentaryzacja modułów — checklist do powielenia wzorca z Fazy 1

Wypełniaj kolumnę **Status** w miarę postępu Fazy 2. Kolumna **Gotowość API** pochodzi z audytu
`plan.md` §0 (liczba `jsonify`/`render_template` w odpowiednim pliku tras — sygnał, nie dowód
kompletności; każdy moduł i tak wymaga własnego mini-gap-analysis jak w `phase-01-pilot-clients.md`
§1.2 zanim ruszy budowa).

| Moduł | Trasy Jinja (plik) | API (plik) | Gotowość API | Złożoność UI (szac.) | Status |
|---|---|---|---|---|---|
| **Klienci** | `main_routes.py` | `api_routes.py` | Kompletna | Średnia | **✅ Zakończony — Faza 1 (zatwierdzony 2026-08-17; UI/nawigacja/tabele/karty statystyk ponownie ręcznie zweryfikowane na żywo 2026-08-18 przy okazji UX-passu, patrz log)** |
| Sprzedawcy | `main_routes.py` | `api_routes.py` | Kompletna | **Wysoka** (skorygowano 2026-08-17 — patrz niżej) | **✅ Zbudowany (Faza 2, 2026-08-17) — UI/nawigacja/tabele ręcznie zweryfikowane na żywo 2026-08-18; pełny funkcjonalny test CRUD nadal czeka. ⚠️ 2026-08-19: znaleziono 1 usterkę UI (wyrównanie nagłówków tabeli), patrz "Pierwszy ręczny QA" niżej i implementation-log.md** |
| Usługi + kategorie | `main_routes.py` | `api_routes.py` + `service_addon_routes.py` | Kompletna | **Wysoka** (skorygowano 2026-08-17 — 4 pod-strony, patrz log) | **✅ Zbudowany (Faza 2, 2026-08-17) — UI/nawigacja/tabele ręcznie zweryfikowane na żywo 2026-08-18; pełny funkcjonalny test CRUD nadal czeka** |
| Pracownicy + formy zatrudnienia | `main_routes.py` | `api_routes.py` | Kompletna (+2 nowe endpointy 2026-08-17: `direct-reports`, `user-options`) | Wysoka (mobile-pin, bulk-services, direct-reports; analizy/wykresy świadomie odłożone) | **✅ Zbudowany (Faza 2, 2026-08-18) — UI/nawigacja/tabele ręcznie zweryfikowane na żywo 2026-08-18; pełny funkcjonalny test CRUD nadal czeka** |
| Faktury | `main_routes.py` + upload | `api_routes.py` | Kompletna (+PDF/email/export) | Wysoka (OCR upload flow) | **✅ Częściowo zbudowany (Faza 2, 2026-08-18) — lista + CRUD + konflikt sprzedawcy + sync + eksport gotowe; podgląd PDF w panelu, `/import-dokumentow` (OCR+SSE), `/historia`, `/ustawienia/email` świadomie odłożone jako osobny przebieg, patrz korekta niżej i implementation-log.md. ⚠️ 2026-08-19: pierwszy ręczny test — panel podglądu PDF (edycja) źle wymiarowany/proporcjonowany, naprawa do zrobienia jako OSTATNIA w kolejce (najbardziej inwazyjna), patrz "Pierwszy ręczny QA" niżej** |
| Dashboard/Pulpit | `main_routes.py` | `api_routes.py` | Kompletna (5 widgetów) | Niska–średnia | **✅ Zbudowany (Faza 2, 2026-08-17) — czeka na ręczny test** |
| Wizyty (lista + CRUD) | `main_routes.py` | `appointment_routes.py` (28 endpointów) | Kompletna | **Bardzo wysoka** (skorygowano 2026-08-18 — 9449 linii w 10 szablonach, patrz korekta niżej) | **✅ Zbudowany częściowo (Faza 2, 2026-08-18) — lista + widok szczegółów + create/edit gotowe. ⚠️ 2026-08-19: pierwszy ręczny test — lista bez sticky-header/scroll wzorca (brak retrofitu z 2026-08-18), widok szczegółów bez przycisku "Powrót"/Escape i ze niejasnymi przyciskami statusu — patrz "Pierwszy ręczny QA" niżej** |
| Kalendarz wizyt (dzień/tydzień/miesiąc) | `main_routes.py` | `appointment_routes.py` | Kompletna | **Wysoka, ale BEZ drag&drop** (odkrycie audytu 2026-08-18 — patrz korekta niżej) | **✅ Zbudowany (Faza 2, 2026-08-18)** — 3 widoki + boczny pasek month-cards. **⚠️ 2026-08-19: pierwszy ręczny test — widoki dnia/tygodnia przewyższają wysokością viewport (scroll pionowy), dzień-widok dodatkowo wymaga przeniesienia sidebaru month-cards z lewej na prawą stronę — patrz "Pierwszy ręczny QA" niżej** |
| Analityka / KPI / Przychody | `main_routes.py` | `analytics_routes.py` (44 jsonify, 0 render) | Prawdopodobnie kompletna | Wysoka (wykresy — patrz `dataviz` skill przy budowie) | **Wymaga audytu** |
| Nieobecności (wnioski) | `absence` blueprint | `absence_routes.py` (40/2) | Prawdopodobnie kompletna | Średnia | **Wymaga audytu** |
| Bilanse urlopowe | `absence_balance` blueprint | `absence_balance_routes.py` (39/1) | Kompletna, w pełni JSON | Średnia–wysoka (inline spinbox/save/undo/reset per wiersz) | **✅ Zbudowany (Option A rollout, 2026-08-24) — `/bilanse-urlopow`: staty, filtry (szukaj/kategoria/status), tabela z inline edycją wykorzystania/limitu/okresu per (pracownik, kategoria), reason-wymagany-przy-zmianie-wykorzystania, zapis+jednopoziomowe cofnięcie+reset-do-zera. `npm run build`/`lint` zielone (backend bez zmian, `pytest` nie wymagany).** |
| Import danych / historia | `main_routes.py` | `import_routes.py` (8/0) | Nieznana | Nieznana (prawdopodobnie OCR/plik) | **Wymaga audytu** |
| Użytkownicy (RBAC) | `users/routes.py` (6/4) | częściowo w tym samym pliku | **Częściowa** | Nieznana | **Wymaga audytu** |
| Role (RBAC, `.permission-tile`) | `roles/routes.py` (4/4) | częściowo w tym samym pliku | **Częściowa** | **Wysoka** (siatka uprawnień) | **Wymaga audytu** |
| Ustawienia e-mail/SMS | `main_routes.py` + `sms_routes.py` (15/2) | mieszane | Nieznana | Niska–średnia | **✅ Zbudowany (Option A rollout, 2026-08-24) — `/ustawienia/email` (już w pełni JSON) + `/ustawienia/sms` (Twilio creds/stats/typy wiadomości, nowe endpointy `/api/sms/*` dodane jako siostrzane do form-POST Jinja) + `/ustawienia/sms/historia`. `npm run build`/`lint` + `pytest` zielone. Ręczna weryfikacja wizualna czeka (brak narzędzi przeglądarkowych w tym środowisku, patrz [[react-migration-browser-tooling-gap]])** |
| Profil / zmiana hasła | `routes/auth/routes.py` | — | Buduje się w Fazie 0 (auth) | Niska | Część Fazy 0 |
| Booking (publiczne, bez logowania) | `booking_routes.py` (12/1) | częściowo | Nieznana | Nieznana | **Poza zakresem? — patrz `plan.md` §5 pkt 1** |
| Landing/public | `templates/landing`, `templates/public` | brak dedykowanego | — | — | **Poza zakresem? — patrz `plan.md` §5 pkt 1** |
| Mobile API (`mobile_routes.py`) | brak `templates/mobile/` znalezionego | `mobile_routes.py` (15/0) | — | — | **Prawdopodobnie inna aplikacja, nie ten frontend — potwierdzić i wykluczyć** |

## Korekta złożoności — Sprzedawcy (2026-08-17, przy starcie budowy w Fazie 2)

Etykieta "Średnia" pochodziła z samego audytu `plan.md` §0 (liczba `jsonify`/`render_template`) —
sygnał, nie mini-gap-analysis. Po realnym przeczytaniu `templates/sellers/list_refined.html`
(1308 linii — CSS 445 / HTML 200 / JS ~655) okazuje się, że to **trzy osobne pod-funkcje** na
jednej stronie, nie jeden wzorzec list+CRUD jak Klienci:

1. Lista sprzedawców + CRUD (sort/search/stats-bar) — analogiczne do Klientów.
2. **Workflow synchronizacji** z fakturami: `syncSellers()` → osobny pełnoekranowy widok wyników
   (`sync-results-view`) z dwiema tabelami — "Niezgodności nazw" (fix per-wiersz: użyj nazwy z bazy
   / z faktury) i "Brakujący sprzedawcy" (dodaj per-wiersz) — patrz `plan.md` §0 "sync (3 warianty)".
3. **Panel haseł PDF** (`openPasswordsPanel()`) — osobne, w pełni odrębne CRUD na
   `SellerPdfPassword` (`database/models.py`), wysuwane jako panel nad listą sprzedawców, nie
   wspomniane w ogóle w tej tabeli przed tą korektą.

Budowa w React: trzy odrębne komponenty/podstrony (`SellersListPage`, `SellerSyncResultsView`,
`SellerPasswordsPanel`), nie jeden `SellersListPage` na wzór Klientów.

## Korekta zakresu — Faktury (2026-08-18, przy starcie budowy w Fazie 2)

Etykieta "Wysoka (OCR upload flow)" z audytu `plan.md` §0 okazała się, po realnym przeczytaniu
`templates/invoices/{list_refined,create,edit,upload}.html` (5074 linii łącznie) +
`routes/upload_routes.py` (staging/SSE-streaming `process`/`finalize`), niedoszacowaniem — to
największy moduł Fazy 2 dotąd, wyraźnie złożony z **dwóch niezależnych rodzin funkcji**, nie
jednego wzorca list+form jak Klienci/Sprzedawcy/Usługi/Pracownicy:

1. **List+CRUD+konflikt sprzedawcy+sync+eksport** — dokładnie ten sam wzorzec co reszta Fazy 2,
   tylko z jednym naprawdę nowym elementem: dwuetapowy przepływ 409 "konflikt sprzedawcy"
   (`seller_conflict`/`seller_info` z `POST/PUT /api/invoices*`) wymagający modala decyzji +
   resubmitu (multipart dla create, JSON przez `/confirm-seller` dla edit) — nieobecny w żadnym
   innym module Fazy 2. Osobny mini-sync (`/api/invoices/seller-sync-check|apply`, prostszy niż
   Sprzedawców własny `/api/sellers/sync` — tylko łączenie z ISTNIEJĄCYM sprzedawcą, nigdy
   tworzenie nowego) zbudowany jako modal (`SellerSyncModal.tsx`), nie osobna podstrona.
2. **Import/OCR** (`/import-dokumentow` — staging wielu plików, SSE-streamowany progress OCR,
   finalize, podgląd PDF w bocznym panelu, `/historia`, `/ustawienia/email`) — architektonicznie
   zupełnie inny rodzaj UI (streaming, wieloplikowy staging), bliższy Kalendarzowi wizyt
   (drag&drop) niż wzorcowi list+form. **Świadomie odłożone jako osobny, następny przebieg** —
   patrz `implementation-log.md` dla pełnego uzasadnienia i listy tego, co konkretnie zostało poza
   zakresem tej sesji.

Zbudowane w tym przebiegu: `FakturyListPage`/`FakturaFormPage`/`SellerSyncModal` (`pages/faktury/`),
pełny `invoicesApi` (`lib/api/invoices.ts`), typy w `types/invoice.ts`, plus dwie zmiany
infrastrukturalne w `lib/api/client.ts` (pierwsze w SPA wsparcie dla `FormData`/upload plików;
`ApiError.data` niosące pełne ciało JSON błędu — potrzebne, żeby czytać `seller_conflict`/
`seller_info` ze statusu 409, nie tylko string wiadomości).

## Korekta zakresu — Wizyty + Kalendarz (2026-08-18, przy starcie budowy w Fazie 2)

Audyt z `module-inventory.md`'s prompta dla "Kalendarz wizyt" zakładał drag&drop jako
najwyższe ryzyko. Po realnym przeczytaniu 10 szablonów (`templates/appointments/*.html`,
9449 linii łącznie) + `routes/appointment_routes.py` (28 endpointów) okazało się:

1. **Żaden z 3 widoków kalendarza nie ma drag&drop.** `calendar.html`/`calendar_week.html`/
   `calendar_month.html` renderują bloki wizyt jako pozycjonowane czasowo `<div>`y
   (position:absolute wg godziny), klikalne — klik = `window.location.href` do
   `/appointment/:id`. Zero `dragstart`/`draggable`/`ondrop` w całym katalogu. Ryzyko z
   audytu wstępnego było przesadzone w JEDNYM wymiarze (interakcja), ale
   niedoszacowane w INNYM: to i tak największy moduł w apce po prostu z racji
   objętości — 10 szablonów, nie 3-4 jak inne moduły.
2. Moduł to w rzeczywistości **znacznie więcej niż "lista + kalendarz"**: osobny
   "power editor" dla superadmina (`superadmin_edit.html` 1125 linii +
   `superadmin_edit_table.html` 1666 linii, gated `data_correction`, już poprawnie
   poza zakresem w routerze), mobilny self-service pracownika (`my_visits.html`,
   `/my-visits`, bez bramki modułowej — inna apka), integracja z nieobecnościami
   (reassign/reschedule/cancel-for-absence — `@absence_management_required`, jawnie
   oznaczone w kodzie jako "Faza 3" supervisor-tool), wysyłka/log SMS.

**Zbudowane w tym przebiegu:** lista (tydzień + tryb "day-chain" z bocznego paska),
widok szczegółów, create/edit, 3 widoki kalendarza, boczny pasek month-cards
(`calendar-sidebar-redesign-prompt.md`, wpięty w dzień-widok i listę na życzenie
użytkownika). **Poza zakresem** (świadomie, do osobnego przebiegu): integracja z
nieobecnościami, wysyłka/log SMS na widoku szczegółów, "Rozlicz przeszłe wizyty"
(skaner `past-pending`/`past-status`), `status-events` polling (globalne
powiadomienia, nie specyficzne dla tych stron). Pełna lista decyzji i uzasadnień w
`implementation-log.md`.

## ✅ 12 usterek UI z dwóch rund QA — naprawione i ZATWIERDZONE przez użytkownika, 2026-08-19

Dwie rundy poprawek tego samego dnia: pierwsza runda — 7 usterek z pierwszego ręcznego
click-through (Wizyty lista, Sprzedawcy nagłówki, Wizyta detail Powrót+dropdown statusu,
Kalendarz tydzień/dzień wysokość+sidebar+page-header, Faktury PDF panel A4). Druga runda —
5 kolejnych usterek z `react-ui-corrections_19080026.txt` (month-cards nachodzenie+nawigacja,
dzień/tydzień kolory statusu+treść bloku+resztkowy scroll, widok miesiąca szerokość+kolory,
panel miniatur PDF). **Użytkownik zatwierdził całość UI po obu rundach** (build/lint czyste po
każdej poprawce; wizualna weryfikacja na żywo była niemożliwa w trakcie implementacji — ani
`/browse`, ani rozszerzenie Chrome nie działały w tym środowisku, patrz
[[react-migration-browser-tooling-gap]] — ale użytkownik potwierdził wynik osobiście po fakcie).
Pełny opis obu rund w `implementation-log.md`.

**Świeża sesja: moduł Wizyty+Kalendarz i Faktury (częściowo) są teraz zamknięte pod kątem UI.**
Następny krok to dowolny z: (a) kolejny moduł z listy "Wymaga audytu" niżej, (b) świadomie
odłożone kawałki Faktur (import/OCR staging, `/historia`, `/ustawienia/email`) lub Wizyt
(integracja z Nieobecnościami, SMS na widoku szczegółów, "Rozlicz przeszłe wizyty") — patrz
`plan.md`'s status i "Korekta zakresu" sekcje wyżej w tym pliku dla pełnej listy odłożonych
kawałków per moduł.

## Pierwszy ręczny QA po naprawie loginu — 2026-08-19 (opis oryginalnych usterek, patrz status wyżej)

Login (kolizja portów z niepowiązanym projektem `human-solutions`, patrz implementation-log.md)
naprawiony 2026-08-19, po czym użytkownik po raz pierwszy realnie przeklikał Faktury i
Wizyty+Kalendarz (oba zbudowane 2026-08-18, nigdy wcześniej nie klikane) plus wrócił do
Sprzedawców. Znaleziono **7 konkretnych usterek UI**, zero jeszcze naprawionych. Surowe notatki
źródłowe (jeśli plik nadal istnieje): `react-UI-issues-fixes_19082026.txt` w korzeniu repo —
**niezacommitowany plik roboczy**, nie mylić z tym podsumowaniem. Pełny opis każdej usterki +
uzasadnienie kolejności w `implementation-log.md`'s sekcja "Naprawa loginu ... + pierwszy ręczny
QA — 2026-08-19".

**To jest zalecany następny krok dla kolejnej sesji** — przed sięganiem po jakikolwiek nowy moduł
z listy "Wymaga audytu" poniżej, dokończyć/oszlifować to, co już zbudowane i właśnie ręcznie
przetestowane:

1. Wizyty lista — retrofit wzorca `.table-container`/sticky-header/scroll z `ClientsListPage`
   (mechaniczne, precedens z 2026-08-18).
2. Sprzedawcy lista — wyrównanie nagłówków kolumn zgodnie z wartościami wierszy (trywialne CSS).
3. Wizyta detail — `useEscapeBack` + przycisk "Powrót" (ponowne użycie istniejącego hooka).
4. Wizyta detail — dropdown zmiany statusu zamiast przycisków. **⚠️ Zadać pytanie
   doprecyzowujące PRZED implementacją** (auto-zapis vs. osobny przycisk potwierdzenia; pełna lista
   statusów vs. tylko `VALID_TRANSITIONS`) — zgodnie z `CLAUDE.md`'s clarification policy.
5. Kalendarz tydzień — dopasowanie wysokości siatki do viewportu (zero scrolla pionowego).
6. Kalendarz dzień — to samo dopasowanie wysokości + przeniesienie sidebaru month-cards z lewej na
   prawą stronę widoku.
7. Faktury edycja — panel podglądu PDF: proporcja A4 zamiast kwadratu, wysokość = od góry panelu do
   stopki page-view, prawdopodobny reflow reszty formularza. **Najbardziej inwazyjna — na koniec.**

Backend: żadna z tych 7 poprawek nie dotyka `routes/`/`repositories/` — czysty CSS/layout/
component-level fix na już poprawnie zabezpieczonych endpointach.

## Gotowe prompty do audytu modułów oznaczonych "Wymaga audytu"

Każdy poniższy prompt można wkleić do sesji/agenta pracującego na tym repo (albo wykonać samemu w
tej sesji, bezpośrednio przez Read/Grep) **przed** rozpoczęciem budowy danego modułu w Fazie 2 —
dokładnie ten mechanizm, o który prosiłeś na starcie. Nie odpalałem ich teraz, żeby nie rozdmuchać
tego planu ponad zaakceptowany zakres (pilot + inwentaryzacja).

### Kalendarz wizyt (najwyższe ryzyko — drag&drop, prawdopodobnie najbardziej złożony UI w całej apce)
> *"Znajdź wszystkie trasy Jinja obsługujące `/appointments`/kalendarz w `main_routes.py` (grep po
> `appointment`), wypisz odpowiadające im szablony w `templates/appointments/`, i dla każdego opisz:
> czy to statyczny render czy JS-renderowany widok (jak `clients/list.html`). Osobno przeczytaj
> `routes/appointment_routes.py` w całości i wypisz pełną listę endpointów z metodami HTTP. Sprawdź
> czy w `static/js/` jest dedykowany plik do kalendarza (drag&drop, przeciąganie wizyt między
> slotami) i jeśli tak — opisz dokładnie jego mechanikę (jakiej biblioteki/API używa: natywne
> HTML5 drag-and-drop, mysz+JS, czy coś innego), bo to determinuje wybór biblioteki React do
> portu (np. potrzeba dnd-kit vs. można to zrobić natywnie)."*

### Analityka / wykresy
> *"Przeczytaj `routes/analytics_routes.py` w całości, wypisz pełną listę endpointów. Sprawdź
> `templates/analytics/` — czy wykresy są renderowane biblioteką JS (Chart.js? D3? coś innego —
> grep po `static/js/analytics/`) czy generowane server-side jako obrazki/SVG. Podaj dokładny
> kształt JSON zwracany przez 2-3 reprezentatywne endpointy (np. te używane przez dashboard
> KPI), żeby dało się zaprojektować typy TS bez zgadywania."*

### RBAC — Użytkownicy i Role (siatka uprawnień)
> *"Przeczytaj `routes/users/routes.py` i `routes/roles/routes.py` w całości. Wypisz, które
> endpointy zwracają JSON a które renderują Jinja — dla renderowanych, opisz czy dane do
> uzupełnienia siatki uprawnień (`.permission-tile` wspomniana w DESIGN.md) są już dostępne przez
> jakiś istniejący endpoint JSON, czy trzeba by je dopiero zbudować. Znajdź i pokaż szablon
> odpowiedzialny za siatkę uprawnień (prawdopodobnie w `templates/roles/`) i opisz jego strukturę
> danych: jak są reprezentowane moduły × uprawnienia, jak wygląda zapis zmiany (czy to bulk-save
> całej macierzy czy pojedyncze przełączniki per-komórka)."*

### Nieobecności + bilanse urlopowe
> *"Przeczytaj `routes/absence_routes.py` i `routes/absence_balance_routes.py` w całości, wypisz
> pełne listy endpointów z metodami. Sprawdź `templates/absences/` — ile jest tam podstron (wnioski,
> kategorie, bilanse, moje-nieobecności — DESIGN-TOKENS.md wspominał o tych czterech jako już
> zmigrowanych na `.stack-cards`) i dla każdej krótko opisz, czy renderuje się server-side czy
> JS-em jak `clients/list.html`."*

### Import danych / historia / OCR upload
> *"Przeczytaj `routes/import_routes.py` i `routes/upload_routes.py` w całości. Opisz cały flow:
> jak wygląda upload pliku (faktury?), czy jest tam polling/progress (async processing w tle?),
> jaki jest kształt odpowiedzi. To determinuje, czy React-owy odpowiednik potrzebuje
> polling/WebSocket/SSE, czy to prosty synchroniczny request-response."*

### Booking (do decyzji zakresu, patrz `plan.md` §5 pkt 1) — audytować DOPIERO PO decyzji, czy w ogóle wchodzi w zakres
> *"Przeczytaj `routes/booking_routes.py` w całości i `templates/booking/`. Opisz: czy to strona
> wymagająca logowania czy w pełni publiczna, jaki ma layout (współdzielony z resztą apki czy
> całkiem osobny), i czy DESIGN.md's AuthLayout/authenticated-shell w ogóle pasuje do tego
> przypadku użycia, czy to zupełnie inny typ ekranu wymagający własnej specyfikacji projektowej."*
