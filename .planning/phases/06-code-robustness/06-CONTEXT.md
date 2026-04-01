# Phase 6: Code Robustness - Context

**Gathered:** 2026-04-01
**Status:** Ready for research/planning

<domain>
## Phase Boundary

Make all errors specific, named, and catchable. Replace pervasive `except Exception as e: return jsonify({'error': str(e)})` pattern across 40+ route handlers with structured `AppError` subclass handling. Wire up existing but unused `AppointmentStatus` enum into all production code. Replace `SELECT *` with explicit column lists in critical repositories. Fix EmailService error handling throughout. Mask email credentials in logs.

</domain>

<decisions>
## Implementation Decisions

### Exception Handling (IMPR-03)
- Refactor ALL route handlers — `str(e)` leaks internal errors to clients, security risk; replace with `AppError` subclasses + generic user-facing messages
- Reparent `AppointmentError` and `OCRExtractionError` to inherit from `AppError` so the global handler catches them
- Use existing `ConflictError(AppError)` (HTTP 409) for appointment scheduling conflicts — add appointment context in message, don't create separate `AppointmentConflictError`
- Add `DatabaseConnectionError(AppError)` — catch connection failures in `BaseRepository._execute()` single catch point, re-raise as structured error
- Global error handler in `app.py` already exists and works — just needs routes to raise `AppError` subclasses instead of catching everything themselves

### Appointment Status Enum (IMPR-04)
- `AppointmentStatus` class already exists in `config/appointment_statuses.py` with all 7 statuses + state machine
- Wire it into ALL production files: appointment_repository.py, analytics_repository.py, appointment_routes.py, appointment_service.py
- Remove duplicate `VALID_TRANSITIONS` dict from `appointment_service.py` — use the one in `AppointmentStatus`
- Fix bug: `excluded_placeholders()` method referenced in docstring but not defined — remove the reference
- Replace all hardcoded status strings in SQL queries with enum references

### SELECT * Replacement (IMPR-05)
- Override `BaseRepository._columns` in 4 critical repos only: clients, employees, users, income_records
- Other repos keep `SELECT *` — not in scope per requirements
- Use the existing `_columns` mechanism in BaseRepository (already built, just unused)

### EmailService Error Handling (FIX-03 expanded)
- `disconnect()` is already correctly implemented (specific IMAP exceptions + logging)
- Extend scope: fix ALL EmailService error handling:
  - Replace bare `except:` in `_extract_email_body_text()` with specific exceptions + logging
  - Replace `print()` with `logging` throughout all methods
  - Replace broad `except Exception` in `connect()`, `fetch_pdf_attachments()`, `_process_email()`, `_save_attachment()` with specific exception types where possible
- Do NOT change return value patterns (False/[]/None) — callers depend on them

### SQL IN Clause & Credential Masking (IMPR-06)
- SQL IN clause safety is ALREADY resolved — `BaseRepository._in_clause()` exists and is used correctly everywhere
- Redirect scope to email credential masking: ensure email passwords/tokens never appear in log output
- Check `connect()` and error messages for credential leaks

### Claude's Discretion
- Exact column lists for each critical repository (derived from schema/models)
- Error message wording for user-facing error responses (generic, non-leaking)
- Specific IMAP exception types to catch in each EmailService method
- Order of implementation across plans

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `exceptions.py` — `AppError` hierarchy with 5 subclasses (ValidationError, NotFoundError, PermissionDeniedError, ConflictError) + HTTP status codes
- `app.py:172` — Global `@app.errorhandler(AppError)` handler, renders JSON for API, HTML otherwise
- `config/appointment_statuses.py` — `AppointmentStatus` class with 7 statuses, semantic groups (FINAL, ACTIVE, EXCLUDED_FROM_SCHEDULE), state machine transitions
- `repositories/base_repository.py:15-17` — `_columns: str = '*'` override mechanism, used in `get_by_id()` and `get_all()`
- `repositories/base_repository.py:81-90` — `_in_clause()` safe parameterized helper

### Integration Points
- `api_routes.py` — 40+ handlers need `except Exception` → `AppError` subclass migration
- `appointment_routes.py` — hardcoded `ALLOWED_FINAL_STATUSES` list → use `AppointmentStatus.FINAL`
- `employee_service_routes.py` — 7 handlers with `except Exception + str(e)`
- `appointment_repository.py` — 7+ hardcoded status strings in queries
- `analytics_repository.py` — 20+ hardcoded status strings in aggregation queries
- `appointment_service.py` — duplicate `VALID_TRANSITIONS` dict to remove
- `services/email_service.py` — 3 bare `except:` + multiple `print()` + broad `except Exception`
- `services/export_service.py:79` — bare `except:` in column width calculation

### Key Finding
Most Phase 6 infrastructure ALREADY EXISTS but is unused. The work is adoption/wiring, not creation. Only `DatabaseConnectionError` needs to be created new.

</code_context>

<specifics>
## Specific Ideas

- The global error handler in app.py means routes can simply `raise NotFoundError("Invoice not found")` instead of manually building JSON responses — massive simplification
- For analytics_repository.py with 20+ status strings, consider importing enum values at module level to keep queries readable
- `export_service.py:79` bare `except:` is a bonus fix — not in requirements but adjacent to FIX-03

</specifics>

<deferred>
## Deferred Ideas

- Refactoring remaining repos (beyond 4 critical) to use explicit column lists — future milestone
- Adding structured logging (JSON format) across the application — separate concern
- Error monitoring/alerting integration (Sentry, etc.) — separate concern

</deferred>
