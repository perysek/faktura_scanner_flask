---
title: "Phase 02: People & access tables → mobile cards"
description: "Apply the shared .stack-cards component to the four people/access list tables (sellers, employees, users, roles), all JS-rendered."
skill: "web-design-guidelines"
status: pending
group: "mobile-tables"
dependencies: [P01]
tags: [phase, responsive, mobile]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 02: People & access tables → mobile cards

**Context:** [[plan|Master Plan]] | **Dependencies:** P01 | **Status:** Pending

---

## Overview

Apply the P01 `.stack-cards` component to the four "who" tables. All four are
JS-rendered (`tbody.innerHTML = data.map(...)`), so `data-label` goes into the
template literal. No new CSS — each table just opts into the shared class and labels
its cells. Mirror each table's own thead labels exactly.

**Goal:** sellers, employees, users, roles each render as labelled cards at ≤640px,
no horizontal scroll, actions reachable; desktop unchanged.

---

## Context & Workflow

- **UI Layer:** `sellers/list_refined.html`, `employees/list.html`, `users/list.html`,
  `roles/list.html`. **CSS/Server/DB:** none (uses P01's component).
- **Upstream:** P01 (`.stack-cards`). **Downstream:** P07 touches none of these.

---

## Prerequisites & Clarifications

### Questions for User
1. **Decorative cells:** hide low-value columns on cards (e.g. an avatar-only cell), or
   show every column as a labelled row?
   - **Assumption:** show all data columns; mark purely-decorative/icon-only cells
     `cell-hide-sm`. Keep identity + actions always.

---

## Implementation (per table — identical recipe)

For each: add `stack-cards` to the `<table>` (+ `stack-cards-wrap` on its scroll
container), add `data-label` to every data `<td>` in the JS renderer mirroring the
thead, mark the identity cell `cell-name` and the actions cell `cell-actions`, mark
any empty/colspan state row `cell-empty`.

### Step 0 — Verification
`/browse` at 375px on prod for `/sellers`, `/employees`, `/users`, `/roles` after
deploy; axe 0 critical/serious each.

### Step 1 — users (`users/list.html`)
- JS: `users.map()` at :182, `#users-body`; thead :56–62.
- Labels: `Imię i nazwisko` (→ `cell-name`), `Email`, `Rola`, `Pracownik`, `Status`,
  `Ostatnie logowanie`; last `<th>`/td (actions) → `cell-actions`.
- Add `stack-cards` to `<table id="users-table">` (:53).

### Step 2 — roles (`roles/list.html`)
- JS: `roles.map()` at :85, `#roles-body`; thead :53–57.
- Labels: `Nazwa` (→ `cell-name`), `Wyświetlana nazwa`, `Uprawnienia modułów`, `Typ`;
  trailing actions td → `cell-actions`. Add `stack-cards` to `<table id="roles-table">`.
- The "Uprawnienia modułów" cell may hold many badges — fine as a wrapping card row.

### Step 3 — employees (`employees/list.html`)
- JS: `employees.map()` at :727, `#employees-tbody`.
- Read the thead during execution; mirror labels. Identity (name) → `cell-name`,
  actions → `cell-actions`. Add `stack-cards` to the table. Hide any avatar-only/icon
  cell with `cell-hide-sm` if it has no standalone meaning.

### Step 4 — sellers (`sellers/list_refined.html`) — split-table special case
- **Note:** sellers uses a sticky split: a header-only `<table>` at :500 (thead :506)
  and a separate body `<table id="sellersTable">` (:520) with a `<colgroup>` and
  `#sellers-tbody` (:526) but **no thead of its own**.
- Add `stack-cards` to `#sellersTable`. On ≤640px also hide the separate header table
  (give it `cell-hide-sm` on its row or wrap it so it's `display:none` — labels come
  from `data-label`, not the header table).
- Columns (from colgroup + header table, mirror header `<th>` text): NIP, Sprzedawca,
  Faktury, Zapłacone, Niezapłacone, Aktualizacja, Akcje.
- JS renderer: `renderTable()` :753, `tbody.innerHTML = filtered.map(...)` :778 — add
  `data-label` there; NIP or name cell → `cell-name`, actions → `cell-actions`.
- Skeleton `<tr class="skeleton-row">` (:527–529): add `cell-hide-sm` to their cells or
  hide the skeleton rows on ≤640px.

### Step 5 — Build (CSS unchanged → build only if a new utility class appears), deploy, verify.

---

## Acceptance Criteria
- [ ] All four tables render as labelled cards at 375px; no h-scroll; actions reachable.
- [ ] Each card's labels match that table's thead wording.
- [ ] sellers' split header table is hidden on mobile; cards still labelled.
- [ ] Desktop rendering unchanged; axe 0 critical/serious on each page.
- [ ] Committed, pushed, deployed, verified on prod.

## Risks
- sellers' two-table split is the only non-uniform case — verify on prod that the body
  cards label correctly and the sticky header doesn't double up.
- Don't forget `escapeHtml` is already applied to cell values; `data-label` is static.
