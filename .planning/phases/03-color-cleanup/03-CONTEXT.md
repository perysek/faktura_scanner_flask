# Phase 3: Color Cleanup - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Wyeliminować wszystkie hardcoded hex kolory z szablonów Jinja2 i plików JS, zastępując je istniejącymi CSS custom properties (`var(--color-accent)`, `var(--color-status-in-progress)` itd.) lub Tailwind token classes (`text-brand-500`). Po tej fazie `#c9a227` i `#d97706` nie powinny pojawiać się w żadnym szablonie ani pliku JS (z wyjątkiem superadmin_edit*.html, który jest celowo wyłączony).

</domain>

<decisions>
## Implementation Decisions

### Token Strategy
- `var(--color-accent)` CSS custom property jest primary token dla brand gold (#c9a227) — spójne z Phase 1 decision (CSS custom properties over Tailwind)
- `#d97706` (amber/warning) to osobny status token `var(--color-status-in-progress)`, nie brand color — zamienić na istniejący CSS var
- Tailwind `brand-500 = #c9a227` w `tailwind.config.js` zostaje jako compile-time duplikat — Tailwind config nie może referować CSS vars
- Inline SVG `stroke="#c9a227"` (users/list.html) zamienić na `stroke="currentColor"` + parent `class="text-brand-500"` — standard Tailwind pattern

### Scope & Boundaries
- `superadmin_edit.html` i `superadmin_edit_table.html` WYŁĄCZONE ze scope — per COL-03 (v3.0): "Power Panel do osobnego CSS, celowa rozbieżność"
- Auth templates (login, profile, forgot_password, reset_password) wymagają osobnej uwagi — login.html nie dziedziczy z base.html, standalone CSS
- Pliki JS w `static/js/` wchodzą w scope — `calendar.html` JS ma `#d97706` do zamiany
- `output.css` (compiled Tailwind) ignorować — generowany automatycznie

### Replacement Approach
- Inline style hex → `style="color: var(--color-accent)"` — minimalna zmiana, spójne z istniejącym wzorcem
- `<style>` block hex → `color: var(--color-accent)` — CSS custom properties
- JS hex stringi (calendar.html coverage bar) → `getComputedStyle(document.documentElement).getPropertyValue('--color-status-in-progress')`
- `npm run build` po zmianach jeśli klasy Tailwind w szablonach się zmienią

### Claude's Discretion
- Kolejność zmian per-template (grupowanie per-feature lub per-template)
- Obsługa edge case'ów z kolorami nie objętymi istniejącymi tokenami

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `static/css/input.css` — centralny plik CSS z `--color-accent: #c9a227` i `--color-accent-muted` w `@layer base :root`
- `tailwind.config.js` — `brand-500: '#c9a227'` z pełną skalą 50-900, utility classes `text-brand-500`, `bg-brand-100` itp.
- Istniejące status colors: `--color-status-in-progress: #d97706`, `--color-status-scheduled: #2563eb` itd. w input.css
- `invoices/list_refined.html` — wzorzec prawidłowego użycia `var(--color-accent)` w inline styles

### Established Patterns
- Szablony definiują style w `{% block styles %}` wewnątrz `<head>`
- CSS custom properties używane konsekwentnie w większości szablonów (`var(--color-ink)`, `var(--font-display)`)
- Tailwind build: `npm run build` → output.css
- Auth login.html ma standalone style (nie dziedziczy z base.html)

### Integration Points
- Znalezione hardcoded hex:
  - `users/list.html:86` — `stroke="#c9a227"` w SVG
  - `appointments/calendar.html:737` — `#d97706` w JS coverage bar
  - `appointments/superadmin_edit.html:20` — `--pp-warning: #d97706` (OUT OF SCOPE)
  - `appointments/superadmin_edit_table.html:19,308` — `#d97706` (OUT OF SCOPE)
- `static/js/invoices/list.js` — już używa `var(--color-accent)` prawidłowo
- Po zmianach klas Tailwind → `npm run build`

</code_context>

<specifics>
## Specific Ideas

Brak specyficznych referencji wizualnych. Wymagania:
- COL-01: Eliminacja ~80 hardcoded hex z szablonów (auth, form, error templates)
- COL-02: `brand-*` Tailwind tokeny lub `var(--color-accent)` zamiast `#c9a227` inline

</specifics>

<deferred>
## Deferred Ideas

- COL-03 (v3.0): Superadmin "Power Panel" do osobnego CSS — dokumentacja celowej rozbieżności
- Ewentualna konsolidacja `--color-accent` i `brand-500` do jednego źródła prawdy (wymaga Tailwind v4 lub CSS-in-JS)

</deferred>
