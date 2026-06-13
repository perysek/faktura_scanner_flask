---
title: "Phase 03: Absences / HR / catalog tables → mobile cards"
description: "Apply the shared .stack-cards component to the seven remaining tables: absences requests + categories + balances, my-absences history, employee assigned-services, service categories, formy zatrudnienia (4 Jinja, 3 JS)."
skill: "web-design-guidelines"
status: pending
group: "mobile-tables"
dependencies: [P01]
tags: [phase, responsive, mobile]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 03: Absences / HR / catalog tables → mobile cards

**Context:** [[plan|Master Plan]] | **Dependencies:** P01 | **Status:** Pending

---

## Overview

The long tail of the mobile-card mandate: seven smaller tables across the absences,
HR, and catalog domains. Four are **Jinja-rendered** (`data-label` goes in the
`{% for %}` loop) and three are **JS-rendered** (`data-label` in the template
literal). All adopt the P01 `.stack-cards` component — no new CSS. This is the
heaviest phase by table count; **commit in two batches** (absences cluster, then
HR/catalog) so a regression is bisectable.

**Goal:** All seven render as labelled cards at ≤640px, no horizontal scroll; desktop
unchanged; axe 0 critical/serious each.

---

## Context & Workflow

- **UI Layer:** `absences/management.html` (×2 tables), `absences/balances.html`,
  `absences/my.html`, `employees/view.html`, `services/categories/list.html`,
  `employees/formy_zatrudnienia/list.html`.
- **CSS/Server/DB:** none. **Upstream:** P01. **Downstream:** P07 also edits
  `absences/my.html`, `absences/management.html`, `services/categories/list.html`,
  `formy_zatrudnienia/list.html` (button consolidation) — P07 runs after this phase.

---

## Prerequisites & Clarifications

### Questions for User
1. **`management.html` "manual" panel table** (the third table, not named in the
   remark) — leave as-is?
   - **Assumption:** leave as-is (out of scope per remark); only requests + categories.
2. **`employees/view.html`** also has a JS price-corrections table (`#adj-history-tbody`).
   Card it too, or only the assigned-services table?
   - **Assumption:** only the `.service-table` assigned-services list (the named one).

---

## Implementation

Per table: add `stack-cards` to the `<table>`, `data-label` on each data cell
mirroring its thead, identity → `cell-name`, actions → `cell-actions`, colspan
empty-state rows → `cell-empty`.

### Step 0 — Verification
`/browse` at 375px on prod for `/absences/management`, `/absences/balances`,
`/absences/my`, the employee view page, `/services/categories`, the formy-zatrudnienia
page; axe each.

### Batch A — absences cluster

**1. absences-requests** (`absences/management.html`, `#requests-table` :243)
- Jinja `{% for ab in requests_list %}` :256. thead :246 (6 cols): Pracownik, Kategoria,
  Okres, Status, Złożono, Odpowiedź (+ an actions col).
- Add `stack-cards` to `#requests-table`; `data-label` on each `<td>` in the loop;
  Pracownik cell → `cell-name`; actions cell → `cell-actions`.

**2. absences-categories** (`absences/management.html`, table :555)
- Jinja `{% for cat in categories %}` :581; thead :567. Add `stack-cards`; label cells;
  name → `cell-name`, actions → `cell-actions`.

**3. absence-balances** (`absences/balances.html`, JS `#balance-tbody` :295)
- Read the renderer + thead during execution; mirror labels. Employee name →
  `cell-name`. This page's own `filterTable` is JS (don't disturb it — P04 only
  de-`window.`s it). Add `stack-cards` to the balances table.

Commit batch A, deploy, verify the three at 375px.

### Batch B — HR / catalog

**4. my-absences-history** (`absences/my.html`, table :301)
- Jinja `{% for ab in absences %}` :313; table has `min-width:700px` (:105) — the
  component's `min-width:0 !important` overrides it on mobile. Add `stack-cards`; label
  cells; first/identity cell → `cell-name`; actions (if any) → `cell-actions`.

**5. employee assigned-services** (`employees/view.html`, `.service-table` :413/:454)
- Jinja `{% for spec in specs %}` :454. Add `stack-cards` to the `.service-table`
  (note: this table uses class `service-table`, not `refined-table` — the component
  keys off `stack-cards`, so just add that class). Label cells; service name →
  `cell-name`; actions → `cell-actions`.

**6. service-categories** (`services/categories/list.html`, JS `#categories-tbody` :433)
- JS `categories.map()` :579 (4 cols). Empty state `<td colspan="4">` :570 → `cell-empty`.
  Add `stack-cards`; label cells; category name → `cell-name`; actions → `cell-actions`.

**7. formy-zatrudnienia** (`employees/formy_zatrudnienia/list.html`, JS `#formy-tbody` :283)
- JS `formy.map()` :337 (6 cols). Empty state `<td colspan="6">` :330 → `cell-empty`.
  Add `stack-cards`; label cells; name → `cell-name`; actions → `cell-actions`.

Commit batch B, deploy, verify the four at 375px.

---

## Acceptance Criteria
- [ ] All seven tables render as labelled cards at 375px; no h-scroll.
- [ ] Jinja tables labelled in the loop; JS tables in the literal; labels match theads.
- [ ] colspan empty-state rows render full-width (`cell-empty`), not as broken flex rows.
- [ ] Desktop unchanged; axe 0 critical/serious each.
- [ ] Two commits (batch A, batch B), both pushed + deployed + verified on prod.

## Risks
- `management.html` has three tables in tab panels — only requests + categories get
  `stack-cards`; verify the manual panel is untouched and tab switching still works.
- `my.html` and `view.html` use non-`refined-table` class names — the component keys
  off `stack-cards`, so adding the class is sufficient; verify min-width override lands
  via computed styles.
