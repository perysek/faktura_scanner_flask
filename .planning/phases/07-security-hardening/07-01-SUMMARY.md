---
phase: 07-security-hardening
plan: 01
subsystem: infra
tags: [flask, security, logging, environment, startup-validation]

# Dependency graph
requires:
  - phase: 06-code-robustness
    provides: AppError exception hierarchy and route-level error handling
provides:
  - SECRET_KEY required at all times with RuntimeError on missing key
  - Log-level controlled by explicit DEBUG=true env var, not FLASK_ENV

affects: [app.py, any phase modifying startup configuration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Startup validation: raise RuntimeError for missing required env vars
    - Log verbosity: explicit DEBUG=true env var instead of implicit FLASK_ENV

key-files:
  created: []
  modified:
    - app.py

key-decisions:
  - "RuntimeError (not ValueError) for startup misconfiguration: startup happens before Flask request context where AppError is appropriate"
  - "SECRET_KEY guard is unconditional: no dev bypass via FLASK_ENV, enforces key from day one of development"
  - "DEBUG env var explicit opt-in: avoids log verbosity leaking into staging environments that share FLASK_ENV=development"

patterns-established:
  - "Startup guard pattern: os.environ.get('VAR'); if not var: raise RuntimeError('...message with fix hint...')"
  - "Log level pattern: os.environ.get('DEBUG', '').lower() == 'true' for explicit debug activation"

requirements-completed: [FIX-04, FIX-05]

# Metrics
duration: 2min
completed: 2026-04-08
---

# Phase 7 Plan 01: Security Hardening - Startup Validation Summary

**SECRET_KEY is now unconditionally required at startup with RuntimeError including token_hex generation hint; log verbosity switched from implicit FLASK_ENV to explicit DEBUG=true env var**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-08T03:14:48Z
- **Completed:** 2026-04-08T03:17:04Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Removed `dev-only-insecure-key` fallback — Flask will never boot with a predictable session key
- RuntimeError message includes exact command to generate a secure key (`python -c "import secrets; print(secrets.token_hex(32))"`)
- Removed FLASK_ENV-based log trigger — DEBUG level now requires explicit `DEBUG=true` env var
- Verbose per-logger debug (pdf_processor, ocr_service) preserved and still gates on the same condition

## Task Commits

Each task was committed atomically:

1. **Task 1: Switch log-level trigger from FLASK_ENV to DEBUG env var** - `e36a7f6` (fix)
2. **Task 2: Remove SECRET_KEY hardcoded fallback, always raise RuntimeError** - `44dd5f1` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app.py` - Log-level trigger and SECRET_KEY guard hardened

## Decisions Made
- RuntimeError chosen over ValueError: startup misconfiguration is a runtime environment problem, not a value validation problem; aligns with Python stdlib convention
- No FLASK_ENV exception for development: forces developers to set SECRET_KEY from day one, preventing accidental prod deployments without the variable
- `os.environ.get('DEBUG', '').lower() == 'true'` pattern: handles case-insensitive values and avoids KeyError on missing var

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `create_app()` smoke test raised `RuntimeError` from `database.py` (DATABASE_URL not set in test env) rather than returning app — confirmed this is expected behavior, SECRET_KEY guard passed correctly before database init

## User Setup Required
None - no external service configuration required. Existing `.env` files need `SECRET_KEY` set if not already present.

## Next Phase Readiness
- Security hardening plan 01 complete
- app.py startup is now production-safe: no insecure defaults, no implicit environment assumptions
- All references to FLASK_ENV removed from app.py; future plans should not reintroduce FLASK_ENV conditionals

---
*Phase: 07-security-hardening*
*Completed: 2026-04-08*
