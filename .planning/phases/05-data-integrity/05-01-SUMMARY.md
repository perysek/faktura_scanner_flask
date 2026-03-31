---
phase: 05-data-integrity
plan: 01
subsystem: database
tags: [postgresql, soft-delete, repository-pattern, unit-tests]

# Dependency graph
requires: []
provides:
  - is_deleted=FALSE filter on all custom query methods in InvoiceRepository (11 filters)
  - is_deleted=FALSE filter on all custom query methods in ClientRepository (9 filters)
  - is_deleted=FALSE filter on all query methods in AppointmentRepository (20 filters)
  - is_deleted=FALSE filter on all query methods in ServiceRepository (17 filters)
  - AppointmentRepository.delete() performs soft-delete UPDATE instead of DELETE FROM
  - ServiceRepository.delete() performs soft-delete UPDATE instead of calling deactivate()
  - AppointmentRepository.restore() and ServiceRepository.restore() methods
  - 40 unit tests proving every query method excludes soft-deleted records
affects: [audit-logging, appointments, services, invoices, clients]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Soft-delete filter pattern: AND is_deleted = FALSE added to every SELECT in custom query methods"
    - "Repository test pattern: mock_db fixture for BaseRepository subclasses, mock_appt_db/mock_svc_db fixtures for standalone repos using get_db_connection"
    - "Soft-delete in standalone repos: UPDATE SET is_deleted=TRUE, deleted_at=CURRENT_TIMESTAMP with restore() companion method"

key-files:
  created:
    - tests/repositories/test_invoice_repository.py
    - tests/repositories/test_soft_delete_repos.py
  modified:
    - repositories/invoice_repository.py
    - repositories/clients/client_repository.py
    - repositories/appointments/appointment_repository.py
    - repositories/services/service_repository.py
    - routes/api_routes.py

key-decisions:
  - "AppointmentRepository and ServiceRepository left as standalone classes (not refactored to extend BaseRepository) — too risky for a soft-delete hardening pass; soft-delete implemented inline instead"
  - "ServiceRepository.delete() now does real soft-delete (is_deleted=TRUE) not deactivation (is_active=FALSE) — deactivate() preserved as separate orthogonal operation"
  - "Pre-existing test failure in test_validators.py::TestIBANValidator::test_iban_inny_kraj_nie_pl is out of scope — documented as deferred"

patterns-established:
  - "All custom SELECT methods in repositories must include AND is_deleted = FALSE (for aliased queries: AND a.is_deleted = FALSE)"
  - "Standalone repos (no BaseRepository): patch the module-local name (repositories.appointments.appointment_repository.get_db_connection) not the source (config.database.get_db_connection)"
  - "Test assertion pattern: assert 'is_deleted = FALSE' in sql with descriptive failure message"

requirements-completed: [IMPR-01]

# Metrics
duration: 9min
completed: 2026-03-31
---

# Phase 5 Plan 01: Soft-Delete Filter Hardening Summary

**Added `is_deleted = FALSE` to 57 query sites across 4 repositories; replaced hard-delete with soft-delete UPDATE in AppointmentRepository and ServiceRepository; 40 new unit tests all passing**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-31T16:19:11Z
- **Completed:** 2026-03-31T16:28:30Z
- **Tasks:** 2
- **Files modified:** 7 (5 repositories/routes + 2 new test files)

## Accomplishments

- Closed all soft-delete filter gaps in InvoiceRepository (8 methods + 2 statistics sub-queries = 11 filter sites), ClientRepository (9 methods), AppointmentRepository (13 methods = 20 filter sites), ServiceRepository (11 methods = 17 filter sites), and 1 raw query in api_routes.py
- Refactored AppointmentRepository.delete() from `DELETE FROM appointments` to `UPDATE SET is_deleted=TRUE`; added restore() companion
- Refactored ServiceRepository.delete() from calling deactivate() (is_active=FALSE) to `UPDATE SET is_deleted=TRUE`; added restore() companion
- Created 40 unit tests (20 per test file) proving every custom query method excludes soft-deleted records; full test suite at 164 passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add is_deleted=FALSE filters to InvoiceRepository + ClientRepository, create tests** - `0c5c29b` (feat)
2. **Task 2: Refactor AppointmentRepository and ServiceRepository for soft-delete, add is_deleted filters, create tests** - `6f53710` (feat)

**Plan metadata:** (to be committed in final docs commit)

## Files Created/Modified

- `repositories/invoice_repository.py` - Added is_deleted=FALSE to find_by_invoice_number, find_by_invoice_number_and_seller (2 branches), search, get_by_date_range, get_by_seller, get_recent, get_upcoming_payments, get_overdue_payments, get_statistics (2 sub-queries)
- `repositories/clients/client_repository.py` - Added is_deleted=FALSE to search, search_by_name, search_by_phone, find_by_email, get_active_clients, get_recent_clients, get_upcoming_birthdays, get_clients_without_recent_visits, get_statistics
- `repositories/appointments/appointment_repository.py` - Added is_deleted=FALSE to all 13 SELECT methods; replaced delete() hard-delete with soft-delete; added restore()
- `repositories/services/service_repository.py` - Added is_deleted=FALSE to all 11 SELECT methods; replaced delete() deactivate-call with real soft-delete; added restore()
- `routes/api_routes.py` - Added WHERE is_deleted=FALSE to raw _fetch_all query in seller sync-check endpoint
- `tests/repositories/test_invoice_repository.py` - TestSoftDelete (10 tests), TestAuditAfterDelete (1 test), TestClientSoftDelete (9 tests) — 20 total
- `tests/repositories/test_soft_delete_repos.py` - TestAppointmentSoftDelete (10 tests), TestServiceSoftDelete (10 tests) — 20 total

## Decisions Made

- AppointmentRepository and ServiceRepository kept as standalone classes rather than refactoring them to extend BaseRepository — the refactor would have been large and risky; soft-delete implemented inline with the same UPDATE pattern
- ServiceRepository.delete() now does real soft-delete (is_deleted=TRUE, deleted_at=CURRENT_TIMESTAMP) instead of calling deactivate() which only set is_active=FALSE — deactivate() preserved unchanged as an orthogonal operation
- Test fixtures for standalone repos (mock_appt_db, mock_svc_db) patch at the module-local binding (`repositories.appointments.appointment_repository.get_db_connection`) rather than the shared source

## Deviations from Plan

None - plan executed exactly as written.

Note: Pre-existing test failure (`test_validators.py::TestIBANValidator::test_iban_inny_kraj_nie_pl`) was present before this plan and is unrelated to soft-delete work. Logged as out-of-scope, not touched.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All custom SELECT queries across the four core repositories now exclude soft-deleted records
- AppointmentRepository.delete() and ServiceRepository.delete() are now consistent with InvoiceRepository.delete() and ClientRepository.delete() (all use soft-delete)
- Ready for Phase 5 Plan 02: audit logging (FIX-01, FIX-02) — the soft-delete FK constraint issue that blocked audit logging is now resolved

## Self-Check: PASSED

- FOUND: tests/repositories/test_invoice_repository.py
- FOUND: tests/repositories/test_soft_delete_repos.py
- FOUND: .planning/phases/05-data-integrity/05-01-SUMMARY.md
- FOUND: commit 0c5c29b (Task 1)
- FOUND: commit 6f53710 (Task 2)

---
*Phase: 05-data-integrity*
*Completed: 2026-03-31*
