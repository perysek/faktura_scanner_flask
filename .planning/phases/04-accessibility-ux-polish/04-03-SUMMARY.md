---
phase: 04-accessibility-ux-polish
plan: 03
subsystem: ui
tags: [error-handling, ux, async, retry, flask, jinja2]

# Dependency graph
requires:
  - phase: 04-02
    provides: aria-live on .timeline-container so inline errors in #emptyState are announced to screen readers
provides:
  - Inline retry button in calendar.html showError() replacing Modals.alert
  - Retry buttons in clients/list.html both API error and network error states
  - Retry button in appointments/list.html network error catch block
affects: [future-async-views, ux-error-patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inline error state with retry button pattern: replace modal alerts with DOM injection into existing empty-state containers"
    - "Retry button uses refined-btn-secondary class and onclick calling the same async load function"

key-files:
  created: []
  modified:
    - templates/appointments/calendar.html
    - templates/clients/list.html
    - templates/appointments/list.html

key-decisions:
  - "Calendar error state uses #emptyState container (already has aria-live coverage from Plan 02) — no new DOM element needed"
  - "No escaping added to showError() message parameter — all callers pass hardcoded Polish string literals, not user input"

patterns-established:
  - "Error recovery pattern: inline error state with retry button inside existing empty-state container replaces modal approach"
  - "Retry buttons inside <td> elements — valid HTML5, consistent with existing table empty-state layout"

requirements-completed: [UX-01]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 4 Plan 03: Retry Buttons in Async Error States Summary

**Replaced calendar Modals.alert with inline error + retry, and added "Sprobuj ponownie" retry buttons to client list and appointment list error states — closes UX-01**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T21:01:52Z
- **Completed:** 2026-03-24T21:03:59Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- calendar.html: showError() now renders inline error in #emptyState (already has aria-live coverage) with retry button calling loadSchedule()
- clients/list.html: retry buttons added to both API error path and network catch block, both calling loadClients()
- appointments/list.html: retry button added to network catch block calling loadAppointments()
- All retry buttons use refined-btn-secondary class matching the design system

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace calendar.html Modals.alert error with inline retry button** - `dba6934` (fix)
2. **Task 2: Add retry buttons to clients/list.html and appointments/list.html error states** - `7f7b982` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `templates/appointments/calendar.html` - showError() replaced: Modals.alert removed, inline error state with SVG icon, heading, message, and retry button rendered in #emptyState
- `templates/clients/list.html` - Two error states updated: API error (line 534) and network catch (line 542) both now include retry button
- `templates/appointments/list.html` - Network catch block (line 305) updated: single-line innerHTML replaced with multi-line block including retry button

## Decisions Made
- Calendar error uses the existing #emptyState container rather than adding a new element — the container already has aria-live coverage from Plan 02, making the error announcement automatic
- No XSS escaping added to showError() message parameter — all call sites pass hardcoded Polish string literals, not user-supplied data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- UX-01 closed: all three async-loading views now have self-service error recovery
- Phase 04 complete — all accessibility and UX polish plans done
- Pattern established: inline retry in empty-state container can be applied to any future async views

## Self-Check: PASSED

- FOUND: templates/appointments/calendar.html
- FOUND: templates/clients/list.html
- FOUND: templates/appointments/list.html
- FOUND commit: dba6934 (fix(04-03): replace Modals.alert error with inline retry button in calendar)
- FOUND commit: 7f7b982 (feat(04-03): add retry buttons to client list and appointment list error states)

---
*Phase: 04-accessibility-ux-polish*
*Completed: 2026-03-24*
