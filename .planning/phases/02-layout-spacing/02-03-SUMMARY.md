---
phase: 02-layout-spacing
plan: "03"
subsystem: templates
tags: [css, layout, max-width, responsive, forms, calendars]
dependency_graph:
  requires: [02-01]
  provides: [SPAC-02]
  affects: [templates/clients, templates/appointments, templates/employees, templates/services, templates/roles, templates/users, templates/sellers, templates/settings, templates/income]
tech_stack:
  added: []
  patterns: [3-value max-width scale: 900px forms, 1400px lists, no constraint for full-width]
key_files:
  created: []
  modified:
    - templates/clients/create.html
    - templates/clients/edit.html
    - templates/appointments/edit.html
    - templates/appointments/view.html
    - templates/employees/create.html
    - templates/employees/edit.html
    - templates/employees/view.html
    - templates/services/create.html
    - templates/services/edit.html
    - templates/roles/create.html
    - templates/roles/edit.html
    - templates/roles/list.html
    - templates/users/create.html
    - templates/users/edit.html
    - templates/sellers/create.html
    - templates/settings/email.html
    - templates/employees/formy_zatrudnienia/list.html
    - templates/appointments/calendar.html
    - templates/appointments/calendar_week.html
    - templates/appointments/calendar_month.html
    - templates/income/dashboard.html
decisions:
  - "3-value max-width scale applied: 900px (forms/detail), 1400px (lists), none (calendars + dashboards)"
  - "Calendar pages lose margin:0 auto along with max-width — centering without a constraint is misleading and has no effect"
  - "invoices/upload.html left untouched (out of scope, pre-existing 600px on a non-.refined-page element)"
metrics:
  duration: "7 minutes"
  completed: "2026-03-19"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 21
---

# Phase 02 Plan 03: Max-width Normalization to 3-Value Scale Summary

Normalized max-width values across 21 templates to the SPAC-02 three-value scale: 900px (forms/detail), 1400px (lists), no constraint (calendars + income dashboard). Eliminated the prior 8-value fragmentation (600/720/800/1000/1100/1200/1400/1600px).

## Tasks Completed

### Task 1: Normalize form and detail templates to 900px (15 files)
- clients/create.html, clients/edit.html: 800px → 900px
- appointments/edit.html, appointments/view.html: 1000px → 900px
- employees/create.html, employees/edit.html: 800px → 900px
- employees/view.html: 1000px → 900px
- services/create.html, services/edit.html: 800px → 900px
- roles/create.html, roles/edit.html: 720px → 900px (spacing format also normalized)
- users/create.html, users/edit.html: 720px → 900px
- sellers/create.html, settings/email.html: 600px → 900px (Plan 02 padding preserved)
- **Commit:** 402818d

### Task 2: Normalize list templates to 1400px, remove max-width from full-width pages (6 files)
- employees/formy_zatrudnienia/list.html: 1100px → 1400px
- roles/list.html: 1200px → 1400px
- appointments/calendar.html: removed max-width (1400px) and margin:0 auto — now `.refined-page { padding: 2rem; }`
- appointments/calendar_week.html: removed max-width (1600px) and margin:0 auto — now `.refined-page { padding: 1rem; }`
- appointments/calendar_month.html: removed max-width (1600px) and margin:0 auto — now `.refined-page { padding: 1rem; }`
- income/dashboard.html: removed max-width (1400px) and margin:0 auto — now `.refined-page { padding: 2rem; }`
- **Commit:** 3c84c12

### Task 3: Visual spot-check (checkpoint:human-verify)
Awaiting human verification.

## Deviations from Plan

None - plan executed exactly as written.

Note: `invoices/upload.html` has `max-width: 600px` on an element-level style (not .refined-page). It was not in the plan's scope and was not touched.

## Self-Check: PASSED

Files verified present:
- templates/appointments/calendar.html — .refined-page { padding: 2rem; } (no max-width)
- templates/roles/list.html — max-width: 1400px
- templates/clients/create.html — max-width: 900px

Commits verified:
- 402818d — feat(02-layout-spacing): normalize form/detail templates to 900px max-width
- 3c84c12 — feat(02-layout-spacing): normalize list templates to 1400px, remove max-width from full-width pages
