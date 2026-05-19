---
title: "Phase 08: Start Import + History Endpoints + Page Route"
description: "Add POST /api/import/start, GET /api/import/history, and GET /import (page) — completing the HTTP layer for the data import feature."
skill: server-action-builder
status: pending
group: "http-layer"
dependencies: [phase-07-session-management, phase-05-background-runner, phase-02-import-log-repository]
tags: [phase, implementation, flask, route, import, history]
created: 2026-05-20
updated: 2026-05-20
---

# Phase 08: Start Import + History Endpoints + Page Route

**Context:** [[plan|Master Plan]] | **Dependencies:** Phases 02, 05, 07 | **Status:** Pending

---

## Overview

Complete the HTTP layer by adding three more endpoints:

1. **`POST /api/import/start`** — validates the date range, prevents concurrent imports, creates an `import_logs` row, starts the background import thread from Phase 05, and immediately returns `{import_id}`.
2. **`GET /api/import/history`** — returns the last 20 `import_logs` rows joined with `users` for the `triggered_by_name` display field.
3. **`GET /import`** — renders `templates/data_import/index.html` (added to `main_bp` in `routes/main_routes.py` so the URL has no `/api` prefix).

After this phase every server-side route is wired. Phase 09 builds the template; Phase 10 wires the JS.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** Phase 09 template + Phase 10 JS consume all three endpoints.
- **Server Layer:**
  - `POST /api/import/start` and `GET /api/import/history` are added to `routes/import_routes.py` (the blueprint from Phase 06).
  - `GET /import` is added to `routes/main_routes.py` (`main_bp`) to avoid the `/api` URL prefix.
- **Database Layer:** Reads from / writes to `import_logs` via `ImportLogRepository` (Phase 02).
- **Background Runner:** Phase 05 `IMPORT_RUNNER.start_import()`.

### User Workflow

**Triggering an import:**

1. Admin selects date range on `/import` page, clicks "Importuj"
2. JS calls `POST /api/import/start` with `{date_start, date_end, dry_run}`
3. Server validates:
   - Dates parse as `YYYY-MM-DD`
   - `date_start <= date_end`
   - No other import currently `running` in `import_logs`
4. Creates `import_logs` row with `status='running'`, returns `{import_id: 42}`
5. Starts background thread via `IMPORT_RUNNER.start_import(import_id, ...)`
6. JS opens `EventSource('/api/import/42/stream')` and watches live progress

**Viewing history:**

1. On page load, JS calls `GET /api/import/history`
2. Returns last 20 import_logs rows, newest first
3. Table renders with status badges and stats

### Integration Points

**Upstream Dependencies:**
- Phase 02 — `ImportLogRepository.create()`, `ImportLogRepository.get_history(limit=20)`
- Phase 05 — `IMPORT_RUNNER.start_import(import_id, date_start, date_end, dry_run)`
- Phase 07 — route file exists; new routes are appended to the same file

**Downstream Consumers:**
- Phase 09 — page template renders via `main.import_page` endpoint
- Phase 10 — JS calls all three endpoints

---

## Prerequisites & Clarifications

### Questions for User

1. **Concurrent import guard:** The plan prevents two imports running simultaneously. Is there ever a reason to allow concurrent imports (e.g. different date ranges in parallel)?
   - **Assumptions if unanswered:** No. One import at a time, globally. The guard queries `import_logs` for any `status='running'` row and returns 409 Conflict if found.
   - **Impact:** Concurrent imports could corrupt the in-memory queue registry; the guard prevents this.

2. **History count:** Last 20 imports shown. Should this be configurable via a query param (`?limit=N`)?
   - **Assumptions if unanswered:** Hard-coded 20. No query param in this phase.

3. **Future date guard:** Should imports for future date ranges be blocked?
   - **Assumptions if unanswered:** Allow `date_end` up to 1 day in the future (to handle same-day imports across timezones). Block anything further.

### Validation Checklist

- [ ] Phase 02 merged — `ImportLogRepository.create()` and `get_history()` exist
- [ ] Phase 05 merged — `IMPORT_RUNNER.start_import()` is callable
- [ ] Phase 07 merged — `routes/import_routes.py` exists
- [ ] `main_bp` import of render_template already in `routes/main_routes.py`
- [ ] `data_import` permission seeded (Phase 01) — `@module_permission_required('data_import')` passes for admin

---

## Requirements

### Functional

**Route: `POST /api/import/start`** (in `routes/import_routes.py`)

- Auth: `@login_required` + `@module_permission_required('data_import')`
- Request JSON: `{date_start: "YYYY-MM-DD", date_end: "YYYY-MM-DD", dry_run: bool}`
- Validation:
  - Both dates present → else `ValidationError('Wymagane: date_start, date_end')`
  - Parse with `datetime.strptime(d, '%Y-%m-%d').date()` → else `ValidationError('Nieprawidlowy format daty')`
  - `date_start <= date_end` → else `ValidationError('date_start musi byc przed date_end')`
  - `date_end <= date.today() + timedelta(days=1)` → else `ValidationError('Data konca nie moze byc w przyszlosci')`
- Concurrent guard: `ImportLogRepository().has_running_import()` → if True: raise `ConflictError('Import jest juz w toku. Poczekaj na zakonczenie.')`
- Create log row: `import_id = ImportLogRepository().create(date_start, date_end, dry_run, user_id=current_user.id)`
- Start thread: `IMPORT_RUNNER.start_import(import_id, date_start, date_end, dry_run)`
- Return: `jsonify({'success': True, 'import_id': import_id})`, HTTP 202

**Route: `GET /api/import/history`** (in `routes/import_routes.py`)

- Auth: `@login_required` + `@module_permission_required('data_import')`
- Calls: `rows = ImportLogRepository().get_history(limit=20)` — returns rows joined with `users.full_name` as `triggered_by_name`
- Serializes datetimes via `.isoformat()`, dates via `.isoformat()`, stats JSONB as-is
- Returns: `jsonify({'success': True, 'history': [...], 'count': N})`

**Route: `GET /import`** (in `routes/main_routes.py`, on `main_bp`)

```python
@main_bp.route('/import')
@login_required
@module_permission_required('data_import')
def import_page():
    return render_template('data_import/index.html')
```

Note the endpoint name is `main.import_page` — Phase 09 uses `url_for('main.import_page')` and the sidebar uses `request.endpoint == 'main.import_page'`.

### Technical

Full implementation of `POST /api/import/start`:

```python
from datetime import datetime, date, timedelta

@import_bp.route('/import/start', methods=['POST'])
@login_required
@module_permission_required('data_import')
def start_import():
    """Start a background import from caldis.pl for the given date range."""
    try:
        data = request.get_json() or {}

        date_start_str = data.get('date_start', '').strip()
        date_end_str   = data.get('date_end', '').strip()
        dry_run        = bool(data.get('dry_run', False))

        if not date_start_str or not date_end_str:
            raise ValidationError('Wymagane: date_start, date_end')

        try:
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date()
            date_end   = datetime.strptime(date_end_str,   '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Nieprawidlowy format daty (oczekiwano YYYY-MM-DD)')

        if date_start > date_end:
            raise ValidationError('date_start musi byc przed lub rowny date_end')

        if date_end > date.today() + timedelta(days=1):
            raise ValidationError('Data konca nie moze byc dalej niz jutro')

        repo = ImportLogRepository()
        if repo.has_running_import():
            raise ConflictError('Import jest juz w toku — poczekaj na zakonczenie.')

        import_id = repo.create(
            date_start=date_start,
            date_end=date_end,
            dry_run=dry_run,
            triggered_by_user_id=current_user.id,
        )
        IMPORT_RUNNER.start_import(import_id, date_start, date_end, dry_run)

        logger.info('Import %d started (range: %s to %s, dry_run=%s)',
                    import_id, date_start, date_end, dry_run)

        return jsonify({'success': True, 'import_id': import_id}), 202

    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in start_import')
        raise AppError('Wystapil blad serwera')
```

Full implementation of `GET /api/import/history`:

```python
@import_bp.route('/import/history', methods=['GET'])
@login_required
@module_permission_required('data_import')
def import_history():
    """Return last 20 import_logs rows with user display names."""
    try:
        rows = ImportLogRepository().get_history(limit=20)

        def _serialize(row):
            def _iso(v):
                return v.isoformat() if v is not None else None
            return {
                'id':                   row['id'],
                'status':               row['status'],
                'stats':                row.get('stats') or {},
                'error_message':        row.get('error_message'),
                'started_at':           _iso(row.get('started_at')),
                'finished_at':          _iso(row.get('finished_at')),
                'date_range_start':     _iso(row.get('date_range_start')),
                'date_range_end':       _iso(row.get('date_range_end')),
                'dry_run':              bool(row.get('dry_run')),
                'triggered_by_user_id': row.get('triggered_by_user_id'),
                'triggered_by_name':    row.get('triggered_by_name'),
                'session_status':       row.get('session_status'),
            }

        history = [_serialize(r) for r in rows]
        return jsonify({'success': True, 'history': history, 'count': len(history)})

    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in import_history')
        raise AppError('Wystapil blad serwera')
```

### `ImportLogRepository` methods required by this phase

Phase 02 must expose:
- `create(date_start, date_end, dry_run, triggered_by_user_id) → int` — inserts row, returns `id`
- `has_running_import() → bool` — `SELECT 1 FROM import_logs WHERE status = 'running' LIMIT 1`
- `get_history(limit=20) → list[dict]` — `SELECT ... FROM import_logs LEFT JOIN users ... ORDER BY started_at DESC LIMIT %s`

If Phase 02 was implemented without these, they must be added to `ImportLogRepository` in this phase before the routes can be tested.

---

## Decision Log

### HTTP 202 for Start Import (ADR-08-01)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** `POST /api/import/start` returns immediately — the work happens in the background. The correct HTTP status for "accepted but not yet complete" is 202 Accepted, not 200 OK.

**Decision:** Return 202 with `{success: True, import_id: N}`.

**Consequences:**
- **Positive:** Semantically correct. Some HTTP clients automatically handle 202 differently (e.g. show a "pending" state).
- **Negative:** Minor — the JS fetch caller must treat both 200 and 202 as success, or explicitly check for 202.
- **Neutral:** The Phase 10 JS will use `if (resp.ok)` which covers both.

### Concurrent Import Guard at DB Level (ADR-08-02)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** Two choices for the concurrent-import guard: (a) in-memory flag on `IMPORT_RUNNER`, (b) DB query against `import_logs`.

**Decision:** Use the DB query (`has_running_import()`). This is resilient to server restarts (the orphan-cleanup in Phase 02 flips stale `running` rows to `failed` on startup, so the guard doesn't block forever after a crash).

**Consequences:**
- **Positive:** Correct even across restarts.
- **Negative:** One extra SELECT per start-import request — negligible cost.

---

## Implementation Steps

### Step 0: Test Definition (TDD)

Add to `tests/routes/test_import_routes.py`:

```python
class TestStartImport:

    def test_start_returns_202_with_import_id(self, client, login_admin, monkeypatch):
        monkeypatch.setattr('routes.import_routes.ImportLogRepository',
                            _mock_repo_factory(has_running=False, create_id=7))
        monkeypatch.setattr('routes.import_routes.IMPORT_RUNNER.start_import',
                            lambda *a, **kw: None)
        resp = client.post('/api/import/start',
                           json={'date_start': '2026-01-01', 'date_end': '2026-01-31'})
        assert resp.status_code == 202
        assert resp.get_json()['import_id'] == 7

    def test_start_rejects_bad_dates(self, client, login_admin):
        resp = client.post('/api/import/start',
                           json={'date_start': 'not-a-date', 'date_end': '2026-01-31'})
        assert resp.status_code == 400

    def test_start_rejects_end_before_start(self, client, login_admin):
        resp = client.post('/api/import/start',
                           json={'date_start': '2026-02-01', 'date_end': '2026-01-01'})
        assert resp.status_code == 400

    def test_start_rejects_concurrent_import(self, client, login_admin, monkeypatch):
        monkeypatch.setattr('routes.import_routes.ImportLogRepository',
                            _mock_repo_factory(has_running=True))
        resp = client.post('/api/import/start',
                           json={'date_start': '2026-01-01', 'date_end': '2026-01-31'})
        assert resp.status_code == 409


class TestImportHistory:

    def test_history_returns_list(self, client, login_admin, monkeypatch):
        fake_rows = [{'id': 1, 'status': 'completed', 'stats': {}, 'started_at': None,
                      'finished_at': None, 'date_range_start': None, 'date_range_end': None,
                      'dry_run': False, 'triggered_by_user_id': 1, 'triggered_by_name': 'Admin',
                      'error_message': None, 'session_status': 'active'}]
        monkeypatch.setattr('routes.import_routes.ImportLogRepository',
                            _mock_repo_factory(history=fake_rows))
        resp = client.get('/api/import/history')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['count'] == 1
        assert body['history'][0]['status'] == 'completed'
```

Helper factory:

```python
def _mock_repo_factory(has_running=False, create_id=1, history=None):
    from unittest.mock import MagicMock
    instance = MagicMock()
    instance.has_running_import.return_value = has_running
    instance.create.return_value = create_id
    instance.get_history.return_value = history or []
    instance.get_by_id.return_value = None
    cls = MagicMock(return_value=instance)
    return cls
```

### Step 1: Add `import_page` to `main_bp`

Edit `routes/main_routes.py` — add after existing routes:

```python
@main_bp.route('/import')
@login_required
@module_permission_required('data_import')
def import_page():
    return render_template('data_import/index.html')
```

Also add `module_permission_required` to the imports at the top of `main_routes.py` if not already present.

### Step 2: Add Routes to `import_routes.py`

Append `start_import()` and `import_history()` to `routes/import_routes.py` (see Requirements section for full code).

Add missing imports at top of `import_routes.py`:

```python
from datetime import datetime, date, timedelta
```

### Step 3: Add `has_running_import()` and `get_history()` to Repository

If Phase 02 didn't include these methods, add them to `repositories/data_import/import_log_repository.py`:

```python
def has_running_import(self) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM import_logs WHERE status = 'running' LIMIT 1")
    return cursor.fetchone() is not None

def get_history(self, limit: int = 20) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT il.*,
               u.full_name AS triggered_by_name
        FROM   import_logs il
        LEFT JOIN users u ON u.id = il.triggered_by_user_id
        ORDER  BY il.started_at DESC
        LIMIT  %s
    """, (limit,))
    return [dict(r) for r in cursor.fetchall()]
```

### Step 4: Run Tests

- [ ] `pytest tests/routes/test_import_routes.py -v` — all pass
- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `POST /api/import/start` returns 202 + `{import_id}` for valid input
- [ ] `POST /api/import/start` returns 400 for invalid/missing dates
- [ ] `POST /api/import/start` returns 409 when another import is running
- [ ] `GET /api/import/history` returns `{success, history, count}`
- [ ] `GET /import` renders the template (HTTP 200, Content-Type text/html)
- [ ] All three routes require `@login_required` + `@module_permission_required('data_import')`
- [ ] All new tests pass

**Integration:**

- [ ] Manual: POST to `/api/import/start` → import_id returned → SSE stream shows live progress
- [ ] Manual: POST again while import running → 409 response
- [ ] Manual: GET `/api/import/history` → list renders in browser JSON

---

## Quality Assurance

### Review Checklist

- [ ] `start_import` returns 202, not 200
- [ ] `ConflictError` used for concurrent import (not `ValidationError`)
- [ ] `ValidationError` used for bad dates (not `AppError` directly)
- [ ] No raw SQL in route handlers — all DB via `ImportLogRepository`
- [ ] `logger.info` logs the import start with id + date range
- [ ] `import_page` route uses `module_permission_required('data_import')`

---

## Dependencies

### Upstream (Required Before Starting)

- **Phase 02** — `ImportLogRepository` with `create()`, `has_running_import()`, `get_history()`
- **Phase 05** — `IMPORT_RUNNER.start_import()`
- **Phase 07** — `routes/import_routes.py` exists

### Downstream (Will Use This Phase)

- **Phase 09** — template rendered by `main.import_page`
- **Phase 10** — JS calls all three endpoints

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Manual smoke: full import triggered from browser, watched in SSE stream
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 08 — start import + history + page route`

---

**Previous:** [[phase-07-session-management|Phase 07: Session Management Endpoints]]
**Next:** [[phase-09-import-template|Phase 09: Import Page Template + Sidebar Link]]
