---
title: "Phase 01: Shared .stack-cards component + clients/invoices/appointments + axe"
description: "Build the reusable @layer-components stacked-card system, migrate clients/list.html onto it as the proof, apply it to invoices and appointments, and clear the two named axe leftovers (T8)."
skill: "web-design-guidelines"
status: pending
group: "mobile-tables"
dependencies: []
tags: [phase, responsive, mobile, design-system, accessibility]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 01: Shared `.stack-cards` component + clients/invoices/appointments + axe

**Context:** [[plan|Master Plan]] | **Dependencies:** none | **Status:** Pending

---

## Overview

The 260610 plan proved the ≤640px stacked-card pattern on `clients/list.html`, but
buried it in that page's local `<style>`. This phase **extracts it into one shared
`.stack-cards` component** in `static/css/input.css @layer components` (ADR-D-01), so
the other 12 tables (P02–P03) opt in with a class + `data-label` attributes instead
of copy-pasting media CSS. clients/list.html is refactored onto the shared component
first — it already works, so it's a zero-risk proof of parity. Then invoices and
appointments adopt it, and the two named axe violations (T8) are fixed in the same
files.

**Goal:** A generic, opt-in card component exists; clients (proof), invoices, and
appointments all render as labelled cards at ≤640px with no horizontal scroll; axe
reports 0 critical/serious on all three, with no `empty-table-header`,
`heading-order`, or `region` on invoices/appointments.

---

## Context & Workflow

### How This Phase Fits

- **CSS Layer:** `static/css/input.css @layer components` — new `.stack-cards` block.
- **UI Layer:** `clients/list.html` (refactor), `invoices/list_refined.html`,
  `appointments/list.html`.
- **Server/DB:** none.

### Problem Being Solved

Issue 4 (mobile h-scroll) on the two highest-traffic tables, the dead-end of a
per-page card recipe, and two sub-serious axe findings (T8) that live in these exact
files.

### Integration Points

- **Downstream:** P02 and P03 consume `.stack-cards` — its API (marker classes) is
  frozen at the end of this phase.

---

## Prerequisites & Clarifications

### Questions for User
1. **clients refactor:** OK to replace clients/list.html's page-local media block with
   the shared class (must look identical)?
   - **Assumption if unanswered:** Yes — it's the parity proof; verified by before/after
     screenshots at 375px.
2. **invoices skeleton rows** (static `<td><div class="skeleton-bar">` :920–949): on
   cards, show as cards or hide?
   - **Assumption:** hide via `cell-hide-sm` on the skeleton `<tr>`s (per-cell skeleton
     bars are meaningless as card rows); the JS empty/loaded state replaces them anyway.

---

## Implementation

### Step 0 — Define verification (first)
- `/browse` at 375px on prod for clients, invoices, appointments after deploy.
- axe-core (CDN inject) on each: 0 critical/serious; assert absence of
  `empty-table-header` (invoices), `heading-order`/`region` (appointments).
- Desktop (≥1024px) screenshots unchanged vs current prod.

### Step 1 — Shared component in `input.css @layer components`

Add (inside the existing `@layer components { … }`). `!important` on the override
props is load-bearing (ADR-D-01 — beats page-local unlayered table CSS):

```css
/* ── Mobile stacked-card tables (ADR-D-01) ──────────────────────────────
   Opt in: add `stack-cards` to a <table>; cells carry data-label="…";
   identity cell = .cell-name, actions cell = .cell-actions, decorative
   cells = .cell-hide-sm. Keyed off marker classes only — never bare
   .refined-table — so non-opted tables are untouched. !important beats
   page-local unlayered <style> (same cascade basis as the 16px rule). */
@media (max-width: 640px) {
  table.stack-cards { min-width: 0 !important; display: block !important; }
  table.stack-cards thead { display: none !important; }
  table.stack-cards tbody { display: block !important; }
  table.stack-cards tbody tr {
    display: block !important;
    background: white; border: 1px solid var(--color-border);
    border-radius: var(--radius-sm); padding: 0.75rem 1rem;
    margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,.04);
  }
  table.stack-cards td {
    display: flex !important; justify-content: space-between; align-items: center;
    gap: 1rem; padding: 0.375rem 0 !important; border: none !important;
    white-space: normal !important; max-width: none !important; overflow: visible;
  }
  table.stack-cards td::before {
    content: attr(data-label); font-size: 0.6875rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--color-ink-subtle); flex-shrink: 0;
  }
  table.stack-cards td.cell-name {
    padding-bottom: 0.5rem !important; margin-bottom: 0.25rem;
    border-bottom: 1px solid var(--color-border-subtle) !important;
  }
  table.stack-cards td.cell-name::before { content: none; }
  table.stack-cards td.cell-actions { padding-top: 0.5rem !important; }
  table.stack-cards td.cell-actions::before { content: "Akcje"; }
  table.stack-cards td.cell-hide-sm { display: none !important; }
  /* Full-width empty-state / colspan rows stay as one block, no label */
  table.stack-cards td.cell-empty { display: block !important; }
  table.stack-cards td.cell-empty::before { content: none; }
}

/* Optional: reset wrapper cosmetics so cards aren't boxed twice */
@media (max-width: 640px) {
  .stack-cards-wrap { overflow: visible !important; border: none; box-shadow: none; background: transparent; }
}
```

Run `npm run build:css`.

### Step 2 — Migrate clients/list.html (proof)
- Add `stack-cards` to the `<table class="refined-table">`; add `stack-cards-wrap` to
  its `.table-container`.
- Delete the page-local `@media (max-width: 640px)` block (lines ~397–433).
- The sparkline cell `class="trend-cell"` → add `cell-hide-sm` (replaces the old
  `td.trend-cell{display:none}` rule). `cell-name`/`cell-actions` already present.
- Verify the empty-state `<td colspan>` rows (renderSkeleton / error / empty) get
  `class="cell-empty"` so they render full-width as a card.

### Step 3 — Invoices (`invoices/list_refined.html`)
- Add `stack-cards` to the data table (the one with thead at :880); `stack-cards-wrap`
  on its container.
- In `renderTable()` (:1247) row template literal, add to each `<td>`:
  `data-label="Nr faktury|Sprzedawca|NIP|Data wyst.|Termin|Kwota|Status"` (mirror
  thead order); number cell `class="cell-name"`, actions cell `class="cell-actions"`.
- Static skeleton `<tr>`s (:920–949): add `cell-hide-sm` to each `<td>` (or `display:none`
  the whole skeleton block on ≤640px).
- Any empty/colspan state rows → `class="cell-empty"`.
- **T8a:** `<th class="col-actions"></th>` (:901) → add `<span class="sr-only">Akcje</span>`;
  the bare `<th>` (:1707, duplicates table) → `<span class="sr-only">Zaznacz</span>`.
  Confirm `sr-only` survives the Tailwind build in this file (it's a new utility here).

### Step 4 — Appointments (`appointments/list.html`)
- Add `stack-cards` to the table (thead :168); wrap container.
- In `renderTable()` (:414) literal, add `data-label` to td's (:431–439):
  `Data|Godzina|Klient|Usługa|Pracownik|Kwota|Status|Ocena|SMS`; client-name cell
  `cell-name`, actions cell (:440) `cell-actions`. Status badge stays a tappable row.
- Empty-state `<td colspan="10">` (:418, :491) → `class="cell-empty"`.
- **T8b:** run axe on prod `appointments/list` first to locate `heading-order` +
  `region` (not in static markup → JS-injected heading or a region outside `<main>`);
  fix at source (correct heading level / add landmark or role), re-run to confirm.

### Step 5 — Build, deploy, verify
Build CSS, `node --check` the touched inline scripts, deploy, verify per Step 0.

---

## Acceptance Criteria
- [ ] `.stack-cards` exists in `input.css @layer components`; CSS builds clean.
- [ ] clients/list.html uses the shared class; its page-local media block is gone;
      375px rendering is identical to current prod (before/after screenshots).
- [ ] invoices + appointments render as labelled cards at 375px, no h-scroll, actions
      reachable; desktop unchanged.
- [ ] axe: 0 critical/serious on all three; no `empty-table-header` (invoices), no
      `heading-order`/`region` (appointments).
- [ ] Committed, pushed, deployed to Vultr, verified on `http://70.34.252.120`.

## Risks
- Cascade: if a td override doesn't take, a page-local unlayered rule lacks the
  `!important` counter — add it to that property. Verify via computed styles in `/browse`.
- Invoices has a status-badge click handler + expandable duplicates row; the component
  is CSS-only (DOM unchanged) so delegation is unaffected — confirm by clicking on prod.
