# Roadmap: MyWay Nails & Beauty — v2.0 UI/UX Polish

## Overview

The v1.0 design system audit scored 17/24. This milestone closes the gap across four pillars: Typography (2/4), Spacing (3/4), Color (3/4), and Experience Design/Accessibility (3/4). Every change is additive or visually neutral — no feature regressions, no new dependencies. The four phases execute in dependency order: CSS architecture first (shared foundation), then layout/spacing (touches same files), then color (independent cleanup), then accessibility and UX polish (purely additive).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: CSS Architecture** - Extract shared :root to input.css, unify type scale across 45 templates (completed 2026-03-19)
- [ ] **Phase 2: Layout & Spacing** - Remove !important padding overrides, standardize max-width scale
- [x] **Phase 3: Color Cleanup** - Eliminate remaining hardcoded hex values, adopt brand-* Tailwind tokens (completed 2026-03-24)
- [ ] **Phase 4: Accessibility & UX Polish** - Add aria attributes, retry actions, fix 404 CTA, fix copy

## Phase Details

### Phase 1: CSS Architecture
**Goal**: Navigating between any two pages feels visually consistent because all typography definitions live in one place
**Depends on**: Nothing (first phase)
**Requirements**: TYPO-01, TYPO-02, TYPO-03
**Success Criteria** (what must be TRUE):
  1. All pages display `.page-title` at exactly 1.75rem — navigating from calendar to client list shows no headline size jump
  2. All pages display `.stat-value` at exactly 1.25rem — no variation between dashboard, income, and list pages
  3. Any developer changing a font size in `input.css` sees the change propagate to all pages without touching individual templates
  4. No template file contains a `:root` block that duplicates properties already declared in `input.css`
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Add global typography block to @layer components in input.css and run build
- [ ] 01-02-PLAN.md — Strip local .page-title and .page-subtitle redeclarations from all 38 templates
- [ ] 01-03-PLAN.md — Strip local .stat-value and .stat-label redeclarations from 7 templates

### Phase 2: Layout & Spacing
**Goal**: Page layout is controlled by each page, not fought against by each page
**Depends on**: Phase 1
**Requirements**: SPAC-01, SPAC-02
**Success Criteria** (what must be TRUE):
  1. Opening any page in the app shows no `!important` in its computed styles for `#main-content` padding
  2. Form pages (create/edit) display content within a consistent max-width (900px)
  3. List pages (clients, employees, services) display content within a consistent max-width (1400px)
  4. Calendar pages use full available width with no max-width constraint
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — Change base.html p-2→p-0 and restore padding on analytics/dashboard.html
- [ ] 02-02-PLAN.md — Strip !important padding overrides from all 13 templates, move padding to .refined-page
- [ ] 02-03-PLAN.md — Normalize max-width scale across ~21 templates (900px forms, 1400px lists, full-width calendars)

### Phase 3: Color Cleanup
**Goal**: Gold accent color is defined in one place and all templates reference the token, not a hex value
**Depends on**: Phase 1
**Requirements**: COL-01, COL-02
**Success Criteria** (what must be TRUE):
  1. Searching templates for `#c9a227` and `#d97706` returns zero results
  2. Auth templates (login, profile, forgot_password, reset_password) reference CSS custom properties or Tailwind tokens instead of hardcoded hex
  3. Error templates (404, 500) and form templates contain no hardcoded hex color values
  4. Calendar appointment blocks use `brand-*` Tailwind utilities instead of inline `#c9a227` strings in JavaScript
**Plans**: TBD

### Phase 4: Accessibility & UX Polish
**Goal**: Every interactive element is reachable by keyboard and screen reader, and every error state offers recovery
**Depends on**: Nothing (independent of Phases 1-3, can be sequenced after Phase 3)
**Requirements**: A11Y-01, A11Y-02, A11Y-03, UX-01, UX-02, UX-03, COPY-01
**Success Criteria** (what must be TRUE):
  1. Every icon-only button (calendar navigation, modal close, flash dismiss) has an `aria-label` matching its visible tooltip text
  2. A screen reader user navigating calendar day view or client list hears content update announcements via `aria-live` regions
  3. A keyboard-only user can skip to main content without tabbing through the sidebar using a skip-navigation link
  4. When the calendar day view or client list shows an error state, a retry button is visible and reloads the failed content
  5. Non-accountant users landing on the 404 page are taken to `main.dashboard` (not `main.invoices_list`) by the CTA button
  6. `sellers/edit.html` shows "Ładowanie..." (with diacritic) and `analytics/dashboard.html` shows "Powrót na górę" (not "Idź na początek")
**Plans**: 3 plans

Plans:
- [ ] 04-01-PLAN.md — Fix diacritic, copy text, and error page CTA routing (UX-02, UX-03, COPY-01)
- [ ] 04-02-PLAN.md — Add skip-nav link, sr-only CSS, aria-live regions, aria-label audit (A11Y-01, A11Y-02, A11Y-03)
- [ ] 04-03-PLAN.md — Add retry buttons to calendar, client list, and appointment list error states (UX-01)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. CSS Architecture | 2/3 | Complete    | 2026-03-19 |
| 2. Layout & Spacing | 0/3 | Not started | - |
| 3. Color Cleanup | 1/1 | Complete   | 2026-03-24 |
| 4. Accessibility & UX Polish | 0/3 | Not started | - |
