# DESIGN-TOKENS.md — Canonical Token System of Record

**Status:** Ratified (Phase 01, 2026-06-11)
**Source of truth:** `static/css/input.css :root` (edit there, run `npm run build:css`, never hand-edit `output.css`)
**Reference implementation:** `templates/clients/list.html` + the `@layer components` `.refined-*` classes ("System B")

## Canonical system

System B ("refined") is canonical per ADR-G-01. Its language: flat fills, 2–3px radii,
CSS-variable colors, text glyphs over icon fonts, `Inter` typography. System A
(gradient buttons, `rounded-xl`/`rounded-2xl`, raw `slate-*`/`primary-*` utilities,
Material Icons) is legacy and gets migrated by P05–P07.

## Token groups (`input.css :root`)

### Text (3-tier ink hierarchy)
| Token | Value | Use |
|---|---|---|
| `--color-ink` | `#1a1a1a` | Primary text; canonical flat primary-button fill |
| `--color-ink-muted` | `#525252` | Secondary text; primary-button hover fill |
| `--color-ink-subtle` | `#6b6b6b` | Helper text, placeholders, KPI labels (WCAG AA ≥4.5:1) |

### Surface
| Token | Value | Use |
|---|---|---|
| `--color-surface` | `#fafafa` | Row hover, subtle panels |
| `--color-surface-warm` | `#f7f6f3` | Page background |

### Border
| Token | Value | Use |
|---|---|---|
| `--color-border` | `#e8e6e1` | Inputs, cards, table heads |
| `--color-border-subtle` | `#f0eeea` | Row dividers, faint separators |

### Radii (added Phase 01)
| Token | Value | Use |
|---|---|---|
| `--radius-sm` | `2px` | Inputs, buttons, badges |
| `--radius-md` | `3px` | Cards, modals |

Consume these instead of hardcoding `2px`/`3px` or Tailwind `rounded-xl`/`rounded-2xl`.

### Brand / accent
| Token | Value | Use |
|---|---|---|
| `--color-accent` | `#c9a227` | DECORATIVE gold only — logo flourish, hover marks |
| `--color-accent-muted` | `rgba(201,162,39,.12)` | Gold tint backgrounds |
| `--color-focus-ring` | `#2563eb` | FUNCTIONAL accent — focus rings, links |

### Semantic
`--color-success` (#2d6a4f forest = text/badges/"paid"), `--color-success-action`
(#10b981 emerald = confirm/save fills) + `-dark`, `--color-warning` (#9a6700),
`--color-error` (#9b2c2c), `--color-info` (#1e6091), `--color-purple` family.
Two greens are intentional (F-008) — do not collapse them.

### Status (appointment lifecycle)
`--color-status-{scheduled|confirmed|in-progress|completed|cancelled|no-show}`
each with `-bg`/`-badge` (and some `-dark`) variants. Use for badges/calendar chips.

### Info panel
`--color-info-bg/-border/-text/-text-dark` (blue tones) for inline informational panels.

### Chart palette
`--color-chart-{blue|green|orange|red|purple|pink|teal|amber|slate|sky}` + `--color-chart-blue-dark`.

### Star / rating
`--color-star-filled` (#f59e0b), `--color-star-empty` (#d1d5db).

### Typography
`--font-display` / `--font-body` = `'Inter', system-ui, sans-serif`.
Scale convention (from System B): table cells 0.8125rem, th labels 0.6875rem
uppercase tracked, page titles via `.page-title`, helper text 0.75rem.

### Easing
`--ease-out-expo` `cubic-bezier(0.16,1,0.3,1)`, `--ease-out-quart` `cubic-bezier(0.25,1,0.5,1)`.

### Sidebar
`--sidebar-bg/-bg-deep/-text/-text-hover/-text-active/-heading/-border/-hover-bg/-active-bg/-active-border` — dark navy drawer palette.

## Conventions ratified in Phase 01

### Flat primary button (no new var needed)
Canonical primary fill = `--color-ink`, hover = `--color-ink-muted`, white text,
`--radius-sm`. Reference: the flat `.refined-btn-primary` in `clients/list.html`
(NOT the gradient `@apply` version currently at `input.css` `.refined-btn-primary`
— P07 reconciles the global class to flat).

### Sort icon (S3 / ADR-01-01)
Canonical = text glyphs: `▲` asc / `▼` desc / dimmed `▲` unsorted, rendered in a
`.th-sort-icon` span inside a `.th-sortable` header. Shared styling now lives in
`input.css @layer components`. **Hand-off:** `clients/list.html` keeps a duplicate
page-local copy until P08 removes it after confirming the shared class is live.
Material `unfold_more`/`expand_less`/`expand_more` icons in the table macro are
replaced by P06.

### Mobile input-zoom guard (Issue 2 / ADR-01-02)
Global rule in `@layer base`: at `max-width: 1023px`, all `input`/`select`/
`textarea`/`.ss-trigger`/`.ss-search`/`.refined-input` are forced to
`font-size: 16px !important`. 16px is the exact iOS Safari threshold — never
lower it to 15px. `!important` is load-bearing: page-local `<style>` blocks are
unlayered CSS and would otherwise beat the layered rule. Desktop (≥1024px)
keeps dense 13–14px type. Do not set form-control font sizes below 16px in
page styles expecting them to apply on mobile — they won't.

## Canonical form components (added Phase 05)

`input.css @layer components` — used by all `form_fields.html` macros:

| Class | Role |
|---|---|
| `.form-label` | Field label (0.8125rem, ink-muted) |
| `.form-input` / `.form-select` / `.form-textarea` | Flat controls: token border, `--radius-sm`, refined focus ring |
| `.form-card` | Section card: `--radius-md`, token border, subtle shadow |
| `.form-btn-primary` | Flat ink fill, hover ink-muted + lift |
| `.form-btn-secondary` | White, token border; **Cancel renders as `<a href>` with this class** (Issue 8) |
| `.form-paste-btn` | OCR paste affordance |

Notes: readonly/disabled styling lives on `.form-input[readonly]`/`:disabled` — do not
re-add `bg-slate-50` conditionals. Checkboxes use `accent-color: var(--color-ink)`.

## Accessible sortable header (added Phase 06)

Pattern (see `scrollable_table.html` `sortable_header` for the reference):
`<th class="th-sortable" aria-sort="none|ascending|descending">` wrapping a
transparent `.th-sort-btn` `<button type="button">` that carries the label +
`.th-sort-icon` glyph (`aria-hidden`). Native Enter/Space; `:focus-visible` ring.

Client-sorted pages must sync `aria-sort` after each sort:
```js
th.setAttribute('aria-sort', dir === 'asc' ? 'ascending' : 'descending');
// + reset all sibling .th-sortable to 'none'
```

**Inventory (2026-06-11):** 47 `<th onclick>` headers remain across 8 hand-rolled
pages (appointments/list, superadmin_edit_table, clients/list, employees/list,
invoices/list_refined, sellers/list_refined, services/list, services/categories).
Clients = P08; the rest are converted during the P07 sweep using this pattern.

## Mobile stacked-card table pattern (added Phase 09)

Reference implementation: `templates/clients/list.html` `@media (max-width: 640px)`.
Recipe for any wide data table (invoices/appointments adopt this in a follow-up):

1. In the row renderer, add `data-label="Kolumna"` to every generic `<td>`;
   mark the identity cell `class="cell-name"` and the buttons cell `class="cell-actions"`.
2. Add the ≤640px media block: container `overflow: visible`; table/thead/tbody/tr/td
   → `display: block` (thead `display: none`); each `td` becomes a flex row with
   `td::before { content: attr(data-label) }` as the label; `cell-name` = card header
   (no label, bottom border), `cell-actions` = footer (`::before { content: "Akcje" }`).
3. Hide decorative cells (e.g. sparkline `trend-cell`) on cards.
4. Relax any `min-width` on the table inside the media query only.

One DOM, CSS-only — desktop rendering is untouched (`data-label` is inert above 640px).

## Build pipeline

```
static/css/input.css  ──npm run build:css──▶  static/css/output.css (minified)
                                                   └─ asset_url() content-hash cache-busts
```

- `npm run watch:css` during development.
- `output.css` is generated — never edit it by hand; changes are overwritten.

## Deferred (tracked for P11 tickets)

- Convert hardcoded `2px`/`3px` radii throughout `input.css` to `--radius-*` (cosmetic).
- Full Material Icons → inline SVG migration outside sort headers.
- `table-utils.js` `sortTable(columnIndex)` vs macro `sort_key` mismatch.
