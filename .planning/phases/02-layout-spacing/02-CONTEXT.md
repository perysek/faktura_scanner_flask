# Phase 2: Layout & Spacing - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Zmienić `base.html` tak żeby `#main-content` nie narzucał padding (zmiana `p-2` → `p-0`), a każda strona definiuje własny padding na swoim wrapperze. Ujednolicić skalę `max-width` across all templates: 900px dla formularzy/detail, 1400px dla list, full-width dla kalendarzy i dashboard. Eliminuje wszystkie 13 `!important` padding override'ów.

</domain>

<decisions>
## Implementation Decisions

### Zmiana base.html
- Zmienić `p-2` na `p-0` w `#main-content` (linia 44 w `base.html`)
- Strony definiują własny padding na swoim wrapperze, nie walczą z base.html
- Error pages (404, 500) naturalnie korzystają z `p-0` — ich fullscreen layout jest prawidłowy
- Wymagany manualny spot-check wizualny 5 kluczowych stron po zmianie

### Skala max-width
- **Formularze** (create/edit): 900px — ujednolicenie (clients/create ma teraz 800px → zmiana na 900px)
- **Detail/view strony** (clients/view, appointments/view, employees/view): 900px
- **Listy** (clients, employees, services, sellers, invoices): 1400px
- **Kalendarze + dashboard**: brak max-width (full-width) — per wymaganie SPAC-02
- **Sellers/edit superadmin**: traktujemy jako specjalny przypadek — bez zmian (własny full-width layout)

### Implementacja max-width
- Max-width jako lokalny wrapper per-template (nie nowe globalne klasy)
- Szablony które nie mają żadnego max-width a są formularzami/views — dostają 900px wrapper
- Istniejące inline `max-width` w szablonach — ujednolicić do skali, nie tworzyć nowych klas

### Claude's Discretion
- Kolejność zmian: najpierw base.html, potem szablony grupowane per-feature
- Dokładna implementacja wrappera (inline style vs Tailwind utility) per-template

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `templates/base.html` linia 44: `<main class="flex-1 overflow-auto p-2" id="main-content">` — jedyna zmiana w base.html
- Już istniejące wzorce max-width: `clients/list.html` (1400px), `clients/view.html` (900px) — referencje dla innych szablonów
- Tailwind `p-0`, `mx-auto` — utility klasy dostępne

### Established Patterns
- Szablony definiują layout w `{% block styles %}` lub inline style na pierwszym divie w `{% block content %}`
- Wzorzec: `<div style="max-width: Xpx; margin: 0 auto; padding: 1rem 1.5rem;">` — stosować konsekwentnie
- `padding: 1rem 1.5rem` to najczęstszy override stosowany przez szablony z `!important`

### Integration Points
- `base.html` zmiana `p-2` → `p-0` dotyczy WSZYSTKICH szablonów — visual regression risk HIGH
- 13 szablonów z `#main-content { padding: ... !important }` do oczyszczenia po zmianie base.html
- Szablony z `padding: 0 !important` (error, superadmin_edit): zostają bez zmian po p-0
- Szablony bez żadnego max-width do audytu: `employees/create`, `employees/edit`, `services/create`, `services/edit`, `roles/*`, `users/*`, `settings/*`

</code_context>

<specifics>
## Specific Ideas

Brak specyficznych referencji wizualnych. Wymagania:
- SPAC-01: Brak `!important` w computed styles dla `#main-content` padding
- SPAC-02: Spójna skala max-width (formularze 900px, listy 1400px, kalendarze full-width)

</specifics>

<deferred>
## Deferred Ideas

Globalne klasy CSS (.page-wrapper-form, .page-wrapper-list) rozważane ale odroczone — per-template wrapper jest wystarczający i mniej ryzykowny dla tej fazy.

</deferred>
