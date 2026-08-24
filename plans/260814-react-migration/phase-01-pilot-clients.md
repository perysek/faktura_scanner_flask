# Faza 1 — Pilot: moduł Klienci

**Status: ✅ ZAKOŃCZONA I ZATWIERDZONA PRZEZ UŻYTKOWNIKA (2026-08-17)** — szczegóły weryfikacji
(build/lint/code-review + finalny status kryteriów akceptacji) w `implementation-log.md`.

**Cel:** pierwszy pełny moduł na React, na prawdziwych danych, jako sprawdzony wzorzec do
powielenia w Fazie 2. Wybrany, bo ma średnią złożoność (lista + CRUD + widok szczegółów + trochę
logiki pochodnej — trendy wizyt, statystyki), a **backend jest już niemal w 100% gotowy** (patrz
`plan.md` §0) — więc pilot testuje głównie wzorzec frontendowy, nie odkrywa nowych problemów
backendowych po drodze.

## 1.1 Stan obecny (zweryfikowany w kodzie)

### Trasy Jinja (`routes/main_routes.py`, linie 174–213)
```python
GET  /clients                      → clients_list()   → render_template('clients/list.html')
GET  /client/create                → create_client()  → render_template('clients/create.html')
GET  /client/<int:id>              → view_client()     → render_template('clients/view.html', client=...)
GET  /client/<int:id>/edit         → edit_client()     → render_template('clients/edit.html', client=...)
```
Wszystkie za `@login_required` + `@module_permission_required('clients')`.

### Szablony (rozmiar = sygnał złożoności)
| Plik | Linie | Charakter |
|---|---|---|
| `templates/clients/list.html` | 1059 | **Już dziś renderuje tabelę po stronie klienta w JS** (template literals `${...}`) z danych pobranych z `/api/clients` — to NIE jest statyczny Jinja-render, tylko wczesna, ręczna forma tego, co robi React. Kolumny: `full_name` (`cell-name`), `last_visit_date`, `next_visit_date`, `completed_visits`, `no_show_count`, sparkline trendu (`cell-hide-sm`), `cancelled_count` (`cell-hide-lg`), `phone` (`cell-hide-lg`), status badge, akcje. Sortowalne nagłówki (`th-sortable`, `aria-sort`) na 6 kolumnach. Używa `.stack-cards` (mobile). |
| `templates/clients/create.html` | 439 | Formularz — do zmapowania na `form.tsx` primitives |
| `templates/clients/edit.html` | 566 | Formularz — prawdopodobnie duży overlap z `create.html`, do sprawdzenia czy da się złożyć jeden `ClientFormPage` z dwoma trybami zamiast dwóch stron |
| `templates/clients/view.html` | 1114 | Największy plik — prawdopodobnie zawiera historię wizyt/statystyki klienta, nie tylko proste pola. **Nie czytałem go w szczegółach** — pierwszy krok tej fazy (patrz §1.4) |

### Repozytorium (`repositories/clients/client_repository.py`, 402 linie)
Metody: `row_to_client`, `create`, `update`, `get_clients_with_stats(search_query, include_inactive)`,
`update_last_visit`. Plus osobno `client_preference_repository.py` (używane przez
`routes/client_preference_routes.py` — 6 `jsonify`, do doczytania jeśli widok klienta pokazuje
preferencje).

### API JSON — już kompletne (`routes/api_routes.py`, linie 2549–3084)
```
GET    /api/clients                              lista + staty wizyt (search, include_inactive)
GET    /api/clients/<id>
GET    /api/clients/duplicate-check
POST   /api/clients
PUT    /api/clients/<id>
DELETE /api/clients/<id>
POST   /api/clients/<id>/restore
POST   /api/clients/<id>/activate
POST   /api/clients/<id>/deactivate
POST   /api/clients/bulk-update-preferences
GET    /api/clients/visit-trends
GET    /api/clients/statistics
GET    /api/clients/birthdays
```
Wszystkie za `@login_required` + `@module_permission_required('clients', ...)`.

## 1.2 Gap analysis — co faktycznie brakuje

- [ ] **Nic strukturalnego po stronie API.** Jedyne do zweryfikowania: czy `GET /api/clients` ma
      limit/paginację (dziś zwraca prawdopodobnie całą listę naraz, co działało dla renderu JS
      po stronie klienta — dla Reacta to też OK *jeśli* liczba klientów w praktyce jest rozsądna;
      **sprawdzić realny rząd wielkości danych** zanim się założy, że paginacja nie jest potrzebna).
- [ ] Kształt JSON z `GET /api/clients` (pola: `date_of_birth`/`first_visit_date`/`last_visit_date`/
      `created_at`/`updated_at` jako ISO stringi, plus `full_name`, `age`, `completed_visits`,
      `no_show_count`, `cancelled_count`, `visits_last_8w`, `next_visit_date`/`next_visit_time`/
      `next_visit_employee`) — to jest gotowy kontrakt do wygenerowania TS `interface Client` 1:1,
      **bez żadnego projektowania od zera**.
- [ ] `X-Requested-With` nagłówek — istniejące endpointy `/api/*` już zwracają czysty JSON zawsze
      (to osobny blueprint od stron Jinja), więc **nie potrzebują** rozgałęzienia jak auth (Faza 0)
      — React może ich używać od razu, bez zmian backendowych.
- [ ] CORS/dev-proxy — jeśli Vite dev server (`:5173`) i Flask (inny port) są różnymi originami w
      developmencie, `credentials:'include'` wymaga poprawnej konfiguracji `CORS`/proxy (patrz
      `phase-00-foundations.md` §0.1) — to fundament, nie coś specyficznego dla Klientów, ale
      pierwszy moduł jest tym, na którym się to faktycznie sprawdzi end-to-end.

## 1.3 Budowa frontendu

| Strona Jinja | React page | Komponenty z DESIGN.md do użycia |
|---|---|---|
| `clients/list.html` | `ClientsListPage.tsx` | `useApiData` (§18) na `GET /api/clients`; tabela z `.refined-table`/`.stack-cards` (port istniejącego markupu, nie projekt od zera); sortowanie klient-side (dane już są w pamięci, jak dziś) z `aria-sort` sync; sparkline trendu — port istniejącej funkcji `sparklineSvg()` z `list.html` (znaleźć ją, prawdopodobnie inline `<script>` w tym samym pliku) |
| `clients/create.html` + `clients/edit.html` | Jeden `ClientFormPage.tsx` z `mode: 'create' \| 'edit'` | `FormCard` + `FormFieldset`, pola przez `TextField`/`SelectField`/`DateField` itd.; `POST`/`PUT` przez `api.post`/`api.put`; walidacja on-submit (DESIGN.md §7) |
| `clients/view.html` | `ClientDetailPage.tsx` | **Do rozpisania po przeczytaniu pliku (1114 linii) — zbyt duży, by zgadywać strukturę z samej nazwy.** Patrz §1.4 |
| Usuwanie (gdziekolwiek dziś jest `confirmDelete`/`Modals.confirm` w kontekście klienta) | `useConfirm()` wywołanie w `ClientsListPage`/`ClientDetailPage` | DESIGN.md §8.2 — pamiętać o zmianie callback→Promise (patrz `phase-00-foundations.md` §0.7) |

## 1.4 Rzeczy do doczytania przed pisaniem kodu tej fazy (jeszcze nie zrobione w tym audycie)

Poniższe nie zostały przeczytane w szczegółach podczas tego planowania — celowo, żeby nie
przeciążać samego planu; to konkretne zadania na start implementacji Fazy 1, wykonywalne
bezpośrednio w tym repo (nie wymaga zewnętrznego agenta, jeśli implementujesz w tej samej sesji):

1. `templates/clients/view.html` (1114 linii) — pełna struktura: jakie sekcje, czy jest tam
   osadzona historia wizyt/kalendarz, czy `client_preference_routes.py` (6 jsonify) jest tu
   konsumowany.
2. `templates/clients/list.html` — dokładny inline `<script>` z funkcją renderu wiersza i
   `sparklineSvg()`, żeby przenieść logikę 1:1 zamiast odtwarzać ją z pamięci.
3. `client_preference_repository.py` + `routes/client_preference_routes.py` — czy to osobny
   pod-moduł wchodzący w zakres pilota, czy osobna sprawa.

**Gotowy prompt**, jeśli wolisz zlecić to jednorazowo innej sesji/agentowi zamiast robić to jako
pierwszy krok implementacji:

> *"Otwórz `templates/clients/view.html` w całości i opisz jego strukturę sekcja po sekcji (jakie
> dane pokazuje, czy ma zagnieżdżone taby/panele, czy renderuje coś po stronie klienta w JS jak
> `list.html`). Osobno wklej treść inline `<script>` z `templates/clients/list.html` odpowiedzialną
> za renderowanie wiersza tabeli i funkcję generującą sparkline trendu wizyt (szukaj
> `sparklineSvg` lub podobnej nazwy). Na końcu sprawdź `routes/client_preference_routes.py` i
> `repositories/clients/client_preference_repository.py` i powiedz, czy dane stamtąd są używane w
> `clients/view.html` czy `clients/edit.html`."*

## 1.5 Kryteria akceptacji pilota

- [ ] Lista klientów: wyszukiwanie, sortowanie (6 kolumn), stan pusty, tryb mobilny (karty zamiast
      tabeli) — wizualnie i funkcjonalnie nieodróżnialne od `clients/list.html` na oko.
- [ ] Tworzenie/edycja: te same pola, ta sama walidacja (w tym duplicate-check), te same komunikaty
      błędów po polsku.
- [ ] Widok szczegółów: parytet z `view.html` (zakres do potwierdzenia po §1.4).
- [ ] Usuwanie: `useConfirm()` zamiast natywnego `confirm()`, soft-delete + restore działa tak jak
      dziś (`DELETE` + `POST /restore`).
- [ ] 4 motywy przetestowane wizualnie na tym module (nie tylko domyślny).
- [ ] Klawiatura: sortowanie nagłówków, formularz, modal potwierdzenia — pełna obsługa bez myszy.
- [ ] Zmierzony czas budowy tego modułu **zapisany** (do kalibracji szacunku dla pozostałych 14 w
      Fazie 2 — to jedyny sposób, by `module-inventory.md`'s złożoność nie była zgadywaniem).
