---
phase: 05-data-integrity
plan: 02
subsystem: data-integrity
tags: [alembic, migrations, soft-delete, restore, audit, tests, undo-toast]
dependency_graph:
  requires: [05-01]
  provides: [partial-unique-invoice-constraint, services-soft-delete-columns, restore-endpoints, undo-toast-component]
  affects: [routes/api_routes.py, routes/appointment_routes.py, templates/base.html]
tech_stack:
  added: []
  patterns: [partial-unique-index, already-deleted-detection-410, undo-toast-restore-pattern]
key_files:
  created:
    - alembic/versions/g1h2i3j4k5l6_partial_unique_invoice_number.py
    - alembic/versions/h2i3j4k5l6m7_add_soft_delete_to_services.py
    - templates/components/undo_toast.html
  modified:
    - routes/api_routes.py
    - routes/appointment_routes.py
    - templates/base.html
    - tests/repositories/test_invoice_repository.py
    - tests/repositories/test_soft_delete_repos.py
decisions:
  - "Test assertion for FK non-cascade check fixed from 'DELETE' not in sql to 'DELETE FROM' not in sql — 'DELETED' appears in IS_DELETED column name so the substring test was always false"
metrics:
  duration_minutes: 6
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_changed: 7
---

# Phase 5 Plan 02: Partial Unique Index, Services Soft-Delete, Restore Endpoints Summary

**One-liner:** Partial unique index on invoice_number (WHERE is_deleted=FALSE), services soft-delete migration, four restore POST endpoints with undo toast and already-deleted 410 detection.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create Alembic migrations | ec2b1e9 | g1h2i3j4k5l6_partial_unique_invoice_number.py, h2i3j4k5l6m7_add_soft_delete_to_services.py |
| 2 | Restore endpoints, undo toast, tests | 7c61320 | routes/api_routes.py, routes/appointment_routes.py, templates/components/undo_toast.html, base.html, tests |

## What Was Built

### Alembic Migrations

**Migration g1h2i3j4k5l6** (partial unique index):
- Merges both Alembic heads (e9f0a1b2c3d4 soft-delete columns + c1d2e3f4a5b6 seller PDF passwords)
- Drops global UNIQUE constraint `invoices_invoice_number_key` with PL/pgSQL exception guard
- Creates partial unique index `idx_invoices_invoice_number_active` WHERE is_deleted = FALSE
- Re-uploading a soft-deleted invoice no longer hits a UNIQUE constraint violation

**Migration h2i3j4k5l6m7** (services soft-delete):
- Chains after g1h2i3j4k5l6
- Adds `is_deleted BOOLEAN NOT NULL DEFAULT false` and `deleted_at DATETIME` columns to services table
- Adds `idx_services_is_deleted` index
- Mirrors exact same pattern from e9f0a1b2c3d4 that covered invoices/appointments/clients

### Restore Endpoints (4 total)

| Endpoint | Route | File |
|----------|-------|------|
| restore_invoice | POST /api/invoices/<id>/restore | routes/api_routes.py |
| restore_client | POST /api/clients/<id>/restore | routes/api_routes.py |
| restore_service | POST /api/services/<id>/restore | routes/api_routes.py |
| restore_appointment | POST /appointments/<id>/restore | routes/appointment_routes.py |

All endpoints: set is_deleted=FALSE via repo.restore(), log RESTORE audit event, return {success, message}.

### Delete Endpoint Enhancements

All four delete endpoints updated:
- Return `restore_url` in success response for undo functionality
- Detect already-deleted records (HTTP 410) with `already_deleted: true` in response
- `delete_client` now calls `client_repo.delete()` instead of `client_repo.deactivate()` — proper soft-delete sets is_deleted=TRUE (previously only set is_active=FALSE)

### Undo Toast Component

`templates/components/undo_toast.html` — pure JavaScript, zero dependencies:
- `showUndoToast(message, restoreUrl, duration=8000)` function
- Shows toast with "Cofnij" (Undo) button that POSTs to restoreUrl
- Auto-hides after 8 seconds, cancelled if user hovers
- On successful restore: shows confirmation, reloads page after 2.2s
- Included globally in `templates/base.html`

### Verification Tests

**test_invoice_repository.py** new classes:
- `TestPartialUniqueConstraint` — verifies find_by_invoice_number queries filter is_deleted=FALSE
- `TestAuditDeleteVerification` (FIX-01) — verifies DELETE audit log inserts with correct action/entity_label
- `TestFKConstraintResolution` (FIX-02) — verifies soft-delete uses UPDATE not DELETE FROM, single execute call (no cascade)

**test_soft_delete_repos.py** new classes:
- `TestAppointmentRestore` — verifies restore() sets is_deleted=FALSE, deleted_at=NULL, filters AND is_deleted=TRUE
- `TestServiceRestore` — same for ServiceRepository

Full test count: 53 repository tests, all passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assertion for FKConstraintResolution**
- **Found during:** Task 2 — test_soft_delete_uses_update_not_delete
- **Issue:** Test asserted `'DELETE' not in sql.upper()` but the SQL `IS_DELETED = TRUE, DELETED_AT = CURRENT_TIMESTAMP` contains the substring 'DELETE' (from IS_DELETED and DELETED_AT column names), making the assertion always false
- **Fix:** Changed assertion to `'DELETE FROM' not in sql.upper()` — this correctly tests the intended behavior (no hard-delete SQL) without false positives
- **Files modified:** tests/repositories/test_invoice_repository.py
- **Commit:** 7c61320

## Pre-existing Issues (Out of Scope)

- `tests/utils/test_validators.py::TestIBANValidator::test_iban_inny_kraj_nie_pl` — pre-existing failure, unrelated to this plan. IBANValidator.validate() accepts non-PL IBANs. Logged here but not fixed.

## Self-Check

Checking key artifacts exist and commits are present:
