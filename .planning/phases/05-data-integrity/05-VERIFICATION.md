---
phase: 05-data-integrity
verified: 2026-04-08T00:00:00Z
status: passed
score: 15/15 must-haves verified
re_verification: false
---

# Phase 5: Data Integrity Verification Report

**Phase Goal:** Deleting a record never destroys its history — all deletions are traceable and recoverable
**Verified:** 2026-04-08
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

Plan 05-01 truths:

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | InvoiceRepository custom queries exclude is_deleted=TRUE | VERIFIED | 11 `is_deleted = FALSE` occurrences in invoice_repository.py |
| 2 | Raw _fetch_all in api_routes.py seller correction excludes soft-deleted | VERIFIED | Line 135: `WHERE is_deleted = FALSE` confirmed |
| 3 | ClientRepository custom queries exclude is_deleted=TRUE | VERIFIED | 9 `is_deleted = FALSE` occurrences in client_repository.py |
| 4 | AppointmentRepository all SELECT methods exclude is_deleted=TRUE | VERIFIED | 20 `is_deleted = FALSE` occurrences in appointment_repository.py |
| 5 | ServiceRepository all SELECT methods exclude is_deleted=TRUE | VERIFIED | 17 `is_deleted = FALSE` occurrences in service_repository.py |
| 6 | AppointmentRepository.delete() does UPDATE is_deleted=TRUE, not DELETE FROM | VERIFIED | Line 459: `UPDATE appointments SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP` — no DELETE FROM found |
| 7 | ServiceRepository.delete() does UPDATE is_deleted=TRUE, not deactivate() | VERIFIED | Line 145: `UPDATE services SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP` — `deactivate` not called from delete() |

Plan 05-02 truths:

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 8 | Re-uploading same invoice_number as soft-deleted succeeds (no UNIQUE violation) | VERIFIED | Migration g1h2i3j4k5l6 drops global UNIQUE, creates partial index `idx_invoices_invoice_number_active WHERE is_deleted = FALSE` |
| 9 | Two active invoices with same invoice_number still blocked | VERIFIED | Same partial unique index enforces uniqueness on is_deleted=FALSE rows |
| 10 | audit_log contains DELETE entry after soft-deleting an invoice | VERIFIED | api_routes.py line 851-859: `audit_repo.log_event(action='DELETE', ...)` — active, not commented |
| 11 | Soft-delete UPDATE does not trigger ON DELETE CASCADE | VERIFIED | AppointmentRepository/ServiceRepository use UPDATE not DELETE; test class TestFKConstraintResolution passes |
| 12 | Services table has is_deleted/deleted_at columns via migration | VERIFIED | Migration h2i3j4k5l6m7 adds both columns to services table with `idx_services_is_deleted` index |
| 13 | Delete API responses include restore_url | VERIFIED | api_routes.py lines 864, 2782, 3123; appointment_routes.py line 529 — all four entities |
| 14 | POST to /api/{entity}/<id>/restore sets is_deleted=FALSE | VERIFIED | restore_invoice (line 876), restore_client (2800), restore_service (3137) in api_routes.py; restore_appointment (541) in appointment_routes.py — all call repo.restore() |
| 15 | Already-deleted record returns specific message, not generic 404 | VERIFIED | invoice/client/service return HTTP 410 with `already_deleted:True`; appointment raises ConflictError (409) — all non-generic |

**Score: 15/15 truths verified**

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `repositories/invoice_repository.py` | All custom queries filter is_deleted=FALSE | VERIFIED | 11 filter sites confirmed |
| `repositories/clients/client_repository.py` | All custom queries filter is_deleted=FALSE | VERIFIED | 9 filter sites confirmed |
| `repositories/appointments/appointment_repository.py` | All SELECT queries filtered, delete() soft-deletes, restore() exists | VERIFIED | 20 filter sites, soft-delete UPDATE, restore() at line 466 |
| `repositories/services/service_repository.py` | All SELECT queries filtered, delete() soft-deletes, restore() exists | VERIFIED | 17 filter sites, soft-delete UPDATE, restore() at line 152 |
| `routes/api_routes.py` | Raw _fetch_all filtered; restore endpoints for invoice/client/service; 410 already-deleted | VERIFIED | All present and wired |
| `routes/appointment_routes.py` | restore_appointment endpoint; already-deleted detection | VERIFIED | restore_appointment at line 541; ConflictError at line 520 |
| `templates/components/undo_toast.html` | Undo toast with Cofnij link | VERIFIED | File exists, contains "Cofnij" at lines 4/26/47/52 |
| `alembic/versions/g1h2i3j4k5l6_partial_unique_invoice_number.py` | Merges Alembic heads, partial unique index WHERE is_deleted=FALSE | VERIFIED | Contains `idx_invoices_invoice_number_active`, merges both heads |
| `alembic/versions/h2i3j4k5l6m7_add_soft_delete_to_services.py` | Adds is_deleted/deleted_at to services | VERIFIED | Adds both columns + idx_services_is_deleted |
| `tests/repositories/test_invoice_repository.py` | TestSoftDelete, TestAuditAfterDelete, TestClientSoftDelete, TestPartialUniqueConstraint, TestAuditDeleteVerification, TestFKConstraintResolution | VERIFIED | All 6 classes present; 26 test methods |
| `tests/repositories/test_soft_delete_repos.py` | TestAppointmentSoftDelete, TestServiceSoftDelete, TestAppointmentRestore, TestServiceRestore | VERIFIED | All 4 classes present; 22 test methods |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `repositories/invoice_repository.py` | `repositories/base_repository.py` | `_soft_delete = True` | VERIFIED | Line 16: `_soft_delete = True` |
| `repositories/clients/client_repository.py` | `repositories/base_repository.py` | `_soft_delete = True` | VERIFIED | Line 15: `_soft_delete = True` |
| `repositories/appointments/appointment_repository.py` | database queries | `AND a.is_deleted = FALSE` in every SELECT | VERIFIED | 20 occurrences confirmed |
| `repositories/services/service_repository.py` | database queries | `AND is_deleted = FALSE` in every SELECT | VERIFIED | 17 occurrences confirmed |
| `alembic/versions/g1h2i3j4k5l6_partial_unique_invoice_number.py` | database schema | `DROP CONSTRAINT invoices_invoice_number_key` + partial index | VERIFIED | PL/pgSQL guard drop + `CREATE UNIQUE INDEX ... WHERE is_deleted = FALSE` |
| `routes/api_routes.py` | `repositories/audit_repository.py` | `audit_repo.log_event(action='DELETE')` | VERIFIED | Lines 851-859, active (not commented) |
| `routes/api_routes.py` restore endpoints | `repositories/base_repository.py` `restore()` | `repo.restore(id)` calls | VERIFIED | restore_invoice/restore_client/restore_service all call repo.restore() |
| `templates/components/undo_toast.html` | `routes/api_routes.py` | `restore_url` in delete response JSON | VERIFIED | All four delete endpoints return `restore_url`; undo_toast.html included globally in base.html (line 89) |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| IMPR-01 | 05-01, 05-02 | Soft delete for invoices and key entities — is_deleted/deleted_at columns, all queries filter WHERE is_deleted=FALSE | SATISFIED | 57 filter sites across 4 repositories; 2 migrations (services columns + partial unique index); 48 tests passing |
| FIX-01 | 05-02 | Audit DELETE operations log correctly — was commented out | SATISFIED | `audit_repo.log_event(action='DELETE', ...)` active at lines 851-859 in delete_invoice |
| FIX-02 | 05-02 | Audit logging FK constraint resolved — soft deletes eliminate cascade conflict | SATISFIED | AppointmentRepository.delete() and ServiceRepository.delete() use UPDATE not DELETE, so ON DELETE CASCADE does not fire; TestFKConstraintResolution verifies this |

**Note:** REQUIREMENTS.md checkboxes for FIX-01 and FIX-02 still show `[ ]` (not ticked). The implementation satisfies both requirements. The doc is a minor documentation debt, not an implementation gap.

---

## Anti-Patterns Found

None. Scanned all 6 modified source files (repositories + routes) for:
- TODO/FIXME/PLACEHOLDER comments — only `placeholders` found, which is legitimate SQL parameterization (`','.join('%s' * len(...))`)
- Empty implementations (`return null`, `return {}`, `return []`) — none found
- Stub delete/restore handlers — none found

---

## Human Verification Required

### 1. Undo Toast UI behavior

**Test:** Delete an invoice from the UI. Observe toast bottom-right.
**Expected:** Toast appears with "Cofnij" button. Clicking it POSTs to restore endpoint and reloads page after 2.2s.
**Why human:** JavaScript toast behavior and timing cannot be verified by grep.

### 2. Partial unique index live database behavior

**Test:** Upload invoice FV/001. Delete it. Re-upload FV/001 (same invoice_number).
**Expected:** Second upload succeeds — no UNIQUE constraint violation.
**Why human:** Migration g1h2i3j4k5l6 must have been applied to the actual database; cannot verify applied state from codebase alone.

### 3. Services table soft-delete columns in production database

**Test:** Check `\d services` in psql, or attempt to delete a service.
**Expected:** `is_deleted` and `deleted_at` columns present; soft-delete works without column-not-found error.
**Why human:** Migration h2i3j4k5l6m7 must have been applied; cannot verify from codebase.

---

## Test Results

```
tests/repositories/test_invoice_repository.py  26 tests passed
tests/repositories/test_soft_delete_repos.py   22 tests passed
Full suite: 291 passed, 1 failed (pre-existing)
```

Pre-existing failure: `TestIBANValidator::test_iban_inny_kraj_nie_pl` — IBANValidator accepts non-PL IBANs. Documented as out-of-scope in both plan summaries. Unrelated to soft-delete work.

---

## Verified Commits

| Commit | Description |
|--------|-------------|
| 0c5c29b | feat(05-01): is_deleted=FALSE filters in InvoiceRepository and ClientRepository |
| 6f53710 | feat(05-01): soft-delete AppointmentRepository and ServiceRepository |
| ec2b1e9 | chore(05-02): Alembic migrations (partial unique index + services soft-delete) |
| 7c61320 | feat(05-02): restore endpoints, already-deleted detection, undo toast, verification tests |

---

_Verified: 2026-04-08_
_Verifier: Claude (gsd-verifier)_
