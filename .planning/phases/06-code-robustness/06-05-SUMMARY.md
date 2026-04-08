---
phase: 06-code-robustness
plan: 05
subsystem: api
tags: [alembic, migration, logging, error-handling, appointments, sse, flask]

# Dependency graph
requires:
  - phase: 06-code-robustness-01
    provides: AppError hierarchy and base exception types
  - phase: 06-code-robustness-02
    provides: Route-level AppError migration pattern
  - phase: 05-data-integrity
    provides: soft-delete migrations and appointment tables
provides:
  - Alembic migration i3j4k5l6m7n8 replacing 6-value CHECK constraint with 7-value (adds 'pending')
  - upload_files with zero print() calls — all debug noise removed
  - SSE generator with generic Polish error messages (no str(e) to clients)
  - bulk_update_seller_invoices with generic per-item error message (no str(e) to clients)
affects: [appointments, api_routes, database-schema]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "logging.exception() captures full traceback — no need for print(traceback.format_exc())"
    - "Generic user-facing error messages in Polish; details to server logs only"
    - "Alembic op.execute() for raw SQL constraint replacement across dialects"

key-files:
  created:
    - alembic/versions/i3j4k5l6m7n8_add_pending_to_appointment_status_check.py
  modified:
    - routes/api_routes.py

key-decisions:
  - "Used op.execute() with raw SQL for constraint replacement — more explicit and dialect-portable than op.drop_constraint/op.create_check_constraint"
  - "Renamed new constraint to chk_appointments_status_v2 to distinguish from legacy check_appointment_status"
  - "Pre-existing print(..., file=sys.stderr) in _log_audit helper left in place — out of scope for this plan (deferred)"

patterns-established:
  - "SSE error pattern: logging.exception() for server details + generic Polish message to client"
  - "Bulk operation error pattern: logging.exception() per item + 'Faktura N: błąd aktualizacji' in errors list"

requirements-completed: [IMPR-04, IMPR-03]

# Metrics
duration: 12min
completed: 2026-04-08
---

# Phase 06 Plan 05: Code Robustness Gap Closure Summary

**Alembic migration adding 'pending' to appointments CHECK constraint + full print()/str(e) cleanup in api_routes upload, SSE, and bulk_update paths**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-08T09:41:44Z
- **Completed:** 2026-04-08T09:53:00Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- New migration i3j4k5l6m7n8 chains from h2i3j4k5l6m7, drops 6-value `check_appointment_status` and adds 7-value `chk_appointments_status_v2` including 'pending' — aligns DB constraint with AppointmentStatus enum (IMPR-04)
- Removed all 6 print()/sys.stdout.flush() debug statements from upload_files; replaced file-count print with `logging.info` (IMPR-03)
- SSE generator now yields 'błąd przetwarzania' (generic) instead of `str(e)` to event-stream clients; `logging.exception()` captures full server-side details
- bulk_update_seller_invoices errors list uses 'Faktura N: błąd aktualizacji' (generic) instead of `str(e)` — no internal error details reach API consumers

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Alembic migration adding 'pending' to appointments.status CHECK constraint** - `bb1dc81` (feat)
2. **Task 2: Remove print() calls from upload_files and replace str(e) in SSE and bulk_update** - `ee8f5ef` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `alembic/versions/i3j4k5l6m7n8_add_pending_to_appointment_status_check.py` - Migration: drops 6-value CHECK, adds 7-value CHECK with 'pending'; downgrade restores original
- `routes/api_routes.py` - Removed 6 print()/flush calls; replaced str(e) with generic messages in SSE and bulk_update; logging.exception() for server details

## Decisions Made
- Used `op.execute()` with raw SQL for constraint replacement — more explicit and dialect-portable than Alembic's higher-level constraint API
- Constraint renamed `chk_appointments_status_v2` to avoid collision with legacy `check_appointment_status` name
- Pre-existing `print(..., file=sys.stderr)` in `_log_audit` helper (line 41) left untouched — out of scope for this plan (not in upload_files, SSE, or bulk_update paths)

## Deviations from Plan

None - plan executed exactly as written.

The `print(..., file=sys.stderr)` at line 41 (`_log_audit` helper) was discovered during verification but is out-of-scope per the plan's target files. Logged for future work.

## Issues Encountered
- Pre-existing test failure in `TestIBANValidator.test_iban_inny_kraj_nie_pl` (German IBAN accepted when Polish-only expected) — unrelated to this plan's changes; 291/292 tests passed with no regressions from this plan's edits.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- IMPR-03 and IMPR-04 fully satisfied — Phase 06 gap closure complete
- All internal error details now go to `logging.exception()` only, never to HTTP/SSE clients
- Database migration i3j4k5l6m7n8 ready to apply at next deployment (`alembic upgrade head`)
- The `_log_audit` print/str(e) at line 41 can be addressed in a future cleanup phase

---
*Phase: 06-code-robustness*
*Completed: 2026-04-08*
