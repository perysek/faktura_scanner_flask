---
title: "Phase 01: Import Logs Migration + Module Permission"
description: "Create the import_logs table, add data_import module to MODULE_PERMISSIONS and role_permissions, all via a single Alembic migration."
skill: postgres-expert
status: pending
group: "foundation"
dependencies: []
tags: [phase, implementation, migration, alembic, postgres, rbac]
created: 2026-05-19
updated: 2026-05-19
---

# Phase 01: Import Logs Migration + Module Permission

**Context:** [[plan|Master Plan]] | **Dependencies:** None | **Status:** Pending

---

## Overview

Lay the database foundation: a new `import_logs` table that records every import attempt with timing, date range, stats JSONB, user, status, and session state — plus a new `data_import` module permission seeded into `role_permissions` for superuser and admin.

**Goal:** After this phase, the DB has `import_logs`, the `data_import` module exists in both static fallback (`MODULE_PERMISSIONS`) and dynamic source of truth (`role_permissions`), and no application code yet depends on either.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** No UI changes. The sidebar link is added in Phase 09 once `user_permissions.data_import` is wired through.
- **Server Layer:** `config/auth_config.py` gets `'data_import': ['superuser', 'admin']` in the `MODULE_PERMISSIONS` dict — this is the fallback that kicks in if the `role_permissions` table is unavailable.
- **Database Layer:**
  - New table: `import_logs` (one row per import attempt)
  - New rows in `role_permissions` for the `data_import` module across all existing roles
- **Integrations:** None.

### User Workflow

This phase has no user-facing surface; downstream phases consume it. The validation workflow is:

**Trigger:** Developer runs `alembic upgrade head`

**Steps:**
1. Migration runs `op.create_table('import_logs', ...)`
2. Migration runs `op.execute(INSERT INTO role_permissions ...)` with `ON CONFLICT DO NOTHING`
3. Developer verifies the table exists: `\d import_logs` in psql
4. Developer verifies the seed: `SELECT * FROM role_permissions WHERE module_name = 'data_import'`
5. Developer runs `alembic downgrade -1` to verify down path works
6. Developer runs `alembic upgrade head` again

**Success Outcome:** The table exists, all 5 roles have a `data_import` row in `role_permissions`, only `superuser` and `admin` have `has_access=TRUE`, and the down migration cleanly removes both.

### Problem Being Solved

**Pain Point:** Without `import_logs`, there's no audit trail — admins can't see "did anyone import last week?" Without `data_import` in `role_permissions`, the existing dynamic permission lookup `RoleRepository().role_has_module_access(role, 'data_import')` returns `False` for everyone, blocking all downstream routes.

**Alternative Approach:** Hard-code role checks in every route — rejected because the codebase has a dynamic RBAC pattern (Phase b0c1d2e3f4a5 set the precedent for `data_correction`).

### Integration Points

**Upstream Dependencies:** None — this is the bottom of the stack.

**Downstream Consumers:**
- Phase 02 builds the repository on top of this table
- Phase 04 inserts `import_logs` rows during the pipeline
- Phase 07/08 routes check `module_permission_required('data_import')`
- Phase 09 renders the sidebar link based on `user_permissions.data_import`

**Data Flow:**

```
Alembic migration ──► import_logs table
                  └─► role_permissions (5 rows: 1 per role)

config/auth_config.py:
  MODULE_PERMISSIONS['data_import'] = ['superuser', 'admin']  (static fallback)

role_permissions table:
  superuser    | data_import | has_access=TRUE
  admin        | data_import | has_access=TRUE
  accountant   | data_import | has_access=FALSE
  receptionist | data_import | has_access=FALSE
  stylist      | data_import | has_access=FALSE
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Revision chain naming:** The most recent alembic revision is `t5u6v7w8x9y0`. Should the new revision follow the existing alphabetic-suffix pattern (`u6v7w8x9y0z1` or similar) or use a short generated hash like `f1a2b3c4d5e6`?
   - **Context:** The codebase mixes both styles; recent migrations use the alphabetic pattern.
   - **Assumptions if unanswered:** Use `u6v7w8x9y0z1_create_import_logs.py` to continue the alphabetic chain.
   - **Impact:** Wrong naming makes future migrations harder to read but doesn't break anything functionally.

2. **role_permissions columns:** Does the `role_permissions` table already have `read_only` and `own_data` columns (per migration `p0q1r2s3t4u5_add_read_only_own_data_to_role_permissions.py`)? The seed insert must include them.
   - **Context:** Phase `b0c1d2e3f4a5` predates those columns and only inserts `(role_id, module_name, has_access)`.
   - **Assumptions if unanswered:** Insert only `(role_id, module_name, has_access)` and rely on column defaults (FALSE) for `read_only` and `own_data`. If defaults don't exist, the migration will be amended to include them.
   - **Impact:** If the columns are NOT NULL without defaults, the insert fails. Verify before running.

3. **session_status enum vs varchar:** `session_status` has 3 values (`active`, `expired`, `missing`). Use a CHECK constraint or PostgreSQL ENUM type?
   - **Context:** The codebase uses CHECK constraints exclusively (see `appointment_status`, `absence_status`).
   - **Assumptions if unanswered:** Use `VARCHAR(20)` + CHECK constraint to match the project pattern.
   - **Impact:** ENUM would be marginally more efficient but breaks the pattern; CHECK is the right call.

4. **stats JSONB default:** Should `stats` default to `'{}'::jsonb` or be nullable?
   - **Context:** Phase 04 writes stats progressively as the import runs. An empty `{}` default makes the row readable mid-import.
   - **Assumptions if unanswered:** `NOT NULL DEFAULT '{}'::jsonb`.
   - **Impact:** Nullable would require null-checks in the history endpoint; default `{}` simplifies UI logic.

### Validation Checklist

- [ ] Revision name confirmed
- [ ] `role_permissions` schema verified (columns + defaults)
- [ ] DEPLOYMENT_VULTR.md and DEPLOYMENT_WINDOWS_SERVER.md note migration step
- [ ] `pytest tests/` baseline passes before changes

> [!CAUTION]
> Verify the `role_permissions` schema on a fresh database before merging. Missing `read_only` / `own_data` defaults will silently break the seed insert on production.

---

## Requirements

### Functional

- Create `import_logs` table with exactly these columns:
  - `id SERIAL PRIMARY KEY`
  - `started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `finished_at TIMESTAMPTZ NULL`
  - `date_range_start DATE NOT NULL`
  - `date_range_end DATE NOT NULL`
  - `triggered_by_user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL`
  - `status VARCHAR(20) NOT NULL DEFAULT 'running'` — CHECK `IN ('running','completed','failed','cancelled')`
  - `stats JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `error_message TEXT NULL`
  - `session_status VARCHAR(20) NULL` — CHECK `IN ('active','expired','missing')` (nullable so we only set it when we know)
  - `dry_run BOOLEAN NOT NULL DEFAULT FALSE`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- Add index on `started_at DESC` (history list ordering)
- Add index on `status` (queries for orphan cleanup)
- Seed `role_permissions` with one row per existing role for module `data_import` — only `superuser` and `admin` get `has_access=TRUE`
- Down migration cleanly removes both

### Technical

- Migration follows the format in `alembic/versions/n8o9p0q1r2s3_create_absence_management_tables.py` (use `op.create_table`, `sa.Column`, `op.create_index`, `op.execute` for seed)
- Use `op.execute` with literal SQL for the role_permissions seed (matches `b0c1d2e3f4a5_add_data_correction_module.py`)
- Use `ON CONFLICT (role_id, module_name) DO NOTHING` so re-runs are idempotent
- Update `config/auth_config.py` `MODULE_PERMISSIONS` dict in the same PR (this is the static fallback — not in the migration itself)

---

## Decision Log

### Use VARCHAR + CHECK Instead of PostgreSQL ENUM (ADR-01-01)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** `status` and `session_status` are bounded enumerations. PostgreSQL has native ENUM types, but adding a value later requires `ALTER TYPE ... ADD VALUE`, which is not transactional in older Postgres versions and is awkward in Alembic.

**Decision:** Use `VARCHAR(20)` + CHECK constraint, matching the existing project pattern (`appointment_status`, `absence_status`).

**Consequences:**
- **Positive:** Adding a new status is a one-line CHECK constraint change; no ENUM dance.
- **Negative:** Marginally less type-safe at the DB layer.
- **Neutral:** Matches every other status column in the codebase.

**Alternatives Considered:**
1. PostgreSQL ENUM type: rejected — breaks project pattern, harder to evolve.
2. Plain `TEXT`: rejected — no validation.

### Index Only on started_at + status (ADR-01-02)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** The history endpoint queries `ORDER BY started_at DESC LIMIT 20`. The startup cleanup queries `WHERE status = 'running'`.

**Decision:** Two single-column indexes. No composite index needed.

**Consequences:**
- **Positive:** Covers both hot queries cheaply.
- **Negative:** None — table will stay small (< 10K rows in 10 years at expected usage).

---

## Implementation Steps

### Step 0: Test Definition (TDD)

#### 0.1: Migration smoke tests

Create `tests/repositories/data_import/__init__.py` and `tests/repositories/data_import/test_import_logs_schema.py`:

- [ ] `test_import_logs_table_exists`: `cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='import_logs'")` returns a row
- [ ] `test_import_logs_columns`: query `information_schema.columns` for `import_logs`, assert every required column exists with correct type
- [ ] `test_import_logs_status_check`: try inserting a row with `status='garbage'`, assert it raises `psycopg2.errors.CheckViolation`
- [ ] `test_session_status_check`: same idea for `session_status`
- [ ] `test_role_permissions_seeded`: query `role_permissions WHERE module_name='data_import'`, assert 5 rows, assert `superuser` and `admin` have `has_access=TRUE`, others FALSE

These tests require a real Postgres connection — mark them `@pytest.mark.integration` and skip in unit mode. The mock_db fixture won't work here.

```python
import pytest
import psycopg2
from psycopg2.errors import CheckViolation


@pytest.mark.integration
class TestImportLogsSchema:
    """Verifies the import_logs table and role_permissions seed."""

    def test_import_logs_table_exists(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'import_logs'
        """)
        assert cur.fetchone() is not None

    def test_status_check_constraint(self, db_conn):
        cur = db_conn.cursor()
        with pytest.raises(CheckViolation):
            cur.execute("""
                INSERT INTO import_logs (date_range_start, date_range_end, status)
                VALUES (%s, %s, %s)
            """, ('2026-01-01', '2026-01-31', 'garbage'))
        db_conn.rollback()

    def test_role_permissions_seeded(self, db_conn):
        cur = db_conn.cursor()
        cur.execute("""
            SELECT r.name, rp.has_access
            FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE rp.module_name = 'data_import'
            ORDER BY r.name
        """)
        rows = cur.fetchall()
        by_role = {r['name']: r['has_access'] for r in rows}
        assert by_role.get('superuser') is True
        assert by_role.get('admin') is True
        assert by_role.get('accountant') is False
        assert by_role.get('receptionist') is False
        assert by_role.get('stylist') is False
```

#### 0.2: Run Tests

- [ ] `pytest tests/repositories/data_import/test_import_logs_schema.py -m integration`
- [ ] All tests fail initially (table doesn't exist yet) — confirms test infra works.

> [!WARNING]
> Schema tests must run against a real DB. If you don't have a local Postgres for integration tests, document the manual SQL verification steps below as the alternative.

---

### Step 1: Write the Alembic Migration

#### 1.1: Create the file

- [ ] Create `alembic/versions/u6v7w8x9y0z1_create_import_logs_and_module_permission.py` (or use the agreed revision id from Q1)
- [ ] Set `down_revision = 't5u6v7w8x9y0'` (current head — verify with `alembic heads`)

#### 1.2: Implement `upgrade()`

```python
"""Create import_logs table + seed data_import module permission

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-05-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'u6v7w8x9y0z1'
down_revision: Union[str, None] = 't5u6v7w8x9y0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── import_logs ───────────────────────────────────────────────────────────
    op.create_table(
        'import_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('date_range_start', sa.Date(), nullable=False),
        sa.Column('date_range_end', sa.Date(), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('stats', sa.dialects.postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('session_status', sa.String(20), nullable=True),
        sa.Column('dry_run', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'],
                                ondelete='SET NULL'),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name='check_import_logs_status'),
        sa.CheckConstraint(
            "session_status IS NULL OR session_status IN ('active', 'expired', 'missing')",
            name='check_import_logs_session_status'),
        sa.CheckConstraint(
            'date_range_end >= date_range_start',
            name='check_import_logs_date_order'),
    )
    op.create_index('idx_import_logs_started_at', 'import_logs',
                    [sa.text('started_at DESC')])
    op.create_index('idx_import_logs_status', 'import_logs', ['status'])

    # ── seed data_import module permission for all roles ──────────────────────
    op.execute("""
        INSERT INTO role_permissions (role_id, module_name, has_access)
        SELECT r.id, 'data_import', (r.name IN ('superuser', 'admin'))
        FROM roles r
        ON CONFLICT (role_id, module_name) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_name = 'data_import';")
    op.drop_index('idx_import_logs_status', table_name='import_logs')
    op.drop_index('idx_import_logs_started_at', table_name='import_logs')
    op.drop_table('import_logs')
```

- [ ] Match the SQLAlchemy + raw SQL split from `n8o9p0q1r2s3_create_absence_management_tables.py`
- [ ] Use `sa.dialects.postgresql.JSONB()` for the `stats` column (not generic JSON)
- [ ] Use `sa.text('started_at DESC')` for the descending index — `op.create_index` doesn't take a string column name with `DESC`
- [ ] Foreign key `triggered_by_user_id → users.id` with `ON DELETE SET NULL` (don't lose import history if user is deleted)

#### 1.3: Implement `downgrade()`

- [ ] Reverse order: delete seeded role_permissions rows, drop indexes, drop table
- [ ] Use the same `ON CONFLICT` pattern is not needed for DELETE — just `WHERE module_name = 'data_import'`

---

### Step 2: Update Static Fallback in auth_config.py

#### 2.1: Add the dict entry

- [ ] Open `config/auth_config.py`
- [ ] Add `'data_import': ['superuser', 'admin'],` to `MODULE_PERMISSIONS` (insert near `'data_correction'`)

```python
MODULE_PERMISSIONS = {
    'invoices': ['superuser', 'admin', 'accountant'],
    'appointments': ['superuser', 'admin', 'receptionist', 'stylist'],
    'clients': ['superuser', 'admin', 'receptionist', 'stylist'],
    'employees': ['superuser', 'admin'],
    'services': ['superuser', 'admin'],
    'settings': ['superuser', 'admin'],
    'reports': ['superuser', 'admin', 'accountant'],
    'data_correction': ['superuser'],
    'data_import': ['superuser', 'admin'],       # ← new
    'absences': ['superuser', 'admin'],
}
```

#### 2.2: Verify no other config file lists modules

- [ ] Grep `MODULE_PERMISSIONS` across the codebase — only `config/auth_config.py` should define it
- [ ] Grep `'data_correction'` — these spots may need a sibling `'data_import'` reference (none expected outside this file based on grep, but verify)

---

### Step 3: Run the Migration + Tests

#### 3.1: Up + down round-trip

- [ ] `alembic upgrade head` — applies the migration
- [ ] `\d import_logs` in psql — verify the schema
- [ ] `SELECT * FROM role_permissions WHERE module_name = 'data_import'` — verify 5 rows
- [ ] `alembic downgrade -1` — rolls back
- [ ] `\dt import_logs` returns "no relations found" — verify drop
- [ ] `alembic upgrade head` — final state

#### 3.2: Run the integration tests

- [ ] `pytest tests/repositories/data_import/test_import_logs_schema.py -m integration` — all pass

#### 3.3: Run the full unit test suite

- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `\d import_logs` shows all 12 columns with correct types, defaults, and constraints
- [ ] `SELECT count(*) FROM role_permissions WHERE module_name='data_import'` returns 5
- [ ] `SELECT name FROM roles JOIN role_permissions rp ON rp.role_id = roles.id WHERE rp.module_name='data_import' AND rp.has_access = TRUE` returns exactly `superuser` and `admin`
- [ ] `MODULE_PERMISSIONS['data_import']` in `config/auth_config.py` equals `['superuser', 'admin']`
- [ ] `alembic downgrade -1` then `alembic upgrade head` is a clean round-trip

**Quality Gates:**

- [ ] No `pytest` failures in the full suite
- [ ] CHECK constraints reject invalid `status` and `session_status` values (integration test confirms)
- [ ] `date_range_end >= date_range_start` constraint rejects inverted ranges

**Integration:**

- [ ] Phase 02 repository can `INSERT INTO import_logs (date_range_start, date_range_end, dry_run, triggered_by_user_id) VALUES (...)` and get back an id (verified manually after Phase 02 lands)

---

## Quality Assurance

### Test Plan

#### Manual Testing

- [ ] **Migration up:** Run `alembic upgrade head` on a fresh dev DB.
  - Expected: Migration completes without error; `import_logs` exists.
- [ ] **Seed verification:** Run `SELECT name, has_access FROM roles JOIN role_permissions rp ON rp.role_id = roles.id WHERE rp.module_name='data_import';`
  - Expected: 5 rows, superuser+admin TRUE, others FALSE.
- [ ] **Down + up cycle:** `alembic downgrade -1` then `alembic upgrade head`.
  - Expected: Both succeed; no orphaned `role_permissions` rows after downgrade.
- [ ] **CHECK constraint:** Manually `INSERT INTO import_logs (date_range_start, date_range_end, status) VALUES ('2026-01-01', '2026-01-31', 'wat');`
  - Expected: `ERROR: new row for relation "import_logs" violates check constraint "check_import_logs_status"`.

#### Automated Testing

```bash
# Activate venv first
pytest tests/repositories/data_import/test_import_logs_schema.py -v -m integration
pytest tests/                                                  # full suite no regression
```

### Review Checklist

- [ ] **Code Review Gate:**
  - [ ] Run `/code-review plans/260519-data-import-playwright/phase-01-import-logs-migration.md` with files: `alembic/versions/u6v7w8x9y0z1_*.py`, `config/auth_config.py`, `tests/repositories/data_import/test_import_logs_schema.py`
  - [ ] Read review at `plans/260519-data-import-playwright/reviews/code/phase-01.md`
  - [ ] Critical findings addressed (0 remaining)
  - [ ] Phase approved for completion

- [ ] **Code Quality:**
  - [ ] `pytest tests/` all pass
  - [ ] No `print()` statements added

- [ ] **Security:**
  - [ ] No hardcoded credentials
  - [ ] No `USING(true)` or skipped CHECK constraints
  - [ ] Foreign key cascade chosen deliberately (`ON DELETE SET NULL` for user reference)

- [ ] **Documentation:**
  - [ ] Migration docstring explains purpose
  - [ ] `MEMORY.md` updated to add `data_import` to the module permission table

- [ ] **Project Pattern Compliance:**
  - [ ] Migration shape matches `n8o9p0q1r2s3_create_absence_management_tables.py`
  - [ ] Seed pattern matches `b0c1d2e3f4a5_add_data_correction_module.py`
  - [ ] Index naming follows `idx_<table>_<column>` convention

---

## Dependencies

### Upstream (Required Before Starting)

- Working alembic configuration (verified by `alembic current` returning the latest revision)
- `users`, `roles`, `role_permissions` tables already exist (they do — verified)

### Downstream (Will Use This Phase)

- **Phase 02 (Import Log Repository):** CRUD against `import_logs`
- **Phase 04 (Import Service Core):** INSERT a row at start, UPDATE on progress/finish
- **Phase 07/08 (Routes):** `@module_permission_required('data_import')` decorator now functional

### External Services

- None.

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Code review passed (see Review Checklist above)
- [ ] Migration tested up + down + up
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 01 — import_logs table + data_import module permission`

---

## Notes

### Technical Considerations

- `JSONB` is preferred over `JSON` for the `stats` column — supports GIN indexing if we ever need to query by stat values
- The `started_at DESC` index is the only one used by the history endpoint's `ORDER BY` — Postgres can scan it backwards anyway, but the explicit descending index removes ambiguity for future query planners
- `triggered_by_user_id` is NULLABLE so a future CLI invocation (script running via cron) can record imports without a user

### Known Limitations

- Old import attempts before this migration won't appear in history — by design.
- A server restart mid-import leaves the row with `status='running'` forever; Phase 02 includes a startup cleanup that flips orphaned rows to `failed` with `error_message='Server restarted mid-import'`.

### Future Enhancements

- Add a `duration_seconds` generated column (`finished_at - started_at`) for faster history rendering
- Add a `xlsx_filename` column if we ever want to keep the source file path for audit (currently we delete it after import)

---

**Previous:** [[plan|Master Plan]]
**Next:** [[phase-02-import-log-repository|Phase 02: Import Log Repository]]
