---
title: "Deferred Design Tickets — Implementation Plan"
description: "Close the 8 deferred tickets from DESIGN-TOKENS.md plus the expanded mobile-stacked-card mandate: card-ify 13 data tables, retire dead JS, replace Material Icons with inline SVG, tokenize radii, add a CI design-guard, consolidate VARIANT buttons, and add a page_title processor."
status: complete
priority: P2
tags: [ui, responsive, accessibility, design-system, icons, ci, planning]
created: 2026-06-13
updated: 2026-06-14
---

# Deferred Design Tickets — Implementation Plan

> **COMPLETE (2026-06-14).** All 9 phases shipped + deployed to Vultr. All 8 deferred
> tickets closed (see DESIGN-TOKENS.md § "Deferred items — RESOLVED"). 14 tables card
> at ≤640px via shared `.stack-cards`; icon font removed (inline SVG); dead JS deleted;
> CI design-guard live; `page_title` processor + 6 pytest tests; axe 0 critical/serious
> on all key pages. Commits: P01 `8de5235`, P02 `aae15db`/`715d175`, P03 `854272e`/
> `b256bb2`/`fdd58ce`, P04 `ca8ac5c`/`2586eee`, P05 `10f82ea`, P06 `a253886`/`dd915a3`,
> P07 `e776047`, P08 `2c2f669`, P09 `037bb8a`.

## Executive Summary

**The Mission:** Close the 8 deferred tickets in
`plans/260610-ui-usability-fixes/DESIGN-TOKENS.md` § "Deferred items", **with an
expanded mobile-tables mandate** (user remark, 2026-06-13): the stacked-card
pattern that shipped on `clients/list.html` is now applied to **13 data tables**
across the app, not just invoices/appointments.

**The architectural decision that shapes this plan:** the 260610 plan put the
≤640px card recipe in `clients/list.html`'s *page-local* `<style>`. Copying that
~35-line media block into 13 templates would rebuild the exact duplication the last
plan tore down. Instead, **Phase 01 builds ONE shared `.stack-cards` component** in
`static/css/input.css @layer components`; every table phase then opts in with a
class + `data-label` attributes. clients/list.html is migrated onto it first as the
proof. (See ADR-D-01.)

**User-visible win:** 13 tables become readable on phones.
**Hygiene win:** the Material Icons web-font (62 glyphs, ~206 usages, one
render-blocking Google-Fonts request) → inline SVG; `table-utils.js` (loaded
globally, **zero live consumers**, already caused a silent-shadowing bug) deleted.

### User decisions (2026-06-13) — locked

1. **P08 `page_title` processor** — **KEEP** (was optional).
2. **Dead JS** — **DELETE** `table-utils.js` + orphans outright (git preserves them).
3. **Icon sweep** — **single phase** (P06), committed in batches.
4. **Card breakpoint** — **`≤640px`, identical to clients** (consistency over per-page tuning).
5. **Phase order** — **user-value first** (the 3 mobile-card phases lead).
6. **REMARK** — card-ify these 12 additional tables (+ invoices from the original ticket = 13):
   appointments-list, sellers-list, employees-list, absences-requests-list,
   absences-categories-list, absence-balances-table, my-absences-history-list,
   employee-view assigned-services-list, service-categories table,
   formy-zatrudnienia-list, users-list, roles-permissions-list.

---

## The 13 mobile-card tables — grounded inventory (verified 2026-06-13)

Each table's **render approach** dictates where `data-label` goes: JS tables get it
in the `tbody.innerHTML = …map(...)` template literal; Jinja tables get it in the
`{% for %}` loop. All adopt the shared `.stack-cards` class from P01.

| # | Table | File | Render | Anchor | Phase |
|---|---|---|---|---|---|
| — | clients (reference) | `clients/list.html` | JS | `renderClients()` | P01 (migrate to shared) |
| 1 | invoices | `invoices/list_refined.html` | JS | `renderTable()` :1247; thead :880 (8 col) | P01 |
| 2 | appointments | `appointments/list.html` | JS | `renderTable()` :414; thead :168 (10 col) | P01 |
| 3 | sellers | `sellers/list_refined.html` | JS | `renderTable()` :753, `#sellers-tbody` | P02 |
| 4 | employees | `employees/list.html` | JS | `…map()` :727, `#employees-tbody` | P02 |
| 5 | users | `users/list.html` | JS | `…map()` :182, `#users-body`, thead :54 | P02 |
| 6 | roles | `roles/list.html` | JS | `…map()` :85, `#roles-body`, table :50 | P02 |
| 7 | absences-requests | `absences/management.html` | Jinja | `#requests-table` `{% for ab in requests_list %}` :256; thead :246 (6 col) | P03 |
| 8 | absences-categories | `absences/management.html` | Jinja | `{% for cat in categories %}` :581; thead :567 | P03 |
| 9 | absence-balances | `absences/balances.html` | JS | `#balance-tbody` :295 | P03 |
| 10 | my-absences-history | `absences/my.html` | Jinja | `{% for ab in absences %}` :313; table min-width:700px :105 | P03 |
| 11 | employee assigned-services | `employees/view.html` | Jinja | `.service-table` `{% for spec in specs %}` :454 | P03 |
| 12 | service-categories | `services/categories/list.html` | JS | `…map()` :579, `#categories-tbody` (4 col) | P03 |
| 13 | formy-zatrudnienia | `employees/formy_zatrudnienia/list.html` | JS | `…map()` :337, `#formy-tbody` (6 col) | P03 |

Notes: `management.html` has a 3rd table (the "manual" panel) the remark didn't name
— left as-is, noted in P03. `employees/view.html` also has a JS-rendered
`#adj-history-tbody` (price corrections) — not in scope; only the Jinja
`.service-table` is the "assigned services" list.

---

## Other tickets — grounded findings

| Ticket | Verified reality |
|---|---|
| T2 table-utils | `base.html:271` loads it globally; **no template uses its API** (no `.sortable-table`, `resultsTable`, numeric `sortTable(n)`, `.column-search`). `absences/balances.html:425` defines its own `window.filterTable`; `invoices/list_refined.html:1568` its own `exportToCSV()`. Orphans: `static/js/invoices/list.js` (referenced by no template), `static/js/invoices/upload_original.js.bak`. |
| T3 icons | 62 distinct glyphs; 163 occurrences / 25 templates + 43 / 9 JS files. Font `<link>` `base.html:75`; `.toast-* .material-icons` color rules :187–190. |
| T4 radii | 6 hardcoded `border-radius: 2px/3px` in `input.css` (635, 735, 821, 843, 864, 886). |
| T6 CI guard | `.github/workflows/ci.yml` exists (pytest job) — guard = one added step; exclude the 3 standalone auth pages. |
| T7 buttons | 14 page-local `.refined-btn-*` blocks. 3 standalone auth (login/forgot/reset) **keep**. 11 VARIANT base-extending pages consolidate. Global `.refined-btn-sm` already exists. |
| T8 axe | Invoices `empty-table-header` = bare `<th class="col-actions">` :901 (+ `<th>` :1707). Appointments `heading-order`/`region` not in static markup (single `<h1>` :106) → JS-injected; diagnose live in P02-fix folded into P01. |

---

## Ticket → Phase Coverage Map

| # | Deferred ticket | Owning Phase(s) |
|---|---|---|
| 1 | Mobile stacked cards (now 13 tables) | **P01** (shared component + clients/invoices/appointments) + **P02** + **P03** |
| 2 | `table-utils.js` reconciliation (→ deletion) | **P04** |
| 3 | Material Icons → inline SVG | **P05** (infra+shared) + **P06** (sweep + font removal) |
| 4 | Radii → `--radius-*` | **P04** |
| 5 | `page_title` context processor | **P08** |
| 6 | CI grep guard | **P04** |
| 7 | VARIANT button consolidation | **P07** |
| 8 | axe leftovers | **P01** (invoices th + appointments heading/region) |

---

## Phase Table

| Phase | Title | Group | Tickets | Deps |
|:--|:--|:--|:--|:--|
| **01** | Shared `.stack-cards` component + clients/invoices/appointments + axe | mobile-tables | T1 core, T8 | — |
| **02** | People & access tables → cards (sellers, employees, users, roles) | mobile-tables | T1 | P01 |
| **03** | Absences/HR/catalog tables → cards (7 tables) | mobile-tables | T1 | P01 |
| **04** | JS hygiene + radius tokens + CI design-guard | guardrails | T2, T4, T6 | — |
| **05** | Inline-SVG icon system + shared-component conversion | icons | T3a | — |
| **06** | Material Icons page sweep + font removal | icons | T3b | P05 |
| **07** | VARIANT button consolidation | buttons | T7 | P02, P03 |
| **08** | `page_title` context processor | navigation | T5 | — |
| **09** | Full regression verification + docs closeout | verification | gate | all |

**Group ordering rationale (user-value first):** the 3 mobile-card phases (P01–P03)
lead. P01 must precede P02/P03 — it builds the shared component they consume.
P04/P05 are independent quick wins. P06 depends on P05 (needs the icon system). P07
runs after P02/P03 because the VARIANT pages it edits (appointments/list,
absences/my, absences/management, services/categories, formy_zatrudnienia) are
rewritten by the card phases — ordering avoids edit collisions. P08 is the lone
Python phase, independent. P09 gates everything.

---

## ADR-D-01 — One shared `.stack-cards` component (not 13 page-local copies)

**Status:** Accepted (2026-06-13).

**Context:** The 260610 plan (ADR-G-02) shipped the card recipe in
`clients/list.html`'s page-local `<style>`, scoped to `.refined-table`. The remark
expands to 13 tables. Thirteen copies of the media block = the duplication the prior
plan fought.

**Decision:** Build a generic, opt-in `.stack-cards` component in `input.css @layer
components`. A table opts in by adding `class="… stack-cards"`; cells carry
`data-label="…"`; the identity cell gets `cell-name`, the actions cell `cell-actions`,
decorative/low-value cells `cell-hide-sm`. The shared media query keys off **those
marker classes only** (never bare `.refined-table`, so non-target tables are
untouched).

**Cascade consequence (load-bearing):** page-local `<style>` is *unlayered* and beats
`@layer components` on equal specificity. So the override properties (`display`,
`min-width`, `padding`, `border`, `white-space`) in the shared block carry
`!important` — an `!important` *layered* declaration still beats a *normal* unlayered
one. This is the same mechanism the iOS-16px rule already relies on (DESIGN-TOKENS.md
§ "Mobile input-zoom guard"). `::before`/flex props that no page sets on base tables
don't strictly need it but get it uniformly for predictability.

**Container note:** with the table itself reset to `min-width:0; display:block`, it no
longer overflows, so a wrapping `overflow:auto` container has nothing to scroll — the
component works regardless of container structure. An optional `.stack-cards-wrap` on
the container resets its border/background cosmetics (as clients does) but isn't
required for function.

**Consequences:** ~35 lines of CSS once; each table phase is `add class + data-label`.
A future table cards itself in minutes. clients/list.html is refactored onto the
shared class in P01 (deletes its page-local block) to prove parity.

---

## ADR-D-02 — `table-utils.js` reconciliation = deletion

**Status:** Accepted (user decision 2, 2026-06-13).

**Context:** Ticket 2 framed this as "reconcile to one key-based util." Verification
shows the global util has **zero live callers**; every list page already has its own
key-based sorter that syncs `aria-sort` (done in the 260610 sweep).

**Decision:** Delete `table-utils.js` (and the two orphaned JS files). This removes the
shadowing trap permanently rather than papering over it. Each page keeps its small,
working, aria-correct local sorter.

**Consequences:** `base.html` loses one `<script>`; three dead files leave the tree
(git history retains them). No behavior change — verified by a per-page sort/filter
smoke test in P04.

---

## Architectural North Star (unchanged from 260610)

Flask + Jinja2 + TailwindCSS. No React/Supabase/server-actions. Canonical tokens in
`input.css :root`; edit `input.css`, run `npm run build:css`, never hand-edit
`output.css`. Real semantic elements + ARIA state. Don't regress the review's
"Positive Observations" (skip-link, CSRF shim, reduced-motion, local-time dates).

### Security (low surface, must not regress)
- Dynamic table cells already pass through `escapeHtml()`; `data-label` values are
  **static column names** (no user data) → no new escaping needed, but never move a
  raw API string into a label.
- CSRF auto-shim untouched. No new endpoints. P08's processor returns only static
  Polish labels keyed by `request.endpoint` — no user data, no DB.

### Testing reality (ADR-G-03 carries over)
Verification-based: gstack `/browse` + axe-core on **production** (per the standing
directive — no dev server / SSH tunnel). `pytest` only for P08 (the one Python phase).

---

## Standing workflow (every phase)

1. Edit → `npm run build:css` if CSS changed.
2. **Scripted-edit safety rails** (the \x01 incident): replacement *functions* not
   string backreferences; after any scripted/regex edit grep for control chars
   `[\x00-\x08]` and `node --check` every touched inline `<script>` (Jinja stripped).
3. Commit (conventional, scoped) → push `origin/invoices-app`.
4. Deploy to Vultr (`vultr-ssh`: pull, conditional `build:css`, restart
   `my-way-beauty-salon`).
5. Verify on **production** `http://70.34.252.120` via `/browse` with a minted session
   cookie — never password-guess prod accounts, never write to prod DB, never submit
   the public rating form.

---

## Phase Specs (summaries — full detail in each phase file)

### P01 — Shared component + clients/invoices/appointments + axe
- Build `.stack-cards` in `input.css @layer components` (ADR-D-01).
- Refactor `clients/list.html` onto it (add class, drop page-local media block, map
  `trend-cell`→`cell-hide-sm`) — prove pixel parity vs current prod.
- Invoices: `renderTable()` td's get `data-label` (Nr faktury/Sprzedawca/NIP/Data
  wyst./Termin/Kwota/Status), number cell `cell-name`, actions `cell-actions`; add
  `stack-cards` to the table; **T8a** fix the empty `<th>`s (:901, :1707) with
  `<span class="sr-only">`.
- Appointments: same on `renderTable()` (10 cols); **T8b** diagnose + fix the live
  `heading-order`/`region` axe violations at source.
- Verify all three at 375px on prod + axe clean.

### P02 — People & access tables → cards
sellers, employees, users, roles. All JS `.map()` renderers. For each: add
`stack-cards` to the table, `data-label` mirroring its thead, mark name + actions
cells; hide any decorative cell with `cell-hide-sm`. Verify each at 375px on prod.

### P03 — Absences / HR / catalog tables → cards
7 tables (4 Jinja, 3 JS — see inventory). Jinja tables get `data-label` in the
`{% for %}` loop; JS tables in the template literal. Watch the `colspan` empty-state
rows (give them `cell-hide-sm`-style full-width handling). Heaviest phase — commit in
2 batches (absences cluster, then catalog/HR). Verify each at 375px on prod.

### P04 — JS hygiene + radius tokens + CI guard
- Remove `base.html:271` script tag; delete `table-utils.js`, `invoices/list.js`,
  `invoices/upload_original.js.bak`; de-`window.` the balances `filterTable`.
- 6 hardcoded radii → `var(--radius-sm/md)`; rebuild.
- Add a `guard` step to `ci.yml`: fail on
  `rounded-xl|rounded-2xl|from-primary-|to-primary-` in `templates/**` (exclude
  login/forgot/reset). Seed a violation to prove it fails, then remove.
- Smoke-test sort/filter/CSV on every list page on prod.

### P05 — Inline-SVG icon system + shared conversion
- `templates/components/icons.html` Jinja macro `icon(name, class, size)` → `<svg
  viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">` (Material Symbols
  outline paths; all 62 names).
- `static/js/icons.js` `Icons.svg(name, cls)` holding only the ~25 JS-used names
  (header comment → macro is source of truth).
- Convert shared infra: base.html toasts (+ retarget `.toast-* .material-icons`
  rules to `svg`), `modals.js`, `notifications.js`, `keyboard-shortcuts.js`, `ui.js`.

### P06 — Material Icons sweep + font removal
- Scripted sweep (safety rails!) converting all `material-icons` spans → `icon()` /
  `Icons.svg()` across 25 templates + 4 JS files, in 2–3 bisectable commits.
- When `grep material-icons` = 0: drop the font `<link>` (base.html:75) + leftover
  `.material-icons` CSS.
- Per-page render check (no tofu/ligature text); confirm fonts.googleapis.com icon
  request gone.

### P07 — VARIANT button consolidation
- Inventory the 11 page-local `.refined-btn-*` blocks vs globals; extend globals with
  genuinely-shared modifiers (compact density, block); one-offs stay local.
- Remove redundant local blocks; swap classnames. **Keep** auth/login, forgot, reset.
- Before/after screenshots (desktop + 375px) per page.

### P08 — `page_title` context processor
- Context processor: `request.endpoint` → Polish label dict, exposed as `page_title`.
- `base.html` mobile-title default `{{ page_title or '' }}`; the 7 explicit blocks
  still override.
- `pytest`: correct label for known endpoints, empty for unmapped, safe outside
  request context. Full suite + coverage gate before push.

### P09 — Regression verification + docs closeout
- Prod axe on key pages: 0 critical/serious; specifically no `empty-table-header`,
  `heading-order`, `region`.
- 375px pass: all 13 tables card-render; no h-scroll; no input zoom.
- Grep gates: `material-icons`=0, `table-utils`=0, CI guard green, hardcoded
  `2px|3px` radii=0 (outside token defs).
- Docs: DESIGN-TOKENS.md "Deferred items" → "Resolved (260613)"; CLAUDE.md gains the
  icon rule + the `.stack-cards` recipe, drops stale table-utils mentions; update
  `project_design_system_state.md` memory.

---

## Out of Scope (stays deferred)
- Re-architecting per-page sorters into a shared util (moot after ADR-D-02).
- Tables beyond the named 13 (any not listed still h-scroll — new ticket if wanted).
- The `management.html` "manual" panel table (not in the remark).
- Standalone auth pages' visual language.

---

**Next:** phase files `phase-01-…` … `phase-09-…` (generated alongside this plan).
