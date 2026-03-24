---
phase: 04-accessibility-ux-polish
plan: 01
subsystem: ui
tags: [jinja2, flask, copywriting, ux, error-pages]

# Dependency graph
requires: []
provides:
  - Corrected Polish diacritic in sellers/edit.html loading state
  - Corrected back-to-top button label in analytics/dashboard.html
  - Role-conditional CTA routing on 404 and 500 error pages
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [Jinja2 inline conditional for role-based URL routing in error pages]

key-files:
  created: []
  modified:
    - templates/sellers/edit.html
    - templates/analytics/dashboard.html
    - templates/errors/404.html
    - templates/errors/500.html

key-decisions:
  - "Error page CTA uses current_user.is_authenticated guard before role check to safely handle anonymous users (Flask-Login AnonymousUserMixin returns False for is_authenticated)"

patterns-established:
  - "Role-conditional url_for pattern: url_for('main.invoices_list' if current_user.is_authenticated and current_user.role == 'accountant' else 'main.dashboard')"

requirements-completed: [UX-02, UX-03, COPY-01]

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 4 Plan 01: Copywriting Fixes and Error Page CTA Routing Summary

**Targeted text corrections (diacritic and button label) plus role-based conditional CTA routing on 404/500 error pages using Jinja2 inline conditionals**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-24T19:50:00Z
- **Completed:** 2026-03-24T19:55:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Fixed missing Polish diacritic: "Ladowanie..." -> "Ładowanie..." in sellers/edit.html
- Corrected back-to-top button from "Idź na początek" to "Powrót na górę" in analytics/dashboard.html
- Both 404 and 500 error pages now route accountant users to invoices_list and everyone else (including unauthenticated) to main.dashboard

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix diacritic and back-to-top button copy** - `5b3eff9` (fix)
2. **Task 2: Add conditional CTA routing to 404 and 500 error pages** - `485e8c5` (fix)

## Files Created/Modified
- `templates/sellers/edit.html` - Fixed "Ładowanie..." diacritic on line 416
- `templates/analytics/dashboard.html` - Changed back-to-top text to "Powrót na górę" on line 84
- `templates/errors/404.html` - Conditional CTA: accountant -> invoices_list, others -> dashboard
- `templates/errors/500.html` - Same conditional CTA as 404.html

## Decisions Made
- Used `current_user.is_authenticated` guard before `current_user.role` check on error pages to safely handle anonymous users — Flask-Login's AnonymousUserMixin does not have a `role` attribute, so checking `.is_authenticated` first prevents AttributeError in unauthenticated sessions.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 4 template files corrected as specified
- Phase 04 plan 01 complete; ready to continue with remaining plans in phase 04

---
*Phase: 04-accessibility-ux-polish*
*Completed: 2026-03-24*
