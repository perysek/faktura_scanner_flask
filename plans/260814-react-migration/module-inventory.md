# Inwentaryzacja modułów — checklist do powielenia wzorca z Fazy 1

Wypełniaj kolumnę **Status** w miarę postępu Fazy 2. Kolumna **Gotowość API** pochodzi z audytu
`plan.md` §0 (liczba `jsonify`/`render_template` w odpowiednim pliku tras — sygnał, nie dowód
kompletności; każdy moduł i tak wymaga własnego mini-gap-analysis jak w `phase-01-pilot-clients.md`
§1.2 zanim ruszy budowa).

| Moduł | Trasy Jinja (plik) | API (plik) | Gotowość API | Złożoność UI (szac.) | Status |
|---|---|---|---|---|---|
| **Klienci** | `main_routes.py` | `api_routes.py` | Kompletna | Średnia | **Pilot — Faza 1** |
| Sprzedawcy | `main_routes.py` | `api_routes.py` | Kompletna | Średnia | Nie rozpoczęto |
| Usługi + kategorie | `main_routes.py` | `api_routes.py` | Kompletna | Średnia | Nie rozpoczęto |
| Pracownicy + formy zatrudnienia | `main_routes.py` | `api_routes.py` | Kompletna | Wysoka (mobile-pin, bulk-services, direct-reports) | Nie rozpoczęto |
| Faktury | `main_routes.py` + upload | `api_routes.py` | Kompletna (+PDF/email/export) | Wysoka (OCR upload flow) | Nie rozpoczęto |
| Dashboard/Pulpit | `main_routes.py` | `api_routes.py` | Kompletna (5 widgetów) | Niska–średnia | Nie rozpoczęto |
| Wizyty (lista + CRUD) | `main_routes.py`? | `appointment_routes.py` (35 jsonify, 0 render) | Prawdopodobnie kompletna | — | **Wymaga audytu** |
| Kalendarz wizyt (tydzień/miesiąc) | `main_routes.py`? | `appointment_routes.py` | Prawdopodobnie kompletna | **Wysoka** (drag&drop, widok siatki) | **Wymaga audytu** |
| Analityka / KPI / Przychody | `main_routes.py` | `analytics_routes.py` (44 jsonify, 0 render) | Prawdopodobnie kompletna | Wysoka (wykresy — patrz `dataviz` skill przy budowie) | **Wymaga audytu** |
| Nieobecności (wnioski) | `absence` blueprint | `absence_routes.py` (40/2) | Prawdopodobnie kompletna | Średnia | **Wymaga audytu** |
| Bilanse urlopowe | `absence_balance` blueprint | `absence_balance_routes.py` (39/1) | Prawdopodobnie kompletna | Średnia | **Wymaga audytu** |
| Import danych / historia | `main_routes.py` | `import_routes.py` (8/0) | Nieznana | Nieznana (prawdopodobnie OCR/plik) | **Wymaga audytu** |
| Użytkownicy (RBAC) | `users/routes.py` (6/4) | częściowo w tym samym pliku | **Częściowa** | Nieznana | **Wymaga audytu** |
| Role (RBAC, `.permission-tile`) | `roles/routes.py` (4/4) | częściowo w tym samym pliku | **Częściowa** | **Wysoka** (siatka uprawnień) | **Wymaga audytu** |
| Ustawienia e-mail/SMS | `main_routes.py` + `sms_routes.py` (15/2) | mieszane | Nieznana | Niska–średnia | **Wymaga audytu** |
| Profil / zmiana hasła | `routes/auth/routes.py` | — | Buduje się w Fazie 0 (auth) | Niska | Część Fazy 0 |
| Booking (publiczne, bez logowania) | `booking_routes.py` (12/1) | częściowo | Nieznana | Nieznana | **Poza zakresem? — patrz `plan.md` §5 pkt 1** |
| Landing/public | `templates/landing`, `templates/public` | brak dedykowanego | — | — | **Poza zakresem? — patrz `plan.md` §5 pkt 1** |
| Mobile API (`mobile_routes.py`) | brak `templates/mobile/` znalezionego | `mobile_routes.py` (15/0) | — | — | **Prawdopodobnie inna aplikacja, nie ten frontend — potwierdzić i wykluczyć** |

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
