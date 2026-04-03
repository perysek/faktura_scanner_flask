---
phase: 06-code-robustness
plan: 02
subsystem: api
tags: [flask, exceptions, error-handling, logging, python]

# Dependency graph
requires:
  - phase: 06-01
    provides: AppError exception hierarchy (AppError, ValidationError, NotFoundError, ConflictError, PermissionDeniedError) and global @app.errorhandler(AppError)
provides:
  - 8 route files fully migrated from except-Exception-return-jsonify pattern to raise AppError subclasses
  - Zero str(e) leaks to API clients across entire routes/ directory
  - All unexpected exceptions logged with full tracebacks via logging.exception()
affects: [phase-07-security, any future route files, api debugging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-layer except: except AppError: raise THEN except Exception as e: logging.exception(); raise AppError generic"
    - "Explicit 4xx returns replaced with raise ValidationError/NotFoundError/ConflictError"
    - "ValueError in user/role routes caught and re-raised as ValidationError"

key-files:
  created: []
  modified:
    - routes/appointment_routes.py
    - routes/upload_routes.py
    - routes/employee_service_routes.py
    - routes/income_routes.py
    - routes/client_preference_routes.py
    - routes/service_addon_routes.py
    - routes/roles/routes.py
    - routes/users/routes.py

key-decisions:
  - "Streaming generator in process_staged_files (upload_routes.py) kept with its own internal per-file except blocks — these return SSE error events, not HTTP JSON, so the route-level AppError pattern wraps only the outer function"
  - "finalize_uploads per-invoice loop kept with its own except block for per-item rollback — the outer function gets AppError wrap"
  - "ValueError in users/routes.py api_create/api_update caught and re-raised as ValidationError to preserve semantic meaning"
  - "roles/routes.py api_list had no error handling — wrapped in try/except AppError block as part of this migration"

patterns-established:
  - "Standard two-layer except pattern: except AppError: raise / except Exception as e: logging.exception('Unexpected error in {fn}'); raise AppError('Wystapil blad serwera')"
  - "Business logic errors use specific subclasses: ValidationError(400), NotFoundError(404), ConflictError(409)"
  - "Streaming/per-item loop internals remain as-is — only route-level handlers adopt the AppError pattern"

requirements-completed: [IMPR-03]

# Metrics
duration: 10min
completed: 2026-04-03
---

# Phase 6 Plan 02: Route Exception Migration Summary

**140 except-Exception-catch-and-jsonify patterns eliminated across 9 route files — all replaced with typed AppError raises and generic fallback logging**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-03T15:36:02Z
- **Completed:** 2026-04-03T15:46:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Eliminated every `except Exception as e: return jsonify({'error': str(e)})` across all 9 route files
- Replaced explicit `return jsonify({'error': ...}), 4xx` with typed raises (ValidationError, NotFoundError, ConflictError)
- All unexpected exceptions now logged with full tracebacks via `logging.exception()` before re-raising as generic `AppError('Wystapil blad serwera')`
- Global `@app.errorhandler(AppError)` now handles 100% of API errors consistently

## Task Commits

1. **Task 1 (partial — a8d476b already committed): Migrate api_routes.py (81 sites)** - `a8d476b` (feat)
2. **Task 1 (completion): Migrate appointment_routes.py + upload_routes.py** - `0005946` (feat)
3. **Task 2: Migrate 6 minor route files** - `7ccb9c9` (feat)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified

- `routes/appointment_routes.py` — 20 sites: except Exception blocks, explicit 400/404/409 returns, import traceback removed
- `routes/upload_routes.py` — 13 sites: stage_files, get_staged_files, clear_all_staged_files, remove_staged_file, finalize_uploads, view_pdf wrapped; streaming generator internals kept as-is
- `routes/employee_service_routes.py` — 7 sites: all CRUD handlers wrapped
- `routes/income_routes.py` — 3 sites: all handlers wrapped
- `routes/client_preference_routes.py` — 5 sites: all CRUD handlers wrapped
- `routes/service_addon_routes.py` — 6 sites: all CRUD handlers wrapped
- `routes/roles/routes.py` — 4 sites: api_create/api_update refactored, api_list/api_delete newly wrapped
- `routes/users/routes.py` — 3 sites: ValueError re-raised as ValidationError, api_list newly wrapped

## Decisions Made

- Streaming generator in `process_staged_files` (upload_routes.py) kept its internal per-file `except Exception` blocks — they produce SSE `file_complete` error events, not HTTP JSON responses, so the AppError pattern applies only at the outer route level
- `finalize_uploads` per-invoice loop: inner except block retained for file rollback logic — it doesn't leak `str(e)` to clients (sanitizes error messages), outer function wrapped with AppError guard
- `ValueError` in users/routes.py caught and converted to `ValidationError` to preserve semantic meaning from user_repo validation
- `roles/routes.py api_create` and `api_update` moved their validation logic outside the try block (before the DB call) so ValidationError/ConflictError are raised directly, with only the DB operations in try

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The previously failing test `TestIBANValidator.test_iban_inny_kraj_nie_pl` was already failing before this plan — it's a pre-existing issue unrelated to route exception migration. All 274 other tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All route files now use consistent AppError exception pattern
- Global error handler produces uniform JSON for all API errors: `{'success': False, 'error': '<message>'}` with correct HTTP status codes
- No internal error text (stack traces, DB messages) leaks to clients
- Ready for Phase 7 (security hardening) — route handlers are clean and auditable

---
*Phase: 06-code-robustness*
*Completed: 2026-04-03*
