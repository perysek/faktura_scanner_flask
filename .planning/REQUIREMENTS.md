# Requirements: MyWay Nails & Beauty — Functional-Improvements

**Defined:** 2026-03-31
**Core Value:** Recepcjonistka i stylistka muszą sprawnie zarządzać rezerwacjami i klientami
**Source:** Codebase concerns audit `.planning/codebase/CONCERNS.md` (2026-03-13)

## v3.0 Requirements

Requirements for the Functional-Improvements milestone. Each maps to a specific concern from the codebase audit.

### Fixes (Bugs & Critical Tech Debt)

- [ ] **FIX-01**: Audit DELETE operations log correctly — currently commented out in api_routes.py, deletions are silently unaudited
- [ ] **FIX-02**: Audit logging FK constraint resolved — soft deletes eliminate the cascade conflict between ON DELETE CASCADE and post-delete logging
- [x] **FIX-03**: EmailService bare `except: pass` in disconnect() replaced with specific IMAP exception handlers and logging
- [x] **FIX-04**: Debug logging configuration moved to environment-based settings — INFO level in production, DEBUG only when explicitly enabled
- [x] **FIX-05**: Flask SECRET_KEY hardcoded fallback removed — app raises error at startup if SECRET_KEY env var is not set

### Improvements (Code Robustness)

- [x] **IMPR-01**: Soft delete for invoices and key entities — `is_deleted` boolean + `deleted_at` timestamp columns, all queries filter `WHERE is_deleted = FALSE`
- [x] **IMPR-02**: Multi-step operations (appointment creation/update/delete) wrapped in database transactions with savepoints and rollback on failure
- [x] **IMPR-03**: Custom exception hierarchy created — business logic errors (e.g. AppointmentConflictError) vs infrastructure errors (e.g. DatabaseConnectionError), routes catch specific types
- [x] **IMPR-04**: Appointment status values defined as Python enum with PostgreSQL CHECK constraint — replaces hardcoded strings ('completed', 'cancelled', 'no_show') across all queries
- [x] **IMPR-05**: `SELECT *` in base_repository.py replaced with explicit column lists in critical repositories (clients, employees, users, income_records)
- [x] **IMPR-06**: Safe SQL IN clause helper function created for parameterized queries; email credential values masked in error messages and logs

### Scaling (Performance & Database)

- [x] **SCAL-01**: Database indexes added on frequently filtered columns — appointments.appointment_date, appointments.employee_id, appointments.status, income_records.appointment_id, and composite indexes for multi-column WHERE + ORDER BY
- [x] **SCAL-02**: Analytics repository complex queries optimized — heavy aggregations refactored, STRING_AGG operations bounded, date range filtering enforced
- [x] **SCAL-03**: Employee schedule fetching refactored from separate per-employee queries to single JOIN query with date range filter
- [x] **SCAL-04**: Database connection pooling implemented — proper pool size management, connection timeout, health checks, cleanup on request end

### Migration Paths (Dependencies & Architecture)

- [x] **MIGR-01**: Deprecated/outdated packages audited via `pip check` and `pip list --outdated` — critical updates applied with compatibility testing
- [x] **MIGR-02**: Psycopg2 connection management improved — connection lifecycle tied to request scope, timeout configuration, leak prevention via context managers

## v4.0 Requirements

Deferred to future milestone.

### Test Coverage

- **TEST-01**: OCR/PDF processing unit tests — regex patterns, PDF parsing, corrupted file handling
- **TEST-02**: API route unit tests — request validation, permission checks, response serialization, error scenarios
- **TEST-03**: Date/time handling tests — DateParser edge cases, leap years, DST transitions
- **TEST-04**: Database migration up/down safety tests — idempotency, rollback integrity

### UI Polish (Carry-over)

- **SPAC-02**: Max-width normalization across templates (900px forms, 1400px lists, full-width calendars)

### Advanced Security

- **RLS-01**: PostgreSQL Row-Level Security policies per role (employees see own data, admins see all)

## Out of Scope

| Feature | Reason |
|---------|--------|
| SQLAlchemy ORM migration | Too large for this milestone — psycopg2 improvements sufficient |
| Async PDF/OCR processing (Celery) | Scaling limit exists but not blocking current usage |
| Email queue system (Redis/Celery) | Email service is optional feature, low priority |
| Full RLS implementation | Complex, requires separate milestone with security focus |
| Dark mode | No user demand |
| Mobile app | Web-first |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | Phase 5 | Pending |
| FIX-02 | Phase 5 | Pending |
| FIX-03 | Phase 6 | Complete |
| FIX-04 | Phase 7 | Complete |
| FIX-05 | Phase 7 | Complete |
| IMPR-01 | Phase 5 | Complete |
| IMPR-02 | Phase 9 | Complete |
| IMPR-03 | Phase 6 | Complete |
| IMPR-04 | Phase 6 | Complete |
| IMPR-05 | Phase 6 | Complete |
| IMPR-06 | Phase 6 | Complete |
| SCAL-01 | Phase 8 | Complete |
| SCAL-02 | Phase 8 | Complete |
| SCAL-03 | Phase 8 | Complete |
| SCAL-04 | Phase 9 | Complete |
| MIGR-01 | Phase 9 | Complete |
| MIGR-02 | Phase 9 | Complete |

**Coverage:**
- v3.0 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-04-08 — v3.0 milestone complete, 15/17 requirements implemented (FIX-01, FIX-02 deferred to Phase 5 human verification)*
