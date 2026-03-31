# Roadmap: MyWay Nails & Beauty — v3.0 Functional-Improvements

## Overview

v2.0 delivered a complete UI/UX overhaul. v3.0 addresses what's underneath: known bugs causing silent data loss, broad exception handling masking real errors, missing database indexes causing slow queries, and connection management gaps that grow worse under load. Five phases execute in dependency order: data integrity first (unblocks audit logging), then robustness foundations (exception hierarchy enables specific error handling), then security hardening (independent quick fixes), then database performance (indexes enable query optimization), then connection and transaction management (capstone — touches everything above).

## Phases

**Phase Numbering:**
- v2.0 completed at Phase 4
- v3.0 starts at Phase 5
- Integer phases (5, 6, 7...): Planned milestone work
- Decimal phases (5.1, 5.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 5: Data Integrity** - Soft delete for invoices + key entities, audit logging of DELETE operations restored
- [ ] **Phase 6: Code Robustness** - Custom exception hierarchy, appointment status enum, SQL safety helpers, EmailService bare except fixed
- [ ] **Phase 7: Security Hardening** - Secret key validation at startup, environment-based logging configuration
- [ ] **Phase 8: Database Performance** - Indexes on filtered columns, analytics query optimization, employee schedule batching
- [ ] **Phase 9: Connection & Transactions** - Connection pooling, psycopg2 lifecycle management, multi-step transactional integrity, dependency audit

## Phase Details

### Phase 5: Data Integrity
**Goal**: Deleting a record never destroys its history — all deletions are traceable and recoverable
**Depends on**: Nothing (first phase of v3.0)
**Requirements**: IMPR-01, FIX-01, FIX-02
**Success Criteria** (what must be TRUE):
  1. Deleting an invoice via the UI marks it `is_deleted = TRUE` and `deleted_at = now()` — it disappears from the invoice list but remains in the database
  2. After an invoice is soft-deleted, the audit log contains a DELETE entry for that invoice — the audit trail is complete
  3. All invoice list queries return only records where `is_deleted = FALSE` — soft-deleted records never reappear in normal views
  4. The FK constraint conflict between `ON DELETE CASCADE` and post-delete audit logging is gone — no constraint violation when auditing a deletion
**Plans**: TBD

### Phase 6: Code Robustness
**Goal**: Errors are specific, named, and catchable — no bug is silently swallowed
**Depends on**: Phase 5
**Requirements**: IMPR-03, IMPR-04, IMPR-05, IMPR-06, FIX-03
**Success Criteria** (what must be TRUE):
  1. An appointment scheduling conflict raises `AppointmentConflictError` — routes can catch this specific type and return a meaningful user message
  2. An infrastructure failure (database unreachable) raises `DatabaseConnectionError` — distinct from business logic errors, logged with full context
  3. All appointment status values (`completed`, `cancelled`, `no_show`) come from a Python enum — searching the codebase for hardcoded status strings returns zero matches outside the enum definition
  4. Critical repository queries (clients, employees, users, income_records) use explicit column lists — `SELECT *` is absent from these files
  5. EmailService `disconnect()` catches specific IMAP exceptions instead of bare `except: pass` — failures are logged, not silently swallowed
**Plans**: TBD

### Phase 7: Security Hardening
**Goal**: The application refuses to start with insecure defaults — no silent production misconfigurations
**Depends on**: Nothing (independent of Phases 5-6, sequenced after Phase 6)
**Requirements**: FIX-04, FIX-05
**Success Criteria** (what must be TRUE):
  1. Starting the app without `SECRET_KEY` set raises a clear startup error — Flask never boots with a predictable session key
  2. Running the app in production produces INFO-level logs — no DEBUG-level OCR/PDF log entries appear unless `DEBUG=true` is explicitly set in environment
  3. Running with `DEBUG=true` env var produces verbose DEBUG logs — the debug mode is intentional and controllable
**Plans**: TBD

### Phase 8: Database Performance
**Goal**: Common queries return results in milliseconds, not seconds — the scheduler and analytics load without noticeable delay
**Depends on**: Phase 5 (indexes reference soft-delete columns in composite WHERE clauses)
**Requirements**: SCAL-01, SCAL-02, SCAL-03
**Success Criteria** (what must be TRUE):
  1. `EXPLAIN ANALYZE` on appointment queries filtered by `appointment_date`, `employee_id`, or `status` shows index scans, not sequential scans
  2. The employee schedule view loads using a single JOIN query — no N+1 pattern where one query fires per employee
  3. Analytics queries include mandatory date range filters — unbounded full-table aggregations are not possible through normal usage
  4. Composite indexes cover the multi-column WHERE + ORDER BY patterns used in appointment listing and analytics
**Plans**: TBD

### Phase 9: Connection & Transactions
**Goal**: Database connections are never leaked, multi-step operations are atomic, and all packages are current
**Depends on**: Phase 8
**Requirements**: SCAL-04, MIGR-01, MIGR-02, IMPR-02
**Success Criteria** (what must be TRUE):
  1. Creating an appointment that fails mid-operation (e.g. income record insert fails) rolls back all partial changes — no orphaned schedule entries or incomplete records remain
  2. Each web request acquires a database connection at start and releases it at end — no connection held open across idle time or after request completion
  3. Running `pip check` reports zero dependency conflicts — all packages are compatible with each other
  4. Outdated packages flagged as critical security or compatibility risks are upgraded and tested
  5. Connection pool size, timeout, and health check parameters are configurable via environment variables — not hardcoded
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in dependency order: 5 → 6 → 7 → 8 → 9
Phase 7 is independent but sequenced after Phase 6 for focus.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Data Integrity | 0/? | Not started | - |
| 6. Code Robustness | 0/? | Not started | - |
| 7. Security Hardening | 0/? | Not started | - |
| 8. Database Performance | 0/? | Not started | - |
| 9. Connection & Transactions | 0/? | Not started | - |
