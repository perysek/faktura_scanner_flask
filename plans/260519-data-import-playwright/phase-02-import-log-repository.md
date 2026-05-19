---
title: "Phase 02: Import Log Repository"
description: "Build the PostgreSQL repository for import_logs with CRUD, status transitions, history fetch, and orphan cleanup."
skill: service-builder
status: pending
group: "foundation"
dependencies: [phase-01-import-logs-migration]
tags: [phase, implementation, repository, postgres, psycopg2]
created: 2026-05-19
updated: 2026-05-19
---

# Phase 02: Import Log Repository

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 01 | **Status:** Pending

---

## Overview

Build `repositories/data_import/import_log_repository.py` — a `BaseRepository` subclass that handles every interaction with the `import_logs` table: create, update progress/status, fetch a single row, list the last N for the history endpoint, and cleanup orphan rows left in `running` state by a previous crash.

**Goal:** Every other phase that touches `import_logs` calls this repository — no ad-hoc SQL elsewhere.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** None.
- **Server Layer:** A new repository module accessible to the import service (Phase 04), background runner (Phase 05), and history endpoint (Phase 08).
- **Database Layer:** Reads + writes `import_logs` rows. Joins to `users.full_name` for the history payload.
- **Integrations:** None.

### User Workflow

No direct user surface. Internal flow:

**Trigger:** Phase 04 service calls `ImportLogRepository().create(...)` at the start of an import.

**Steps:**
1. `create(date_start, date_end, dry_run, triggered_by_user_id)` → returns new `import_id`, status='running'
2. `update_stats(import_id, stats_dict)` called periodically during the run
3. `update_session_status(import_id, 'active'|'expired'|'missing')` called after Playwright sign-in check
4. `mark_completed(import_id, stats_dict)` on success
5. `mark_failed(import_id, error_message, stats_dict)` on failure
6. `mark_cancelled(import_id)` if admin clicks cancel (out of scope for now but reserve the method)

**Success Outcome:** Every state of the import is reflected in the row, queryable by `get_by_id` for the SSE/status endpoint and `get_recent(limit=20)` for the history table.

### Problem Being Solved

**Pain Point:** Without a repository, the service layer would scatter `INSERT INTO import_logs`, `UPDATE import_logs SET stats = stats || ...`, and `SELECT ... FROM import_logs JOIN users ...` calls across multiple files — exactly the anti-pattern the project's architecture forbids.

**Alternative Approach:** Inline SQL in `data_import_service.py` — rejected because every other domain in the codebase has a repository (`AppointmentRepository`, `SmsReminderRepository`, etc.).

### Integration Points

**Upstream Dependencies:**
- Phase 01 — `import_logs` table + `users` FK

**Downstream Consumers:**
- Phase 04 — calls `create`, `update_stats`, `mark_completed`, `mark_failed`
- Phase 05 — calls `mark_failed` from the orphan-cleanup hook
- Phase 06 — calls `get_by_id` for status polling
- Phase 08 — calls `get_recent` for the history endpoint

**Data Flow:**

```
service / route ──► ImportLogRepository ──► import_logs
                                       └──► users (LEFT JOIN for history)
```

---

## Prerequisites & Clarifications

### Questions for User

1. **stats merge strategy:** When `update_stats` is called mid-run, should it replace the entire `stats` JSONB or merge with `||`?
   - **Context:** PostgreSQL `jsonb || jsonb` does shallow merge. The service writes the full counter dict every time, so replace is simpler.
   - **Assumptions if unanswered:** Replace entirely on each call (the service maintains the counter dict in memory).
   - **Impact:** Wrong choice produces wrong stats; replace is the safer default.

2. **Orphan cleanup trigger:** Should `cleanup_orphans()` run on app startup (from `app.py`) or be exposed only as a method called explicitly?
   - **Context:** The codebase auto-runs `cleanup_stale_uploads` on startup (`app.py:264`).
   - **Assumptions if unanswered:** Provide the method, call it from `app.py` startup hook in this phase.
   - **Impact:** Without startup cleanup, orphaned `running` rows would block the "import already running?" check in Phase 05.

3. **Soft delete:** Should `import_logs` support soft delete?
   - **Context:** `BaseRepository._soft_delete` flag enables it. But these are audit records — we never want to hide them.
   - **Assumptions if unanswered:** No soft delete (`_soft_delete = False`); records are immutable history.
   - **Impact:** None — we just don't expose a delete method on this repository.

4. **Concurrent imports:** Should `has_running_import()` check be in this repository (DB-level) or in the runner (memory-level thread registry)?
   - **Context:** Phase 05 builds a memory registry. But if multiple processes ever run (gunicorn workers), only DB-level check is reliable.
   - **Assumptions if unanswered:** Add `find_running()` here returning `Optional[row]` — Phase 05 uses it as the source of truth.
   - **Impact:** Wrong choice allows duplicate concurrent imports under multi-worker deployments.

### Validation Checklist

- [ ] Phase 01 is merged and `import_logs` exists in dev DB
- [ ] `BaseRepository` API reviewed — confirm `_execute_insert` returns the new id correctly
- [ ] Test fixture `mock_db` (from `tests/conftest.py`) covers the use cases needed

> [!CAUTION]
> Phase 04 will write to this repository in a background thread. Confirm that `DatabaseConnection.get_connection()` (which uses Flask's `g`) is acceptable in a thread context — see Phase 05 for the resolution. If not, this phase must accept a `conn` parameter explicitly.

---

## Requirements

### Functional

- `create(date_start, date_end, dry_run, triggered_by_user_id) -> int` — inserts a `status='running'`, `stats='{}'`, returns new id
- `get_by_id(import_id: int) -> Optional[dict]` — single row, including `triggered_by_user_id` (the route joins user info separately for the history endpoint)
- `update_stats(import_id: int, stats: dict) -> None` — replaces the stats JSONB
- `update_session_status(import_id: int, session_status: str) -> None` — sets the session_status column to 'active' | 'expired' | 'missing'
- `mark_completed(import_id: int, stats: dict) -> None` — sets `status='completed'`, `finished_at=NOW()`, `stats=...`
- `mark_failed(import_id: int, error_message: str, stats: Optional[dict] = None) -> None` — sets `status='failed'`, `finished_at=NOW()`, `error_message=...`
- `mark_cancelled(import_id: int) -> None` — sets `status='cancelled'`, `finished_at=NOW()`
- `find_running() -> Optional[dict]` — returns the row that's currently `status='running'`, or None
- `get_recent(limit: int = 20) -> List[dict]` — returns the last N rows with `triggered_by_user_name` (JOIN against `users`) for the history table
- `cleanup_orphans() -> int` — UPDATEs all `status='running'` rows to `status='failed'` with `error_message='Server restarted mid-import'`; returns the count

### Technical

- Inherit `BaseRepository`, set `table_name='import_logs'`, `_soft_delete = False`
- Override `_columns` to list explicit columns (no `SELECT *` — matches project convention)
- Use `safe_commit(conn)` not raw `conn.commit()` so the repo plays nice with `managed_transaction`
- Background-thread usage: ALL methods accept an optional `conn` parameter (default `None` → uses `DatabaseConnection.get_connection()`). When called from a thread, the runner passes a thread-local connection obtained from the pool directly. See Phase 05 for the connection-management pattern.

---

## Decision Log

### Replace JSONB stats, Not Merge (ADR-02-01)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** The service maintains a counter dict (`{inserted: 5, skipped_zero: 2, ...}`) in memory and writes it after each batch of rows. Two options: shallow-merge with `stats || %s::jsonb`, or replace with `stats = %s::jsonb`.

**Decision:** Replace.

**Consequences:**
- **Positive:** Simpler SQL, no risk of stale keys from a previous write lingering.
- **Negative:** None — the service always has the full counter dict.

### Optional `conn` Parameter on Every Method (ADR-02-02)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** The background thread doesn't have a Flask request context, so `DatabaseConnection.get_connection()` (which reads `g.db`) won't work directly. We could push a Flask app context inside the thread (`with app.app_context():`), or take a `conn` parameter explicitly.

**Decision:** Take optional `conn`. If None, fall back to `_get_conn()` (the BaseRepository helper). When called from threads, Phase 05 passes a pool-acquired connection.

**Consequences:**
- **Positive:** Repository is reusable from both request and thread contexts.
- **Negative:** Adds a parameter to every method.
- **Neutral:** Matches the pattern from `repositories/db_utils.py` helpers in the codebase.

---

## Implementation Steps

### Step 0: Test Definition (TDD)

#### 0.1: Repository unit tests

Create `tests/repositories/data_import/test_import_log_repository.py`:

```python
"""
Tests for ImportLogRepository — verifies CRUD + status transitions + orphan cleanup.
Uses the mock_db fixture from tests/conftest.py.
"""
import pytest
from datetime import date


class TestImportLogRepository:

    def test_create_inserts_running_row(self, mock_db):
        mock_db.cursor.fetchone.return_value = {'id': 42}
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()

        new_id = repo.create(
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            dry_run=False,
            triggered_by_user_id=7,
        )

        assert new_id == 42
        sql = mock_db.cursor.execute.call_args[0][0]
        params = mock_db.cursor.execute.call_args[0][1]
        assert 'INSERT INTO import_logs' in sql
        assert '%s' in sql            # uses parameter binding
        assert '?' not in sql         # NOT sqlite syntax
        # status defaults to 'running' via DB default — not in params
        assert 7 in params

    def test_update_stats_replaces_jsonb(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.update_stats(42, {'inserted': 10, 'skipped': 2})
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE import_logs' in sql
        assert 'SET stats = %s' in sql

    def test_mark_completed_sets_finished_at(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.mark_completed(42, {'inserted': 50})
        sql = mock_db.cursor.execute.call_args[0][0]
        assert "status = 'completed'" in sql or "status = %s" in sql
        assert 'finished_at' in sql

    def test_mark_failed_records_error(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.mark_failed(42, 'Playwright timeout', stats={'errors': 1})
        sql = mock_db.cursor.execute.call_args[0][0]
        params = mock_db.cursor.execute.call_args[0][1]
        assert 'Playwright timeout' in params
        assert 'error_message' in sql

    def test_find_running_returns_row_or_none(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()

        mock_db.cursor.fetchone.return_value = {'id': 99, 'status': 'running'}
        assert repo.find_running() == {'id': 99, 'status': 'running'}

        mock_db.cursor.fetchone.return_value = None
        assert repo.find_running() is None

    def test_get_recent_joins_users(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.get_recent(limit=20)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'LEFT JOIN users' in sql
        assert 'ORDER BY started_at DESC' in sql
        assert 'LIMIT %s' in sql

    def test_cleanup_orphans_returns_count(self, mock_db):
        mock_db.cursor.rowcount = 3
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        count = repo.cleanup_orphans()
        assert count == 3
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE import_logs' in sql
        assert "status = 'failed'" in sql or "status = %s" in sql
        assert "WHERE status = 'running'" in sql or "WHERE status = %s" in sql
```

#### 0.2: Run Tests

- [ ] `pytest tests/repositories/data_import/test_import_log_repository.py -v`
- [ ] All tests fail (module doesn't exist yet)

> [!WARNING]
> Use the `mock_db` fixture pattern — don't reach for real DB integration tests here. The schema integration tests live in Phase 01.

---

### Step 1: Create the Repository Module

#### 1.1: Folder + `__init__.py`

- [ ] `mkdir repositories/data_import/`
- [ ] Create `repositories/data_import/__init__.py` (empty)

#### 1.2: Write `import_log_repository.py`

```python
"""
Repository for import_logs — audit trail for the caldis.pl Playwright import feature.

Every import attempt (running, completed, failed, cancelled) has exactly one row.
The data_import_service writes here; the SSE / status / history endpoints read.

Background-thread safe: every method accepts an optional `conn` parameter so
the runner can pass a pool-acquired connection from outside the Flask request
context. When `conn=None`, falls back to DatabaseConnection.get_connection().
"""
import json
import logging
from datetime import date
from typing import Any, List, Optional

import psycopg2.extensions

from config.database import DatabaseConnection, safe_commit
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ImportLogRepository(BaseRepository):
    """CRUD + status transitions for import_logs."""

    _columns = (
        'id, started_at, finished_at, date_range_start, date_range_end, '
        'triggered_by_user_id, status, stats, error_message, session_status, '
        'dry_run, created_at'
    )

    def __init__(self):
        super().__init__('import_logs')

    # ── connection helper ────────────────────────────────────────────────────
    def _conn(self, conn: Optional[psycopg2.extensions.connection]):
        """Return the supplied connection, or fall back to the request-scoped one."""
        return conn if conn is not None else DatabaseConnection.get_connection()

    # ── create ───────────────────────────────────────────────────────────────
    def create(self, date_start: date, date_end: date,
               dry_run: bool, triggered_by_user_id: Optional[int],
               conn: Optional[psycopg2.extensions.connection] = None) -> int:
        """Insert a new running row, return its id."""
        query = """
            INSERT INTO import_logs
                (date_range_start, date_range_end, dry_run, triggered_by_user_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (
            date_start.isoformat(),
            date_end.isoformat(),
            dry_run,
            triggered_by_user_id,
        ))
        new_id = cursor.fetchone()['id']
        safe_commit(conn)
        return new_id

    # ── reads ────────────────────────────────────────────────────────────────
    def get_by_id(self, import_id: int,
                  conn: Optional[psycopg2.extensions.connection] = None) -> Optional[dict]:
        query = f"SELECT {self._columns} FROM import_logs WHERE id = %s"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (import_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_running(self,
                     conn: Optional[psycopg2.extensions.connection] = None) -> Optional[dict]:
        """Return the single currently-running import, or None."""
        query = f"""
            SELECT {self._columns}
            FROM import_logs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_recent(self, limit: int = 20,
                   conn: Optional[psycopg2.extensions.connection] = None) -> List[dict]:
        """Return the last N imports with triggered_by_user_name for the history table."""
        query = """
            SELECT
                il.id, il.started_at, il.finished_at,
                il.date_range_start, il.date_range_end,
                il.status, il.stats, il.error_message,
                il.session_status, il.dry_run,
                il.triggered_by_user_id,
                u.full_name AS triggered_by_user_name
            FROM import_logs il
            LEFT JOIN users u ON u.id = il.triggered_by_user_id
            ORDER BY il.started_at DESC
            LIMIT %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        return [dict(r) for r in cursor.fetchall()]

    # ── updates ──────────────────────────────────────────────────────────────
    def update_stats(self, import_id: int, stats: dict,
                     conn: Optional[psycopg2.extensions.connection] = None) -> None:
        query = "UPDATE import_logs SET stats = %s::jsonb WHERE id = %s"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (json.dumps(stats), import_id))
        safe_commit(conn)

    def update_session_status(self, import_id: int, session_status: str,
                              conn: Optional[psycopg2.extensions.connection] = None) -> None:
        if session_status not in ('active', 'expired', 'missing'):
            raise ValueError(f"Invalid session_status: {session_status}")
        query = "UPDATE import_logs SET session_status = %s WHERE id = %s"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (session_status, import_id))
        safe_commit(conn)

    def mark_completed(self, import_id: int, stats: dict,
                       conn: Optional[psycopg2.extensions.connection] = None) -> None:
        query = """
            UPDATE import_logs
            SET status = 'completed', finished_at = NOW(), stats = %s::jsonb
            WHERE id = %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (json.dumps(stats), import_id))
        safe_commit(conn)

    def mark_failed(self, import_id: int, error_message: str,
                    stats: Optional[dict] = None,
                    conn: Optional[psycopg2.extensions.connection] = None) -> None:
        if stats is not None:
            query = """
                UPDATE import_logs
                SET status = 'failed', finished_at = NOW(),
                    error_message = %s, stats = %s::jsonb
                WHERE id = %s
            """
            params = (error_message, json.dumps(stats), import_id)
        else:
            query = """
                UPDATE import_logs
                SET status = 'failed', finished_at = NOW(),
                    error_message = %s
                WHERE id = %s
            """
            params = (error_message, import_id)
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, params)
        safe_commit(conn)

    def mark_cancelled(self, import_id: int,
                       conn: Optional[psycopg2.extensions.connection] = None) -> None:
        query = """
            UPDATE import_logs
            SET status = 'cancelled', finished_at = NOW()
            WHERE id = %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (import_id,))
        safe_commit(conn)

    # ── orphan cleanup ───────────────────────────────────────────────────────
    def cleanup_orphans(self,
                        conn: Optional[psycopg2.extensions.connection] = None) -> int:
        """Flip orphaned 'running' rows (from a previous crash) to 'failed'.

        Returns the number of rows updated.
        """
        query = """
            UPDATE import_logs
            SET status = 'failed', finished_at = NOW(),
                error_message = 'Server restarted mid-import'
            WHERE status = 'running'
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query)
        count = cursor.rowcount
        safe_commit(conn)
        if count > 0:
            logger.warning(f"cleanup_orphans: flipped {count} stale 'running' rows to 'failed'")
        return count
```

- [ ] Module path: `repositories/data_import/import_log_repository.py`
- [ ] Match the docstring + import order from `repositories/sms/sms_repository.py`
- [ ] Use `json.dumps()` for the JSONB parameter — psycopg2 doesn't auto-serialize dicts to JSONB

---

### Step 2: Wire Orphan Cleanup into App Startup

#### 2.1: Add hook in `app.py`

- [ ] Edit `app.py`. Near the existing `cleanup_stale_uploads(app)` call (around line 264):

```python
# Cleanup orphaned import_logs rows from previous crash
from repositories.data_import.import_log_repository import ImportLogRepository
try:
    with app.app_context():
        count = ImportLogRepository().cleanup_orphans()
        if count:
            logging.info(f"Flipped {count} orphaned import_logs rows to 'failed'")
except Exception as e:
    logging.warning(f"Could not run import_logs orphan cleanup at startup: {e}")
```

- [ ] Wrap in try/except so a missing table (e.g. before migration runs) doesn't crash the app

---

### Step 3: Verify

#### 3.1: Run the new tests

- [ ] `pytest tests/repositories/data_import/test_import_log_repository.py -v` — all pass

#### 3.2: Manual smoke

- [ ] Start the Flask app
- [ ] In a Python shell: `from repositories.data_import.import_log_repository import ImportLogRepository; r = ImportLogRepository(); r.create(date(2026,1,1), date(2026,1,31), False, 1)` — returns an int

#### 3.3: Full test suite

- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `repositories/data_import/import_log_repository.py` exists with all 9 methods listed in Functional Requirements
- [ ] Every method uses `%s` placeholders (not `?`)
- [ ] Every method accepts optional `conn` parameter
- [ ] `app.py` calls `cleanup_orphans()` on startup
- [ ] `pytest tests/repositories/data_import/test_import_log_repository.py` passes

**Quality Gates:**

- [ ] No `print()` statements
- [ ] No `sqlite3` imports
- [ ] All SQL queries use `%s` placeholders
- [ ] No `SELECT *` (uses explicit `_columns`)

**Integration:**

- [ ] Phase 04 service can call all repository methods without errors (verified after Phase 04 lands)
- [ ] Phase 08 history endpoint calls `get_recent(20)` and gets a list of dicts including `triggered_by_user_name`

---

## Quality Assurance

### Test Plan

#### Manual Testing

- [ ] **Round-trip:** `repo.create(...)` then `repo.get_by_id(new_id)` returns the same row with `status='running'`.
  - Expected: id matches, status is 'running', stats is `{}`.
- [ ] **Mark completed:** `repo.mark_completed(id, {'inserted': 5})`.
  - Expected: row now has `status='completed'`, `finished_at` is set, stats is `{"inserted": 5}`.
- [ ] **Orphan cleanup:** Insert a row directly with `status='running'`, restart the app.
  - Expected: row is flipped to `status='failed'` with the expected `error_message`.
- [ ] **Find running:** With one running import, `find_running()` returns the row; with no running imports, returns None.

#### Automated Testing

```bash
pytest tests/repositories/data_import/test_import_log_repository.py -v
pytest tests/                                                            # full suite
```

### Review Checklist

- [ ] **Code Review Gate:**
  - [ ] Run `/code-review plans/260519-data-import-playwright/phase-02-import-log-repository.md` with files: `repositories/data_import/import_log_repository.py`, `repositories/data_import/__init__.py`, `app.py`, `tests/repositories/data_import/test_import_log_repository.py`
  - [ ] Read review at `plans/260519-data-import-playwright/reviews/code/phase-02.md`
  - [ ] Critical findings addressed

- [ ] **Code Quality:**
  - [ ] `pytest tests/` all pass
  - [ ] Type hints on every public method

- [ ] **Security:**
  - [ ] No raw user input concatenated into SQL
  - [ ] `error_message` parameter accepts any string but is always parameterized

- [ ] **Documentation:**
  - [ ] Docstrings explain background-thread usage of the `conn` parameter

- [ ] **Project Pattern Compliance:**
  - [ ] Repository file structure matches `repositories/sms/sms_repository.py`
  - [ ] Uses `BaseRepository` + `safe_commit`
  - [ ] Explicit `_columns` (no `SELECT *`)

---

## Dependencies

### Upstream (Required Before Starting)

- **Phase 01** — `import_logs` table exists; `data_import` module permission seeded

### Downstream (Will Use This Phase)

- **Phase 04** — service writes rows during the pipeline
- **Phase 05** — runner uses `find_running()` to prevent concurrent imports
- **Phase 06** — status endpoint reads `get_by_id`
- **Phase 08** — history endpoint reads `get_recent(20)`

### External Services

- None.

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 02 — ImportLogRepository`

---

## Notes

### Technical Considerations

- The repository must work both inside a request (Flask `g.db`) and from a background thread (explicit `conn`). The optional-`conn` pattern is the cleanest way to support both.
- `json.dumps()` is required because `psycopg2` doesn't auto-serialize Python dicts to JSONB — passing a raw dict produces a `TypeError: can't adapt type 'dict'`.

### Known Limitations

- `find_running()` returns only one row even though the DB allows multiple. In practice we never have more than one (Phase 05 enforces it), but if a future bug allows it, the second one would be hidden until the first finishes.
- `cleanup_orphans()` is a blunt instrument — it flips EVERY running row to failed. If a legitimate import is actually running during startup (impossible in single-worker mode), it would be killed. Not a concern given the deployment model.

### Future Enhancements

- Add `get_stats_aggregate(date_from, date_to)` for reporting
- Add `mark_cancelled_by_user(import_id, user_id)` once cancel UI is built

---

**Previous:** [[phase-01-import-logs-migration|Phase 01: Import Logs Migration + Module Permission]]
**Next:** [[phase-03-postgres-lookup-builders|Phase 03: PostgreSQL Lookup Builders + Parser Helpers]]
