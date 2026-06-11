---
title: "Phase 07: Page-Sweep Migration & Consistency Verification"
description: "Sweep all macro-consuming pages to the canonical look, reconcile the global .refined-btn-* gradient/flat duplication, and prove one consistent design language (Issue 5-pages)."
skill: "web-design-guidelines"
status: pending
group: "design-system-migration"
dependencies: [P05, P06]
tags: [phase, design-system, verification, css]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 07: Page-Sweep Migration & Consistency Verification

**Context:** [[plan|Master Plan]] | **Dependencies:** P05, P06 | **Status:** Pending

---

## Overview

P05/P06 migrated the shared macros; this phase closes Issue 5 by sweeping the **pages** that still carry orphaned System-A styling or page-local design forks, and by reconciling the one global duplication that proves the two systems coexist: `.refined-btn-primary`/`.refined-btn-secondary` are defined **twice** — a gradient `@apply` version in `static/css/input.css` (`@layer components`, ~line 463) and a flat `var(--color-ink)` version page-locally in `clients/list.html` (~line 106) and the `*list_refined.html` pages. This phase makes the global definitions canonical (flat), removes redundant page-local copies, and verifies area-by-area that the app reads as one language.

**Goal:** No page looks like "a different app"; `git grep` finds no System-A button/card/radius utilities on migrated pages; the global `.refined-btn-*` is flat and singular.

> [!NOTE]
> This is the broadest phase. If a single session can't finish the full sweep, split it by area (forms-pages vs. list/table-pages) into P07a/P07b and update plan.md's Phase Table — do not leave it half-sept-and-marked-done.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** All pages that consume the migrated macros or define page-local `.refined-*` styles: create/edit forms (clients, sellers, employees, services, invoices, appointments, users, roles), list/refined pages (`invoices/list_refined.html`, `sellers/list_refined.html`, `history/list_refined.html`), dashboards (`dashboard/index.html`, `analytics/dashboard.html`, `income/dashboard.html`), settings, absences.
- **Server Layer:** None.
- **Database Layer:** None.
- **Integrations:** `npm run build:css` after the global `.refined-btn-*` reconciliation.

### User Workflow

**Trigger:** A user moves between any two pages (e.g. dashboard → invoices → a create form).

**Steps:**
1. Buttons, inputs, cards, badges, and sort affordances look and behave the same on every page.
2. Muscle memory transfers; "what's primary/clickable" is unambiguous.

**Success Outcome:** Consistent affordances; the review's learnability concern (Issue 5) is resolved.

### Problem Being Solved

**Pain Point:** Issue 5 — two visual languages erode learnability and double maintenance.

**Alternative Approach:** Migrating only the macros (P05/P06) leaves page-local forks and the global button duplication, so inconsistency persists.

### Integration Points

**Upstream Dependencies:** P05 (`.form-*`), P06 (table macros + tokens).

**Downstream Consumers:** P11 final verification samples these pages.

**Data Flow:**
```
input.css .refined-btn-* (now flat, canonical)  ─▶ dashboards/analytics inherit flat
page-local .refined-btn-* duplicates  ─▶ removed where identical
remaining System-A page styling  ─▶ migrated to tokens/macros
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Reconcile `.refined-btn-*` globally to flat:** Make the `input.css @layer components` `.refined-btn-primary`/`secondary` the flat token version (matching `clients/list.html`), so dashboards/analytics that use the gradient `@apply` version shift to flat?
   - **Context:** This is the canonical decision (ADR-G-01). It changes the look of pages using the global gradient buttons.
   - **Assumptions if unanswered:** Yes — flat is canonical; verify dashboards/analytics visually.
   - **Impact:** Without it, two button looks persist.

2. **Sweep order / batching:** Sweep by area in this order — forms → list/refined → dashboards → settings/absences — committing per area?
   - **Assumptions if unanswered:** Yes; per-area commits for reviewability.
   - **Impact:** Easier review + rollback.

3. **Out-of-scope pages:** Public pages (`public/*`, `booking/index.html`, `auth/login.html`) and the standalone `appointment_rate.html` (P10) are NOT part of the authenticated design system sweep?
   - **Assumptions if unanswered:** Correct — public/standalone pages keep their own minimal styling; only the authenticated app is swept.
   - **Impact:** Avoids touching intentionally-standalone pages.

### Validation Checklist

- [ ] Global `.refined-btn-*` reconciliation approved.
- [ ] P05 + P06 merged.
- [ ] Area list + order confirmed.
- [ ] Grep inventory of page-local `.refined-*` definitions produced before starting.

> [!CAUTION]
> Reconciling the global `.refined-btn-*` affects MANY pages at once. Screenshot dashboards/analytics before/after; these are the most likely to surprise.

---

## Requirements

### Functional

- Global `.refined-btn-primary`/`secondary` in `input.css` are flat/token (canonical); redundant page-local duplicates removed where byte-identical in intent.
- Every authenticated page that used macros or page-local System-A styling now reads canonical.
- `git grep "rounded-xl\|rounded-2xl\|from-primary-\|to-primary-"` across `templates/` returns only intentional, documented exceptions (ideally none in the authenticated app).

### Technical

- Per-area commits.
- Rebuild after the global CSS change.
- Maintain a sweep checklist (page → status) in this phase file's QA section.

---

## Decision Log

### Flat `.refined-btn-*` is canonical (ADR-07-01)

**Date:** 2026-06-10
**Status:** Accepted (implements ADR-G-01)

**Context:** Duplicate gradient-vs-flat definitions.

**Decision:** Global `input.css` definitions become flat token buttons; page-local duplicates removed.

**Consequences:** One button look app-wide. Dashboards/analytics change appearance (verified). Less CSS overall.

---

## Implementation Steps

### Step 0: Define Verification + Inventory (do first)

- [ ] `git grep -n "rounded-xl\|rounded-2xl\|from-primary-\|to-primary-\|\.refined-btn-primary\s*{" templates/ static/css/` → build the sweep inventory.
- [ ] List every template defining a page-local `.refined-*` block (at least `clients/list.html`, `invoices/list_refined.html`, `sellers/list_refined.html`, `history/list_refined.html`).
- [ ] `/browse` baseline screenshots per area (forms, list, dashboards) at 1440px + 390px.
- [ ] Define the pass bar: per area, after-screenshots show canonical buttons/inputs/cards; axe parity; no console errors.

### Step 1: Reconcile global `.refined-btn-*`

- [ ] In `input.css @layer components`, replace the gradient `@apply` `.refined-btn-primary`/`.refined-btn-secondary` (~lines 463–480) with the flat token versions (port from `clients/list.html:106-156`): `--color-ink` fill, `--radius-sm`, token hover. Keep `.refined-btn-sm` and the `.active` modifier (re-style flat).
- [ ] `npm run build:css`.
- [ ] Verify dashboards/analytics/income now render flat buttons; screenshot.

### Step 2: Remove redundant page-local duplicates

- [ ] In `clients/list.html` and the `*list_refined.html` pages, delete the page-local `.refined-btn-primary`/`.refined-btn-secondary` (and `.th-sort-icon` if still duplicated post-P01) blocks **only where the global now matches**. Keep any page-specific modifiers (e.g. `.refined-btn-secondary.btn-active` in clients) that have no global equivalent — or promote them to `input.css` if shared.
- [ ] Re-verify those pages look unchanged (global now provides the same flat style).

### Step 3: Sweep remaining System-A page styling

For each area, in order (forms → list/refined → dashboards → settings/absences):

- [ ] Replace orphaned `rounded-xl`/`rounded-2xl` cards with `.form-card`/`.table-card`/`.refined-card` or token radius.
- [ ] Replace gradient/`slate-*`/`primary-*` buttons with `.form-btn-*`/`.refined-btn-*`.
- [ ] Ensure tables use the migrated macros or the `.refined-table` family.
- [ ] Commit per area: `style(<area>): canonical design language (phase 07)`.

### Step 4: Final consistency pass

- [ ] Re-run the grep; resolve/justify any remaining hits.
- [ ] `/design-review` across one page per area; confirm one language.
- [ ] axe on each swept area: 0 critical/serious.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] Global `.refined-btn-*` is flat/canonical; no page-local duplicate remains where identical.
- [ ] Every authenticated area swept; buttons/inputs/cards/sort affordances consistent.
- [ ] `git grep` shows no unintended System-A utilities in the authenticated app.

**Quality Gates:**
- [ ] axe 0 critical/serious on each swept area.
- [ ] No console errors; no broken layouts at 1440px/390px.
- [ ] `/design-review` confirms consistency.

**Integration:**
- [ ] Dashboards/analytics (heaviest gradient users) render flat and look intentional.

---

## Quality Assurance

### Sweep Checklist (fill during implementation)

| Area | Pages | Status |
|------|-------|--------|
| Forms | clients/sellers/employees/services/invoices/appointments/users/roles create+edit | ☐ |
| List/refined | invoices/sellers/history `list_refined`, services/employees/users/roles `list` | ☐ |
| Dashboards | dashboard/index, analytics/dashboard, income/dashboard | ☐ |
| Settings/absences | settings/*, absences/* | ☐ |

### Test Plan

#### Manual Testing
- [ ] **Cross-page consistency:** Click through dashboard → invoices → a create form → settings; buttons/inputs identical.
  - Expected: one language; Actual: ___

#### Automated Testing
```bash
npm run build:css
git grep -n "rounded-xl\|rounded-2xl\|from-primary-" templates/   # expect only justified/none in authenticated app
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` per area batch; `/design-review` final; 0 critical.
- [ ] **Code Quality:** Duplicated CSS removed; net CSS smaller.
- [ ] **Security:** N/A.
- [ ] **Documentation:** Update `DESIGN-TOKENS.md` "migration complete" + list any intentional exceptions.
- [ ] **Project Pattern Compliance:** Canonical classes; build pipeline.

---

## Dependencies

### Upstream (Required Before Starting)
- P05, P06.

### Downstream (Will Use This Phase)
- P11 (final sample verification).

### External Services
- None.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Sweep checklist complete (or phase split + plan.md updated)
- [ ] Code + design review passed per area
- [ ] Phase marked DONE in plan.md
- [ ] Committed per area: `style(<area>): canonical design language (phase 07)`

---

## Notes

### Technical Considerations
- Removing page-local CSS shrinks `output.css` and per-page `<style>` blocks — confirm nothing depended on a page-local override that the global lacks.
- Public/standalone pages (`public/*`, `auth/login.html`, `booking/index.html`, `appointment_rate.html`) are intentionally excluded.

### Known Limitations
- Some one-off pages may keep small bespoke styles; document each exception rather than forcing the token system where it doesn't fit.

### Future Enhancements
- A CI grep guard (fail build if `rounded-xl`/`from-primary-` reappears in authenticated templates) would prevent re-forking.

---

**Previous:** [[phase-06-migrate-table-macros|Phase 06]]
**Next:** [[phase-08-clients-table-a11y|Phase 08: Clients table a11y & polish]]
