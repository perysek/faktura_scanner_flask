# Phase 4: Accessibility & UX Polish - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Dodać atrybuty dostępności (aria-label, aria-live, skip-navigation) do wszystkich interaktywnych elementów, retry actions w stanach błędu dla async komponentów, naprawić routing CTA na stronach 404/500, oraz poprawić copywriting (diacritic fix, tekst "Powrót na górę"). Po tej fazie każdy element interaktywny jest osiągalny klawiaturą i czytnikiem ekranu, a każdy stan błędu oferuje recovery action.

</domain>

<decisions>
## Implementation Decisions

### Aria Labels & Skip Navigation
- Wszystkie icon-only buttons (nawigacja kalendarza prev/next, modal close, flash dismiss) dostają `aria-label` dopasowany do widocznego tooltip text
- Skip-navigation link: ukryty link na początku `base.html` z `class="sr-only focus:not-sr-only"` — standard Tailwind a11y pattern, linkujący do `#main-content`
- `aria-live="polite"` regions na kontenerach async treści: calendar day view, client list, appointment list
- `login.html` (standalone, bez sidebaru) NIE dostaje skip-nav — niepotrzebny

### Error States & Retry Actions
- Retry button "Spróbuj ponownie" widoczny w error state, wywołuje `location.reload()` lub re-fetch endpointu
- Retry dodany do: calendar day view, client list, appointment list — per UX-01
- 404 CTA: warunkowy per rola — accountant → `main.invoices_list`, reszta → `main.dashboard` (Jinja if na `current_user.role`)
- 500 CTA: ta sama logika warunkowa co 404

### Copywriting Fixes
- `analytics/dashboard.html`: "Idź na początek" → "Powrót na górę" — per COPY-01
- `sellers/edit.html` line 416: "Ladowanie..." → "Ładowanie..." (fix brakującego diakrytyku ą) — per UX-03
- Nie skanujemy szerzej pod kątem diakrytyków — UX-03 wskazuje konkretnie te 2 pliki

### Claude's Discretion
- Dokładna implementacja retry logic (reload vs re-fetch) per-komponent
- Styl wizualny retry buttona (powinien pasować do istniejącego design systemu)
- Dokładna lista icon-only buttons do zaudytowania (planner zidentyfikuje z codebase scout)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `base.html` — target dla skip-navigation link, ma `id="main-content"` na `<main>`
- `templates/components/flash_messages.html` — ma 2 atrybuty aria, target dla dismiss button aria-label
- `templates/components/confirm_modal.html` — ma 2 atrybuty aria, close button potrzebuje aria-label
- Tailwind `sr-only` i `focus:not-sr-only` klasy dostępne (nie wymaga dodatkowego CSS)

### Established Patterns
- 66 istniejących atrybutów aria w 20 plikach — nie zaczynamy od zera
- Async content ładuje się przez JavaScript fetch → innerHTML replacement
- Error states zazwyczaj brak retry — po prostu wyświetlają komunikat
- Calendar navigation używa `<button>` z ikonami SVG (prev/next month/week)

### Integration Points
- `base.html` — skip-nav link musi być PIERWSZYM dzieckiem `<body>` (przed sidebar)
- Calendar views (calendar.html, calendar_week.html, calendar_month.html) — icon buttons do zaudytowania
- `templates/errors/404.html` line 103 i `500.html` line 103 — CTA linkujące do `main.invoices_list`
- `templates/clients/list.html` — async loading, potrzebuje aria-live + retry
- `templates/appointments/list.html` — async loading, potrzebuje aria-live + retry

</code_context>

<specifics>
## Specific Ideas

- A11Y-01: aria-label MUSI pasować do widocznego tooltip text (np. button z tooltip "Poprzedni miesiąc" → `aria-label="Poprzedni miesiąc"`)
- A11Y-02: aria-live na kontenerze, nie na poszczególnych elementach wewnątrz
- UX-02: Warunek Jinja: `{% if current_user.is_authenticated and current_user.role == 'accountant' %}main.invoices_list{% else %}main.dashboard{% endif %}`
- COPY-01: Dokładny tekst: "Powrót na górę" (nie "Do góry", nie "Na górę")

</specifics>

<deferred>
## Deferred Ideas

- A11Y-04 (v3.0): Focus trap w modal dialogs
- A11Y-05 (v3.0): Pełny screen reader test
- Retry na WSZYSTKICH async komponentach (nie tylko 3 z UX-01)

</deferred>
