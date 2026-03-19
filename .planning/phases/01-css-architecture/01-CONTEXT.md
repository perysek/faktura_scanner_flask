# Phase 1: CSS Architecture - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Przenieść wszystkie wspólne definicje klas typograficznych (`.page-title`, `.page-subtitle`, `.stat-value`, `.stat-label`) z 38+ indywidualnych szablonów Jinja2 do jednego miejsca w `static/css/input.css`. Po tej fazie żaden szablon nie powinien redefiniować tych 4 klas — używają globalnej definicji lub jej nie nadpisują. Zmiany muszą być wizualnie neutralne lub poprawić spójność.

</domain>

<decisions>
## Implementation Decisions

### Skala .page-title
- Ujednolicić do 1.75rem na wszystkich stronach włącznie z kalendarami (calendar_month.html, calendar_week.html — teraz 1.375rem)
- font-family: var(--font-display) wchodzi do globalnej definicji (eliminuje pominięcie w auth/change_password.html)
- margin-bottom NIE wchodzi do globalnej definicji — każdy szablon definiuje spacing kontekstowo

### Skala .stat-value
- Standaryzować na 1.25rem globalnie (spójne z dashboard/sellers — subdued, czytelny styl)
- Szablony z 1.75rem (clients/list, employees/list) i 1.5rem (income/dashboard) zostaną zaktualizowane do 1.25rem

### Zakres globalizacji
- Tylko 4 klasy: .page-title, .page-subtitle, .stat-value, .stat-label
- Klasy unikalne per-feature (np. .coverage-value, .summary-value, .appointment-client) zostają lokalnie
- Cel: eliminacja duplikatów w 38+ szablonach, nie nadmierny refaktor

### Claude's Discretion
- Kolejność usuwania lokalnych definicji po ich globalnym dodaniu (można grupować per-feature lub per-alfabetycznie)
- Jak obsłużyć szablony, które rozszerzają globalną definicję z dodatkowym stylem (np. dodają color lub margin) — drobne override'y zostawiamy lokalnie

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `static/css/input.css` — już istnieje z blokiem `@layer base { :root { ... } }` i rozbudowanymi CSS custom properties; jest to właściwe miejsce na nowe `@layer components { ... }` z klasami typografii
- `static/css/output.css` — plik kompilowany przez Tailwind (`npm run build`); nie edytować bezpośrednio
- `tailwind.config.js` — konfiguruje brand-500 (#c9a227) i inne tokeny; phase nie wymaga zmian tutaj

### Established Patterns
- Wszystkie szablony definiują style w bloku `<style>` w `{% block styles %}` wewnątrz `<head>`
- `base.html` dostarcza layout i bloki stylów, strony dziedziczą przez `{% extends "base.html" %}`
- CSS custom properties używane konsekwentnie (`var(--color-ink)`, `var(--font-display)`)
- Tailwind build: `npm run build` → `npm run watch` (z package.json)

### Integration Points
- Po dodaniu klas do `input.css` → `npm run build` generuje nowe `output.css`
- Szablony używają `<link href="{{ url_for('static', filename='css/output.css') }}">`
- 38 szablonów z lokalnymi definicjami `.page-title` do oczyszczenia (grep: `\.page-title\s*{`)
- Zmiana skali w .stat-value dotknie: clients/list.html (1.75rem→1.25rem), employees/list.html (1.75rem→1.25rem), income/dashboard.html (1.5rem→1.25rem)

</code_context>

<specifics>
## Specific Ideas

Brak specyficznych referencji wizualnych — otwarte na standardowe podejście. Kluczowe wymagania:
- TYPO-01: Jeden blok `:root`/`@layer components` w input.css zamiast 45 duplikatów
- TYPO-02: .page-title = 1.75rem wszędzie
- TYPO-03: .stat-value = 1.25rem wszędzie

</specifics>

<deferred>
## Deferred Ideas

Brak — dyskusja pozostała w granicach Phase 1. Klasy `.section-title` i `.form-label` rozważane ale odroczone do kolejnych milestoneów.

</deferred>
