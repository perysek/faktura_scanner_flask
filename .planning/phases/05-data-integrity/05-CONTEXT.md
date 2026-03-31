# Phase 5: Data Integrity - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement complete soft-delete pattern for invoices and key entities (clients, appointments, services). All deletions become traceable and recoverable — records are flagged `is_deleted = TRUE` with `deleted_at` timestamp instead of being physically removed. Audit logging works correctly for all DELETE operations. FK constraint conflicts eliminated by soft-delete pattern.

</domain>

<decisions>
## Implementation Decisions

### Delete User Experience
- Delete confirmation wording stays unchanged — "Usuń" (Delete), no rename to "Archiwizuj"
- After soft-delete, show a toast notification with "Cofnij" (Undo) link allowing immediate restore
- No admin "trash" view for soft-deleted records — recovery is at DB level only
- If a user targets an already-deleted record (stale tab), return "already deleted" message rather than generic 404

### Data Lifecycle & Edge Cases
- Soft-delete extends to clients, appointments, and services — not just invoices (IMPR-01 "key entities" interpretation)
- Seller hard-delete asymmetry preserved — sellers are not in IMPR-01 scope; invoices linked to deleted sellers survive via soft-delete
- Alembic migration uses IF EXISTS guard for constraint name — production may differ from dev

### Claude's Discretion
- Internal implementation details of the undo toast (duration, placement, restore API endpoint design)
- Test structure and naming conventions for new soft-delete tests
- Order of implementation within waves (query filters vs migration vs undo UX)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseRepository._soft_delete` flag — already implemented in `repositories/base_repository.py` (lines 19-117), handles `get_by_id`, `get_all`, and `delete` automatically
- `InvoiceRepository._soft_delete = True` — already set (line 16), `delete()` already performs UPDATE instead of DELETE
- Migration `e9f0a1b2c3d4_add_soft_delete_columns.py` — already adds `is_deleted`/`deleted_at` to invoices, appointments, clients tables
- `audit_repo.log_event()` — audit DELETE call already exists in `api_routes.py` lines 809-817
- `audit_log` table FK constraint on `invoice_id` already removed (schema.sql lines 60-69)

### Established Patterns
- Repository pattern with `BaseRepository` providing common CRUD; child repos override with custom queries
- `_soft_delete` flag in BaseRepository controls filter behavior for `get_by_id` and `get_all`
- Custom query methods (search, get_by_date_range, etc.) bypass base class and write raw SQL — these need manual `is_deleted = FALSE` filters
- Alembic migrations chain via `down_revision`; latest is `e9f0a1b2c3d4`
- Toast notifications pattern exists in templates for flash messages

### Integration Points
- `InvoiceRepository` — 8+ custom query methods need `AND is_deleted = FALSE`: search, get_by_date_range, get_by_seller, find_by_invoice_number, find_by_invoice_number_and_seller, get_recent, get_upcoming_payments, get_overdue_payments, get_statistics
- `api_routes.py:127` — raw `_fetch_all` query bypasses repository filter
- `DuplicateDetectionService.check_duplicate()` — calls `find_by_invoice_number_and_seller()` which must exclude soft-deleted
- `delete_seller` endpoint — loops and calls `invoice_repo.delete()` (already soft-delete), seller itself stays hard-delete
- `invoice_number UNIQUE` constraint — must become partial unique index (`WHERE is_deleted = FALSE`)
- ClientRepository, AppointmentRepository, ServiceRepository — need `_soft_delete = True` flag and custom query audits
- Services table — may need `is_deleted`/`deleted_at` columns added via new migration

</code_context>

<specifics>
## Specific Ideas

- User wants "Cofnij" (Undo) toast after delete — implies a restore API endpoint and brief undo window
- Soft-delete scope explicitly expanded to include clients, appointments, and services (not just invoices)
- "Already deleted" response preferred over 404 for stale delete attempts — friendlier UX

</specifics>

<deferred>
## Deferred Ideas

- **90-day auto-purge**: User requested automatic hard-deletion of soft-deleted records after 90 days. Requires new infrastructure (management script, cron/scheduler). Deferred — can be a future phase addition or separate task.
- **Admin trash view**: Explicitly declined for Phase 5, but could be useful in a future milestone.

</deferred>
