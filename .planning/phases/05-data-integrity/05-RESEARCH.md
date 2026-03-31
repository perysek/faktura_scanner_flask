# Phase 5: Data Integrity - Research

**Researched:** 2026-03-31
**Domain:** Soft delete pattern, PostgreSQL constraint management, audit logging, psycopg2/Flask/Alembic
**Confidence:** HIGH

## Summary

Phase 5 implements three tightly coupled requirements: soft delete for invoices (IMPR-01), correct DELETE audit logging (FIX-01), and resolution of the FK constraint conflict between `ON DELETE CASCADE` on `duplicate_detection` and post-delete audit logging (FIX-02).

The good news is that the infrastructure is already partially in place. `BaseRepository` has `_soft_delete` flag support (lines 19–117), `InvoiceRepository` already sets `_soft_delete = True` (line 16), the migration `e9f0a1b2c3d4_add_soft_delete_columns.py` already adds `is_deleted` and `deleted_at` columns to the `invoices` table (and `appointments`, `clients`), and `delete_invoice` in `api_routes.py` already calls `invoice_repo.delete(invoice_id)` which, because `_soft_delete = True`, already does `UPDATE invoices SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP`. The audit call immediately after (lines 809–817) also already exists and appears to be working.

What is NOT done: several `InvoiceRepository` query methods (`search`, `get_by_date_range`, `get_by_seller`, `find_by_invoice_number`, `find_by_invoice_number_and_seller`, `get_recent`, `get_upcoming_payments`, `get_overdue_payments`, `get_statistics`) do NOT filter `WHERE is_deleted = FALSE`. There is also a raw `_fetch_all` call in `api_routes.py` line 127–132 that queries `invoices` directly without the filter. The `duplicate_detection` table has `FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE` — this means a hard DELETE of an invoice cascades there, but since `InvoiceRepository.delete()` is now a soft delete (UPDATE), the cascade no longer fires for invoice deletes. However a soft-deleted invoice with `invoice_number UNIQUE` constraint will block re-uploading the same invoice number.

The `audit_log` table's FK constraint has already been removed via the idempotent migration block in `schema.sql` (lines 60–69). The `invoice_id` column in `audit_log` has no FK constraint now — it is a plain `INTEGER`. So FIX-02 is mostly resolved at the schema level already; the concern note in CONCERNS.md describes the historical problem that the schema migration already addresses.

**Primary recommendation:** The work is focused: (1) add `AND is_deleted = FALSE` filters to the remaining InvoiceRepository query methods that bypass the base `get_all`/`get_by_id`, (2) add a partial unique index on `invoice_number WHERE is_deleted = FALSE` to replace the global UNIQUE constraint (so a soft-deleted invoice's number can be reused), (3) verify the audit DELETE call works correctly end-to-end, (4) verify `duplicate_detection` ON DELETE CASCADE does not cause issues with soft delete (it doesn't — no hard DELETE fires), (5) wire up a new Alembic migration for the partial unique index change.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| IMPR-01 | Soft delete for invoices — `is_deleted` boolean + `deleted_at` timestamp, all queries filter `WHERE is_deleted = FALSE` | Columns exist (migration e9f0a1b2c3d4). `BaseRepository.delete()` already does soft delete. Need to fix 8 InvoiceRepository methods + 1 raw query in api_routes that skip the filter. Also need to fix UNIQUE constraint on invoice_number to be partial. |
| FIX-01 | Audit DELETE operations log correctly | The `delete_invoice` route already calls `audit_repo.log_event(action='DELETE')` after `invoice_repo.delete()`. Because soft delete (UPDATE) keeps the invoice row alive, `invoice_id` in audit_log no longer risks FK violation. Verify end-to-end. |
| FIX-02 | Audit logging FK constraint resolved — soft deletes eliminate cascade conflict | `audit_log` has no FK constraint (removed in schema.sql lines 60–69). `duplicate_detection` FK is ON DELETE CASCADE but only fires on hard DELETE — soft delete (UPDATE) does not trigger it. The FK concern is already resolved at schema level; this task verifies and documents it. |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg2 | 2.x (project-pinned) | PostgreSQL driver | Already in use project-wide |
| Alembic | 1.x (project-pinned) | Database migrations | Already in use, all schema changes go through migrations |
| pytest | 8.3.4 | Test framework | Already in requirements-dev.txt |
| pytest-mock | 3.14.0 | Mock patching | Already in requirements-dev.txt |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| factory-boy | 3.3.1 | Test data factories | If creating repository-level integration tests with real DB fixtures |

**Installation:** No new libraries required — all stack components are already installed.

---

## Architecture Patterns

### Soft Delete in this Codebase

The project already uses a consistent soft-delete pattern in `BaseRepository`:

```python
# BaseRepository — already exists
_soft_delete: bool = False  # set True in child repo

def get_by_id(self, id: int):
    soft = " AND is_deleted = FALSE" if self._soft_delete else ""
    query = f"SELECT {self._columns} FROM {self.table_name} WHERE id = %s{soft}"
    ...

def get_all(self) -> List[Any]:
    soft = " WHERE is_deleted = FALSE" if self._soft_delete else ""
    query = f"SELECT {self._columns} FROM {self.table_name}{soft} ORDER BY id DESC"
    ...

def delete(self, id: int) -> bool:
    if self._soft_delete:
        query = f"UPDATE {self.table_name} SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP WHERE id = %s"
    else:
        query = f"DELETE FROM {self.table_name} WHERE id = %s"
    cursor = self._execute(query, (id,))
    return cursor.rowcount > 0
```

`InvoiceRepository` already sets `_soft_delete = True`, so `get_by_id` and `get_all` are already filtered. The gap is the custom query methods.

### Pattern: Add is_deleted Filter to Custom Queries

For every custom `SELECT` query in `InvoiceRepository`, add `AND is_deleted = FALSE` to the WHERE clause:

```python
# Before (missing filter):
def search(self, search_term: str) -> List[Any]:
    query = """
        SELECT * FROM invoices
        WHERE seller_name ILIKE %s
           OR invoice_number ILIKE %s
           OR seller_nip ILIKE %s
        ORDER BY invoice_date DESC
    """

# After (correct):
def search(self, search_term: str) -> List[Any]:
    query = """
        SELECT * FROM invoices
        WHERE is_deleted = FALSE
          AND (seller_name ILIKE %s
           OR invoice_number ILIKE %s
           OR seller_nip ILIKE %s)
        ORDER BY invoice_date DESC
    """
```

This same fix applies to: `find_by_invoice_number`, `find_by_invoice_number_and_seller`, `get_by_date_range`, `get_by_seller`, `get_recent`, `get_upcoming_payments`, `get_overdue_payments`, `get_statistics` (all inner queries), and the raw `_fetch_all` call in `api_routes.py:127`.

### Pattern: Partial UNIQUE Index for invoice_number

The current schema has `invoice_number TEXT NOT NULL UNIQUE`. With soft delete, a re-uploaded invoice with the same number as a soft-deleted one will fail the UNIQUE constraint. The correct fix is a **partial unique index**:

```sql
-- Drop the existing full UNIQUE constraint
ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key;

-- Create partial unique index: only active (non-deleted) invoices must be unique
CREATE UNIQUE INDEX idx_invoices_invoice_number_active
    ON invoices (invoice_number)
    WHERE is_deleted = FALSE;
```

This allows the same invoice_number to exist multiple times as long as at most one has `is_deleted = FALSE`. The Alembic migration for this should follow migration `e9f0a1b2c3d4`.

### Pattern: Alembic Migration Authoring

New migration chaining from `e9f0a1b2c3d4`:

```python
revision: str = '<new_rev_id>'
down_revision: Union[str, None] = 'e9f0a1b2c3d4'

def upgrade() -> None:
    # Drop global UNIQUE constraint
    op.drop_constraint('invoices_invoice_number_key', 'invoices', type_='unique')
    # Create partial unique index (only active invoices)
    op.execute("""
        CREATE UNIQUE INDEX idx_invoices_invoice_number_active
        ON invoices (invoice_number)
        WHERE is_deleted = FALSE
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_invoices_invoice_number_active")
    op.create_unique_constraint('invoices_invoice_number_key', 'invoices', ['invoice_number'])
```

Note: Alembic does not have a native `op.create_index` option for partial indexes — use `op.execute` with raw SQL.

### Audit DELETE Flow (Current State)

```
UI deleteInvoice(id)
  → DELETE /api/invoices/<id>
    → invoice_repo.get_by_id(id)     # fetch before soft-delete (for invoice_number)
    → invoice_repo.delete(id)         # UPDATE is_deleted=TRUE, deleted_at=now()
    → seller_repo.decrement_invoice_count(seller_id)
    → audit_repo.log_event(           # row still exists → no FK conflict
        entity_type='invoice',
        action='DELETE',
        entity_id=invoice_id,
        entity_label=invoice.invoice_number,
        ...
      )
    → return {"success": True}
```

This flow already exists in `delete_invoice` (api_routes.py lines 786–825). Because the row is NOT deleted (only flagged), `invoice_id` in the audit_log INSERT is valid and not subject to cascade deletion.

### Anti-Patterns to Avoid

- **Hard delete in the delete endpoint:** Do not change `invoice_repo.delete()` to a hard DELETE — that re-introduces the FK cascade problem for `duplicate_detection`.
- **Removing the UNIQUE constraint without adding a partial index:** This would allow genuine invoice number duplicates (same invoice uploaded twice while active).
- **Filtering `is_deleted` in templates/JS instead of SQL:** The filter must be enforced server-side in the repository layer, not at the presentation layer.
- **Using `_fetch_all` or raw queries that bypass the repository:** The raw `_fetch_all` call in `api_routes.py:127` queries the invoices table directly — it must also add `AND is_deleted = FALSE`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migrations | Manual SQL via psycopg2 | Alembic | Version-controlled, reversible, team-safe |
| Partial unique index | Application-level uniqueness check | PostgreSQL partial UNIQUE index | DB-enforced, atomic, works under concurrent requests |
| Soft delete infrastructure | Custom delete flag per repository | `_soft_delete = True` in BaseRepository | Already built; consistent across all repos |

**Key insight:** The soft delete infrastructure (`_soft_delete`, `is_deleted` column, migration) is already in the codebase. The work here is completing the gaps — not building a new system.

---

## Common Pitfalls

### Pitfall 1: UNIQUE Constraint Blocks Re-upload After Soft Delete

**What goes wrong:** User soft-deletes invoice FV/2026/001. Later tries to re-upload the same invoice. PostgreSQL rejects with `duplicate key value violates unique constraint "invoices_invoice_number_key"` even though the active copy was deleted.

**Why it happens:** The global `UNIQUE` constraint on `invoice_number` applies to all rows, including `is_deleted = TRUE` rows.

**How to avoid:** Replace global UNIQUE with partial UNIQUE index (`WHERE is_deleted = FALSE`). This is an Alembic migration task.

**Warning signs:** Integration tests that soft-delete then re-create will fail with integrity errors before this fix.

### Pitfall 2: Duplicate Detection Returns Soft-Deleted Records as Existing

**What goes wrong:** `DuplicateDetectionService.check_duplicate()` calls `find_by_invoice_number_and_seller()` which queries without `is_deleted = FALSE`. A soft-deleted invoice is returned as an "existing" invoice, blocking re-upload with "duplicate detected" error.

**Why it happens:** `find_by_invoice_number_and_seller` and `find_by_invoice_number` do not filter by `is_deleted`.

**How to avoid:** Add `AND is_deleted = FALSE` to both `find_by_invoice_number` and `find_by_invoice_number_and_seller` queries.

**Warning signs:** After soft-deleting an invoice, uploading the same PDF again reports "duplicate detected" instead of creating a new record.

### Pitfall 3: Statistics Include Soft-Deleted Invoices

**What goes wrong:** Dashboard shows wrong totals — amounts from deleted invoices appear in the paid/unpaid counts and financial sums.

**Why it happens:** `get_statistics()` has inner queries (`FROM invoices`) without `WHERE is_deleted = FALSE`.

**How to avoid:** Add `WHERE is_deleted = FALSE` (or `AND is_deleted = FALSE`) to all sub-queries within `get_statistics()`.

### Pitfall 4: Raw _fetch_all in api_routes Bypasses Repository Filter

**What goes wrong:** The seller data correction endpoint (`api_routes.py:127`) uses `current_app.invoice_repo._fetch_all("""SELECT ... FROM invoices ...""")` — a raw query that bypasses all `_soft_delete` logic. Soft-deleted invoices appear in seller correction analysis.

**Why it happens:** Direct use of `_fetch_all` with hand-written SQL skips the repository's `_soft_delete` guard.

**How to avoid:** Add `AND is_deleted = FALSE` to the WHERE clause of this raw query, or refactor it to call a repository method.

### Pitfall 5: audit_log LEFT JOIN on Soft-Deleted Invoices Breaks History Display

**What goes wrong:** `AuditRepository.get_all()` does `LEFT JOIN invoices i ON a.invoice_id = i.id` to fetch `invoice_number`. After soft delete, the invoice row still exists (`is_deleted = TRUE`) so the JOIN still returns `invoice_number` correctly. This is actually fine — no pitfall here. However, if a future migration hard-deletes old records, the JOIN will return NULL for deleted invoices.

**How to avoid:** The LEFT JOIN is correct. The audit record stores `entity_label = invoice_number` at log time as a separate column, which serves as a fallback. Verify that `entity_label` is populated on DELETE events (it is: `entity_label=getattr(invoice, 'invoice_number', None)` in `delete_invoice`).

### Pitfall 6: duplicate_detection ON DELETE CASCADE

**What goes wrong:** Confusion about whether `FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE` in `duplicate_detection` is a problem.

**Why it is NOT a problem with soft delete:** Soft delete performs `UPDATE invoices SET is_deleted = TRUE` — not `DELETE`. PostgreSQL ON DELETE CASCADE only fires on a `DELETE` statement. The cascade never fires. No Alembic migration needed for `duplicate_detection`.

---

## Code Examples

### Example 1: Fixed find_by_invoice_number (add is_deleted filter)

```python
# Source: existing repositories/invoice_repository.py pattern
def find_by_invoice_number(self, invoice_number: str) -> Optional[Any]:
    """Znajdź aktywną fakturę po numerze (pomija soft-deleted)"""
    query = "SELECT * FROM invoices WHERE invoice_number = %s AND is_deleted = FALSE"
    return self._fetch_one(query, (invoice_number,))
```

### Example 2: Fixed get_statistics inner queries

```python
# Add is_deleted = FALSE to both sub-queries in get_statistics
query_basic = """
    SELECT
        COUNT(*) as total_count,
        COUNT(CASE WHEN status = 'Opłacona' THEN 1 END) as paid_count,
        COUNT(CASE WHEN status = 'Nieopłacona' THEN 1 END) as unpaid_count
    FROM invoices
    WHERE is_deleted = FALSE
"""

query_amounts = """
    SELECT currency, status, payment_status,
           SUM(amount) as total_amount, COUNT(*) as count
    FROM (
        SELECT currency, status, amount,
               CASE
                   WHEN status = 'Nieopłacona' AND payment_due_date < CURRENT_DATE THEN 'overdue'
                   WHEN status = 'Nieopłacona' THEN 'unpaid'
                   WHEN status = 'Opłacona' THEN 'paid'
                   ELSE 'unpaid'
               END as payment_status
        FROM invoices
        WHERE is_deleted = FALSE
    ) sub
    GROUP BY currency, status, payment_status
"""
```

### Example 3: Alembic migration — partial unique index

```python
# alembic/versions/<rev>_add_partial_unique_invoice_number.py
from alembic import op

revision = '<new_rev>'
down_revision = 'e9f0a1b2c3d4'

def upgrade() -> None:
    op.drop_constraint('invoices_invoice_number_key', 'invoices', type_='unique')
    op.execute("""
        CREATE UNIQUE INDEX idx_invoices_invoice_number_active
        ON invoices (invoice_number)
        WHERE is_deleted = FALSE
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_invoices_invoice_number_active")
    op.create_unique_constraint(
        'invoices_invoice_number_key', 'invoices', ['invoice_number']
    )
```

### Example 4: Verify audit DELETE event already in place

```python
# routes/api_routes.py — lines 809–817 (already present, just verify)
current_app.audit_repo.log_event(
    entity_type='invoice',
    action='DELETE',
    entity_id=invoice_id,
    entity_label=getattr(invoice, 'invoice_number', None),
    field_name='status',
    old_value='active',
    new_value='deleted',
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard delete (DELETE FROM invoices) | Soft delete (UPDATE is_deleted=TRUE) | BaseRepository already implements, InvoiceRepository already has `_soft_delete=True` | Row preserved, FK cascade never fires |
| `invoice_number TEXT NOT NULL UNIQUE` (global) | `UNIQUE INDEX WHERE is_deleted = FALSE` (partial) | Phase 5 Alembic migration | Re-upload after soft-delete works |
| Audit log had FK REFERENCES invoices(id) | audit_log.invoice_id has no FK (schema.sql migration dropped it) | Already in schema.sql | Post-delete audit INSERT no longer violates FK |

**The implementation gap is narrower than CONCERNS.md implies.** The schema migration (`e9f0a1b2c3d4`) and `BaseRepository.delete()` already do the heavy lifting. Phase 5 is about completing the last-mile: query filters, partial unique index, and verification.

---

## Open Questions

1. **Is the Alembic chain on production in sync with the migration files?**
   - What we know: Migration `e9f0a1b2c3d4` exists and adds `is_deleted`/`deleted_at` columns.
   - What's unclear: Whether the production database has this migration applied (i.e., whether columns exist already).
   - Recommendation: Run `alembic current` at the start of implementation to verify; the migration task should check `alembic upgrade head` is safe before applying the partial unique index migration.

2. **Does the delete_seller endpoint (lines 1900–1946) need soft-delete handling for its cascade invoice deletes?**
   - What we know: `delete_seller` loops over linked invoices and calls `invoice_repo.delete(invoice.id)` — which is already soft delete. Then calls `seller_repo.delete(seller_id)` — `SellerRepository` does NOT have `_soft_delete = True`, so sellers are hard-deleted.
   - What's unclear: Whether sellers should also be soft-deleted (out of scope for Phase 5 per requirements — IMPR-01 is invoices only).
   - Recommendation: Leave seller hard-delete unchanged. Confirm in plan that invoices linked to a soft-deleted seller remain accessible via audit log.

3. **invoice_number UNIQUE constraint name in production**
   - What we know: Schema defines `invoice_number TEXT NOT NULL UNIQUE`, which PostgreSQL auto-names `invoices_invoice_number_key`.
   - What's unclear: Whether the constraint was created with a custom name on the production instance.
   - Recommendation: In the Alembic migration, use `IF EXISTS` guard or check constraint name dynamically before dropping.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | `pytest.ini` (testpaths = tests) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IMPR-01 | `invoice_repo.delete()` sets `is_deleted=TRUE`, `deleted_at=now()` | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete -x` | ❌ Wave 0 |
| IMPR-01 | `get_all()` excludes is_deleted invoices | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_get_all_excludes_deleted -x` | ❌ Wave 0 |
| IMPR-01 | `search()` excludes is_deleted invoices | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_search_excludes_deleted -x` | ❌ Wave 0 |
| IMPR-01 | `get_statistics()` excludes is_deleted invoices | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_statistics_excludes_deleted -x` | ❌ Wave 0 |
| IMPR-01 | Re-upload of same invoice_number after soft-delete succeeds (partial unique index) | unit | `pytest tests/repositories/test_invoice_repository.py::TestPartialUniqueConstraint -x` | ❌ Wave 0 |
| IMPR-01 | Duplicate detection ignores soft-deleted invoices | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_find_by_number_excludes_deleted -x` | ❌ Wave 0 |
| FIX-01 | DELETE endpoint logs audit entry with action='DELETE' | unit | `pytest tests/routes/test_api_routes.py::TestDeleteInvoice -x` | ✅ (partial — `test_audit_log_event_delete_signature` exists) |
| FIX-02 | audit_log INSERT after soft-delete does not raise FK violation | unit | `pytest tests/repositories/test_invoice_repository.py::TestAuditAfterDelete -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/repositories/test_invoice_repository.py` — covers IMPR-01 soft delete behavior, FIX-02 audit FK
- [ ] `tests/repositories/__init__.py` — may already exist (directory has `__init__.py`)

*(Existing: `tests/routes/test_api_routes.py::TestDeleteInvoice::test_audit_log_event_delete_signature` covers FIX-01 partially — it tests the `log_event` call signature but not the full HTTP DELETE flow.)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `repositories/base_repository.py`, `repositories/invoice_repository.py`, `repositories/audit_repository.py`, `routes/api_routes.py`, `database/schema.sql`, `alembic/versions/e9f0a1b2c3d4_add_soft_delete_columns.py`
- PostgreSQL documentation knowledge (partial unique indexes, ON DELETE CASCADE behavior) — HIGH confidence, stable feature since PostgreSQL 8.x

### Secondary (MEDIUM confidence)
- `.planning/codebase/CONCERNS.md` — describes the original problems; codebase inspection shows some are already resolved

### Tertiary (LOW confidence)
- None — all findings are based on direct codebase inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all tooling already in project
- Architecture: HIGH — code directly inspected, patterns are already partially implemented
- Pitfalls: HIGH — derived from actual code analysis (missing WHERE clauses confirmed by reading the query methods), not speculation

**Research date:** 2026-03-31
**Valid until:** 2026-05-01 (stable Python/PostgreSQL codebase, no fast-moving dependencies)
