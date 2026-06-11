---
title: "Phase 06: Migrate Table Macros + Accessible Sortable Header"
description: "Migrate scrollable_table.html macros onto canonical tokens, make sortable_header keyboard/SR-accessible with aria-sort, and unify on the glyph sort icon (Issue 5-tables + Issue 1-macro + S3)."
skill: "web-design-guidelines"
status: pending
group: "design-system-migration"
dependencies: [P01, P05]
tags: [phase, design-system, accessibility, jinja, css]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 06: Migrate Table Macros + Accessible Sortable Header

**Context:** [[plan|Master Plan]] | **Dependencies:** P01, P05 | **Status:** Pending

---

## Overview

`templates/components/scrollable_table.html` is System A: `table_card` uses `rounded-2xl`, `sortable_header` is a `<th onclick="sortTable(...)">` with a Material icon and **no `tabindex`/`role`/keyboard handler/`aria-sort`** (Issue 1, macro half), badges/empty-states/action-buttons use `slate-*`/`primary-*`. This phase migrates the macros onto canonical tokens (matching P05's language), rebuilds `sortable_header` so the clickable content is a real `<button>` with `aria-sort` reflected on the `<th>`, and adopts the canonical glyph sort-icon (`.th-sort-icon` from P01, Suggestion 3).

**Goal:** Macro-rendered tables look canonical and their sortable headers are fully keyboard/SR operable.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/components/scrollable_table.html` (`table_card`, `table_header_classes`, `sortable_header`, `search_row`, `empty_state`, `status_badge`, `ocr_badge`, `action_button`, `search_toggle_button`, `loading_skeleton`) + token classes in `input.css`. Affects pages using these macros (e.g. invoice scanner tables, settings tables).
- **Server Layer:** None.
- **Database Layer:** None.
- **Integrations:** Sort behavior still calls the page-provided handler (`sortTable(sort_key)` in `static/js/table-utils.js`); we add a11y semantics around it without changing the sort algorithm.

### User Workflow

**Trigger:** A keyboard or screen-reader user wants to sort a macro-rendered table.

**Steps:**
1. User Tabs to a column header; it's a focusable `<button>` with an accessible name (e.g. "Sortuj: Data").
2. Enter/Space triggers the sort.
3. The `<th>` `aria-sort` updates to `ascending`/`descending`; SR announces it; the glyph flips `▲`/`▼`.

**Success Outcome:** Sorting works without a mouse and is announced to assistive tech.

### Problem Being Solved

**Pain Point:** Issue 1 (macro half) — keyboard/SR-inaccessible sorting; Issue 5 (tables) — divergent table styling; Suggestion 3 — mixed sort-icon vocabulary.

**Alternative Approach:** Leaving `<th onclick>` excludes keyboard/SR users from a core admin interaction.

### Integration Points

**Upstream Dependencies:** P01 (`.th-sort-icon`, tokens, radii), P05 (established `.form-*`/token approach + reconciliation pattern).

**Downstream Consumers:** P07 (page sweep verifies all macro tables); P08 mirrors the same a11y pattern on the clients page's hand-rolled headers.

**Data Flow:**
```
sortable_header(label, sort_key, current_sort, current_order)
   └─ <th aria-sort=…> <button onclick="<existing handler>"> label + .th-sort-icon glyph
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Sort handler:** Keep calling the existing `sortTable('{{ sort_key }}')` (or whatever the consuming page wires) and ONLY add a11y semantics — i.e. not refactor the `table-utils.js` sort algorithm this phase?
   - **Context:** `table-utils.js`'s `sortTable(columnIndex,…)` signature vs. the macro passing a string key is a latent mismatch; consuming pages may override `sortTable` or use server-side `?sort=` links.
   - **Assumptions if unanswered:** Yes — wrap with a11y only; do NOT rewrite the sort algorithm. Flag the mismatch for a separate ticket.
   - **Impact:** Rewriting sort logic here would balloon scope and risk regressions on pages we can't all see.

2. **Button vs. tabindex th:** Use a real inner `<button type="button">` (preferred, native keyboard) rather than `tabindex=0 role=button` on the `<th>`?
   - **Assumptions if unanswered:** Inner `<button>` (review's preferred option).
   - **Impact:** `<button>` gets Enter/Space free; `role=button` needs a manual key handler.

3. **aria-sort update for server-sorted tables:** For tables that sort via full-page `?sort=` reload, set `aria-sort` from the macro params (server already knows current sort)?
   - **Assumptions if unanswered:** Yes — `sortable_header` sets `aria-sort` from `current_sort`/`current_order` at render time (correct for server-sort); for client-sort pages the page's JS updates it (document the helper).
   - **Impact:** Covers both sort modes.

### Validation Checklist

- [ ] Handler-scope decision confirmed (a11y-only).
- [ ] P01 (`.th-sort-icon`) + P05 merged.
- [ ] Identify which live pages actually render the `sortable_header` macro (grep) to verify against.

> [!CAUTION]
> Do not change `sortTable` in `table-utils.js` this phase. If a consuming page's sort is broken by the latent columnIndex mismatch, raise it separately — conflating it here risks the a11y win.

---

## Requirements

### Functional

- `sortable_header` renders a focusable `<button>` with an accessible name and reflects `aria-sort` on the `<th>` (`none`/`ascending`/`descending`).
- Sort icon = canonical glyph via `.th-sort-icon` (P01); no Material `unfold_more` in the macro.
- All other macros (`table_card`, badges, empty_state, action_button, search, skeleton) use canonical tokens (flat, 2px, `--color-*`).
- No `rounded-xl`/`rounded-2xl`/`from-primary-`/`slate-*` raw utilities left in `scrollable_table.html` (token classes or token colors instead).

### Technical

- New token classes (`.table-card`, `.table-th`, `.th-sortable`, `.table-badge*`, `.table-action-btn`, etc.) in `input.css @layer components` OR reuse existing `.refined-table` family — prefer extending the existing `.refined-table` system since it's already canonical.
- Keep `aria-label`+`title` on icon action buttons (review praised this — don't regress).
- Rebuild + commit `output.css`.

---

## Decision Log

### Inner `<button>` + `aria-sort` (ADR-06-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** `<th onclick>` excludes keyboard/SR (Issue 1).

**Decision:** Render the header content inside `<button type="button">`; set `aria-sort` on the `<th>`; flip `.th-sort-icon` glyph. Preserve the page-provided onclick handler.

**Consequences:** Native keyboard support; correct SR announcement. Slight markup change to the macro signature consumers ignore.

### Reuse `.refined-table` family (ADR-06-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** A canonical `.refined-table` already exists in `input.css @layer components`.

**Decision:** Migrate macro tables to the `.refined-table` family + token badges/buttons rather than invent parallel `.table-*` classes.

**Consequences:** Macro tables and System-B tables share one stylesheet path. Some macro-specific helpers (sticky header, search row) still need small additions.

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] `git grep -ln "from 'components/scrollable_table.html' import" templates/` → list pages that render the macros; pick 1–2 as references.
- [ ] `/browse` baselines (before) of a reference macro table.
- [ ] Assertions: a `sortable_header` cell contains a focusable `<button>`; pressing Enter triggers sort; `<th aria-sort>` changes; computed `.table-card`/`.refined-table` radius is flat (2–3px).
- [ ] axe baseline on the reference table.
- [ ] Confirm a11y assertions FAIL before (no button, no aria-sort).

### Step 1: Token classes / extend refined-table

- [ ] In `input.css @layer components`, add the macro-specific helpers on top of `.refined-table` (sticky header variant, search-row input, token badges, token action button, flat `.table-card`). Reuse `--color-*`, `--radius-sm/md`. Keep names consistent with existing `.refined-*`.
- [ ] `npm run build:css`.

### Step 2: Rebuild `sortable_header` for a11y + glyph icon

- [ ] Replace the macro body (`scrollable_table.html:67-82`) with:
```jinja
{% macro sortable_header(label, sort_key, current_sort='', current_order='asc', align='left', width_class='') %}
{% set is_active = (current_sort == sort_key) %}
{% set aria = ('ascending' if current_order == 'asc' else 'descending') if is_active else 'none' %}
<th class="th-sortable {{ width_class }} {{ 'sort-active' if is_active else '' }}"
    aria-sort="{{ aria }}" id="th-{{ sort_key }}">
  <button type="button" class="th-sort-btn {{ 'justify-end' if align == 'right' else ('justify-center' if align == 'center' else '') }}"
          onclick="sortTable('{{ sort_key }}')">
    <span>{{ label }}</span>
    <span class="th-sort-icon" id="si-{{ sort_key }}" aria-hidden="true">{{ '▲' if (is_active and current_order == 'asc') else ('▼' if is_active else '▲') }}</span>
  </button>
</th>
{% endmacro %}
```
- [ ] Add the `.th-sort-btn` style (transparent button, inherits th color, flex, cursor) in `input.css`:
```css
.th-sort-btn {
    display: inline-flex; align-items: center; gap: 0.375rem;
    background: none; border: none; padding: 0; margin: 0; font: inherit;
    color: inherit; text-transform: inherit; letter-spacing: inherit; cursor: pointer;
}
.th-sort-btn:focus-visible { outline: 2px solid var(--color-focus-ring); outline-offset: 2px; border-radius: 2px; }
```
- [ ] Document the client-side helper consuming pages should call to keep `aria-sort` in sync when they sort without a reload (set `th.setAttribute('aria-sort', dir === 'asc' ? 'ascending' : 'descending')` and reset others to `none`).

### Step 3: Migrate the remaining macros to tokens

- [ ] `table_card`: `rounded-2xl shadow-sm border border-slate-200` → flat `.table-card` (token border, `--radius-md`); keep `overflow-x-auto scrollbar-thin`.
- [ ] `table_header_classes`: swap `bg-slate-50 text-slate-600` → token (`var(--color-surface)`, `var(--color-ink-subtle)`).
- [ ] `empty_state`: swap slate/primary utilities to tokens; keep the icon + action link (action → token-primary).
- [ ] `status_badge` / `ocr_badge`: map to token semantic colors (`--color-success`, `--color-warning`, `--color-error`) with token-tinted backgrounds (match `clients/list.html` `.status-badge` pattern).
- [ ] `action_button`: keep `aria-label`+`title`; swap hover colors to tokens (`--color-ink`, `--color-error`, etc.) and `rounded-lg`→`--radius-sm`.
- [ ] `search_row` / `search_toggle_button`: token input + token toggle states.
- [ ] `loading_skeleton`: keep `.skeleton` shimmer (already token-agnostic); just flat radius.

### Step 4: Rebuild + verify

- [ ] `npm run build:css`.
- [ ] Reference macro table: keyboard-Tab to a header (focus ring visible), Enter sorts, `aria-sort` flips, glyph flips.
- [ ] `git grep -n "rounded-xl\|rounded-2xl\|from-primary-\|unfold_more" templates/components/scrollable_table.html` → no matches.
- [ ] axe on reference table: 0 critical/serious.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] `sortable_header` content is a focusable `<button>` with accessible name; Enter/Space sorts.
- [ ] `<th aria-sort>` reflects `none`/`ascending`/`descending`.
- [ ] Sort icon is the canonical glyph (no Material `unfold_more`).
- [ ] Macro tables render canonical flat token styling.

**Quality Gates:**
- [ ] No System-A raw utilities left in `scrollable_table.html`.
- [ ] Icon action buttons keep `aria-label`+`title` (no regression).
- [ ] axe 0 critical/serious on a reference macro table.

**Integration:**
- [ ] Consuming pages still sort (handler unchanged); server-sort pages render correct initial `aria-sort`.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Keyboard sort:** Tab to header, Enter — table sorts, SR (VoiceOver/NVDA or `/browse` a11y tree) announces sort state.
  - Expected: operable + announced; Actual: ___
- [ ] **Visual parity:** Macro table matches `clients/list.html` table language.
  - Expected: consistent; Actual: ___

#### Automated Testing
```bash
npm run build:css
git grep -n "unfold_more\|rounded-2xl\|from-primary-" templates/components/scrollable_table.html  # expect empty
# /browse: header button focusable; aria-sort toggles
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (files: `templates/components/scrollable_table.html`, `static/css/input.css`, `static/css/output.css`); `/design-review`; 0 critical.
- [ ] **Code Quality:** Macro signatures backward-compatible (same params).
- [ ] **Error Handling:** N/A.
- [ ] **Security:** Labels are static template text; no injection.
- [ ] **Documentation:** Sort-a11y helper + token badge classes in `DESIGN-TOKENS.md`.
- [ ] **Project Pattern Compliance:** Extends `.refined-table` family; build pipeline.

---

## Dependencies

### Upstream (Required Before Starting)
- P01 (`.th-sort-icon`, tokens), P05 (token-class approach).

### Downstream (Will Use This Phase)
- P07 (sweep), P08 (mirror a11y pattern on clients headers).

### External Services
- None.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification passes (reference tables)
- [ ] Code + design review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `style(tables): token migration + accessible sortable header (phase 06)`

---

## Notes

### Technical Considerations
- The latent `sortTable(columnIndex)` vs. `sortTable(sort_key)` mismatch in `table-utils.js` is NOT fixed here (a11y-only scope). Raise as a separate ticket if a consuming page's sort is found broken.
- `aria-sort` belongs on the `<th>`, not the `<button>` — keep it there.

### Known Limitations
- For client-side-sorted macro tables, the page JS must update `aria-sort` after sorting; documented helper provided but each such page must call it (verified in P07 for the ones that exist).

### Future Enhancements
- Reconcile the `table-utils.js` sort to accept a sort-key and update `aria-sort` centrally, so consuming pages need no per-page glue.

---

**Previous:** [[phase-05-migrate-form-fields|Phase 05]]
**Next:** [[phase-07-page-sweep-consistency|Phase 07: Page-sweep migration & consistency verification]]
