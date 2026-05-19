---
title: "Phase 05: Background Runner + Progress Queue"
description: "Thread-based runner that starts a DataImportService in a background thread, exposes a per-import-id progress queue for SSE consumption, and prevents concurrent imports."
skill: service-builder
status: pending
group: "background-task"
dependencies: [phase-04-import-service-core]
tags: [phase, implementation, threading, queue, sse]
created: 2026-05-19
updated: 2026-05-19
---

# Phase 05: Background Runner + Progress Queue

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 04 | **Status:** Pending

---

## Overview

Build `services/data_import_runner.py` — a singleton-style manager that spawns a `threading.Thread` for each import, maintains a per-`import_id` `queue.Queue` for progress events, and enforces "only one import at a time" by checking `ImportLogRepository.find_running()` before starting.

**Goal:** The HTTP layer (Phase 08) calls `runner.start_import(...)` and immediately returns the `import_id`. The SSE endpoint (Phase 06) calls `runner.get_queue(import_id)` to pull events.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** None.
- **Server Layer:** New module `services/data_import_runner.py` with a module-level singleton `IMPORT_RUNNER`.
- **Database Layer:** Reads `import_logs` via `ImportLogRepository` for the running-import check; writes nothing directly.
- **Integrations:** None — wraps Phase 04 service.

### User Workflow

No direct user surface.

**Trigger:** Phase 08 POST `/api/import/start` calls `IMPORT_RUNNER.start_import(...)`.

**Steps:**
1. `start_import` checks if any import is currently running (DB check + memory check)
2. If yes → raises `ConflictError("Import już trwa")`
3. If no → creates the `import_logs` row, allocates a `queue.Queue`, spawns a thread
4. Thread runs `DataImportService().run_import(import_id, ..., progress_callback=queue.put)`
5. On thread exit (success or failure), a sentinel event `{type: 'done'}` is placed in the queue and the queue is left in the registry (SSE clients can still drain residual events)
6. After some retention period (1 hour), the queue is GC'd from the registry

**Success Outcome:** Caller gets `import_id` instantly; SSE stream can pull progress; only one import runs at a time across the process.

### Problem Being Solved

**Pain Point:** Calling `DataImportService.run_import` from inside the request handler would block the request for 30–120s, exhaust gunicorn workers, and trigger proxy timeouts.

**Alternative Approach:** Celery / RQ — rejected per ADR-G-01 (too much infra). The current scheduler in `scheduler.py` proves the threading model is sufficient.

### Integration Points

**Upstream Dependencies:**
- Phase 04 `DataImportService`
- Phase 02 `ImportLogRepository`

**Downstream Consumers:**
- Phase 06 SSE stream + status endpoint
- Phase 08 start + history endpoints

**Data Flow:**

```
                                     ┌──────────────────────┐
   POST /api/import/start            │ IMPORT_RUNNER        │
                ─────────────────────┤  (module singleton)  │
                  start_import(...)  └──────────────────────┘
                                              │
                                              ├─► find_running()? → ConflictError if running
                                              ├─► repo.create(...) → import_id
                                              ├─► queues[import_id] = Queue()
                                              ├─► Thread(target=_run, args=(import_id,)).start()
                                              └─► return import_id (immediately)

   Thread:
        DataImportService().run_import(
            import_id, ..., progress_callback=queues[import_id].put)

   GET /api/import/<id>/stream
                ──────► IMPORT_RUNNER.get_queue(id) → Queue
                          │
                          └─► generator pulls events, yields SSE frames
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Queue size:** Bounded or unbounded? A frozen SSE consumer with an unbounded queue could leak memory.
   - **Context:** Each event is a small dict (~200 bytes); even 1000 events is 200KB.
   - **Assumptions if unanswered:** Unbounded for simplicity. If memory becomes an issue, switch to `Queue(maxsize=1000)` and drop oldest.
   - **Impact:** Negligible at our scale.

2. **Queue retention after import finishes:** How long to keep finished queues?
   - **Context:** A user might reconnect to the SSE stream after the import already completed (e.g. they reload the page). The queue should have the final `done` event still available.
   - **Assumptions if unanswered:** Keep queues for 1 hour after `mark_completed`/`mark_failed`. Implement via a `last_activity_at` timestamp and a lazy cleanup pass at the start of each new import.
   - **Impact:** Without retention, late-arriving SSE clients see an empty queue and a `done` event was missed; they have to fall back to the status polling endpoint.

3. **Concurrent imports across multiple processes:** If we ever deploy with `gunicorn --workers 4`, two workers could each pass the "no running import" check and both start. How do we prevent that?
   - **Context:** Current deploy is single-process (Waitress on Windows, single gunicorn worker on Vultr). Phase 02 `find_running()` is the DB-level safety net.
   - **Assumptions if unanswered:** Single-process is the contract. Document this in the README. If we ever scale, replace the in-memory queue with Redis and use Postgres advisory locks.
   - **Impact:** Multi-worker deploy without changes would corrupt state. Phase 11 (future) would handle it.

4. **Cleanup interval:** The runner needs to GC old queues. Run on every start? Periodic timer?
   - **Context:** A timer thread adds complexity. Lazy cleanup on every `start_import` is simpler.
   - **Assumptions if unanswered:** Lazy cleanup at start.
   - **Impact:** A long-idle server keeps a few stale queues in memory. Acceptable.

### Validation Checklist

- [ ] Phase 04 service merged
- [ ] Confirm single-process deployment model (`gunicorn --workers 1` on Vultr, Waitress single-process on Windows)
- [ ] `threading` module behavior on Windows Waitress verified (it works, same as in `scheduler.py`)

> [!CAUTION]
> A thread that crashes silently (no exception handler at the top) becomes a zombie. The runner's thread function MUST have a top-level try/except that marks the log failed even if `DataImportService` doesn't catch the error itself.

---

## Requirements

### Functional

- Module-level singleton: `IMPORT_RUNNER = ImportRunner()`
- `ImportRunner.start_import(date_start, date_end, dry_run, triggered_by_user_id) -> int`:
  - Cleanup old queues (older than 1 hour after finish)
  - Check `find_running()` → raise `ConflictError` if anything is running
  - Create the log row (`repo.create(...)`) → get `import_id`
  - Create the queue, spawn the thread
  - Return `import_id`
- `ImportRunner.get_queue(import_id: int) -> Optional[Queue]`:
  - Return the queue if it exists, else None
- `ImportRunner.has_queue(import_id: int) -> bool`
- `ImportRunner.is_running(import_id: int) -> bool` — combines DB status check + thread alive check

### Technical

- New file: `services/data_import_runner.py`
- Use `threading.Thread(target=..., daemon=True)` — daemon so a hard process kill doesn't hang
- Use `queue.Queue` (thread-safe)
- Registry: `dict[int, dict]` with shape `{import_id: {queue: Queue, thread: Thread, finished_at: Optional[datetime]}}`
- Protect the registry with `threading.Lock` — even though most access patterns are single-writer, the SSE endpoint reads while the thread writes
- Thread function: top-level try/except → if `DataImportService` raises, log the exception, push a `{type: 'status', status: 'failed', message: str(exc)}` event into the queue, set `finished_at`
- Sentinel `{type: 'done'}` event always pushed when thread exits (success or failure) — SSE generator uses this to terminate

---

## Decision Log

### Single Module-Level Singleton (ADR-05-01)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** The runner state (registry) must be shared across all requests in the same process. Options: (a) module-level singleton, (b) Flask app extension, (c) class attribute.

**Decision:** Module-level singleton `IMPORT_RUNNER = ImportRunner()` at the bottom of `services/data_import_runner.py`.

**Consequences:**
- **Positive:** Imports cleanly: `from services.data_import_runner import IMPORT_RUNNER`. No Flask coupling.
- **Negative:** Hard to swap for tests — but the class itself is also exposed for direct instantiation in tests.
- **Neutral:** Same pattern as `scheduler.py` uses (`_scheduler` module-level var).

### Daemon Threads, Always (ADR-05-02)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** A non-daemon thread blocks process exit. A daemon thread is killed on process exit.

**Decision:** Always `daemon=True`. If the process is shutting down, an in-flight import is best-effort lost; the orphan cleanup in Phase 02 catches it on next startup.

**Consequences:**
- **Positive:** Clean shutdowns.
- **Negative:** Mid-import on shutdown = lost progress. Acceptable.

---

## Implementation Steps

### Step 0: Test Definition (TDD)

#### 0.1: Runner unit tests

Create `tests/services/test_data_import_runner.py`:

```python
"""
Tests for ImportRunner — threading, queue management, concurrent-import prevention.
DataImportService is mocked so we don't run real imports.
"""
import time
import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock


class TestImportRunner:

    def test_start_returns_import_id_immediately(self):
        from services.data_import_runner import ImportRunner

        with patch('services.data_import_runner.ImportLogRepository') as MockRepo, \
             patch('services.data_import_runner.DataImportService') as MockSvc:
            MockRepo.return_value.find_running.return_value = None
            MockRepo.return_value.create.return_value = 99
            # Block the service so the thread doesn't exit immediately
            MockSvc.return_value.run_import.side_effect = lambda *a, **kw: time.sleep(0.5) or {}

            runner = ImportRunner()
            import_id = runner.start_import(
                date(2026, 1, 1), date(2026, 1, 31),
                dry_run=False, triggered_by_user_id=1,
            )
            assert import_id == 99
            # The queue exists
            assert runner.get_queue(99) is not None

    def test_start_raises_when_another_running(self):
        from services.data_import_runner import ImportRunner
        from exceptions import ConflictError

        with patch('services.data_import_runner.ImportLogRepository') as MockRepo:
            MockRepo.return_value.find_running.return_value = {'id': 5, 'status': 'running'}
            runner = ImportRunner()
            with pytest.raises(ConflictError):
                runner.start_import(
                    date(2026, 1, 1), date(2026, 1, 31),
                    dry_run=False, triggered_by_user_id=1,
                )

    def test_queue_receives_progress_events(self):
        from services.data_import_runner import ImportRunner

        captured_callback = []

        def fake_run_import(import_id, date_start, date_end, dry_run, progress_callback):
            progress_callback({'type': 'log', 'message': 'hello'})
            return {}

        with patch('services.data_import_runner.ImportLogRepository') as MockRepo, \
             patch('services.data_import_runner.DataImportService') as MockSvc:
            MockRepo.return_value.find_running.return_value = None
            MockRepo.return_value.create.return_value = 77
            MockSvc.return_value.run_import.side_effect = fake_run_import

            runner = ImportRunner()
            import_id = runner.start_import(
                date(2026, 1, 1), date(2026, 1, 31),
                dry_run=False, triggered_by_user_id=1,
            )

            # Wait for the thread to push the event + sentinel
            time.sleep(0.1)
            q = runner.get_queue(import_id)
            events = []
            while not q.empty():
                events.append(q.get_nowait())
            types = [e['type'] for e in events]
            assert 'log' in types
            assert 'done' in types  # sentinel

    def test_thread_exception_marks_failed(self):
        from services.data_import_runner import ImportRunner

        def bad_run_import(*args, **kwargs):
            raise RuntimeError("Boom")

        with patch('services.data_import_runner.ImportLogRepository') as MockRepo, \
             patch('services.data_import_runner.DataImportService') as MockSvc:
            MockRepo.return_value.find_running.return_value = None
            MockRepo.return_value.create.return_value = 88
            MockSvc.return_value.run_import.side_effect = bad_run_import

            runner = ImportRunner()
            import_id = runner.start_import(
                date(2026, 1, 1), date(2026, 1, 31),
                dry_run=False, triggered_by_user_id=1,
            )
            time.sleep(0.1)
            # Should have called mark_failed on the repo (the service didn't, so the runner did)
            # Also: a 'status: failed' event should be in the queue
            q = runner.get_queue(import_id)
            events = []
            while not q.empty():
                events.append(q.get_nowait())
            statuses = [e.get('status') for e in events if e.get('type') == 'status']
            assert 'failed' in statuses
```

#### 0.2: Run Tests

- [ ] `pytest tests/services/test_data_import_runner.py -v` — all fail

---

### Step 1: Create the Runner Module

#### 1.1: File

Create `services/data_import_runner.py`:

```python
"""
Background runner for the caldis.pl import pipeline.

Spawns one daemon thread per import, exposes a per-import_id queue for SSE
consumers, and prevents concurrent imports via:
  - DB-level check (find_running() before start)
  - Memory-level check (registry of active threads)

Single-process deployment is assumed. For multi-worker deployments, the
in-memory queue must be replaced with Redis pub/sub and the running-import
gate must use Postgres advisory locks.
"""
import logging
import threading
import queue as queue_module
from datetime import date, datetime, timedelta
from typing import Optional

from exceptions import ConflictError
from repositories.data_import.import_log_repository import ImportLogRepository
from services.data_import_service import DataImportService

logger = logging.getLogger(__name__)

# Retention: keep finished queues around for 1 hour so a reconnecting SSE
# client can still see the final 'done' event.
QUEUE_RETENTION = timedelta(hours=1)


class ImportRunner:
    """One-import-at-a-time scheduler with per-import progress queues."""

    def __init__(self):
        self._registry: dict[int, dict] = {}
        self._lock = threading.Lock()

    # ── public API ───────────────────────────────────────────────────────────
    def start_import(self, date_start: date, date_end: date,
                     dry_run: bool, triggered_by_user_id: int) -> int:
        """Start a new import. Returns the new import_id immediately.

        Raises ConflictError if another import is already running.
        """
        with self._lock:
            self._cleanup_stale_queues_locked()

            repo = ImportLogRepository()
            existing = repo.find_running()
            if existing is not None:
                raise ConflictError(
                    f"Import już trwa (id={existing['id']}). "
                    "Poczekaj na zakończenie lub przeładuj stronę."
                )

            import_id = repo.create(
                date_start=date_start, date_end=date_end,
                dry_run=dry_run, triggered_by_user_id=triggered_by_user_id,
            )
            q: queue_module.Queue = queue_module.Queue()
            thread = threading.Thread(
                target=self._run_thread,
                args=(import_id, date_start, date_end, dry_run, q),
                daemon=True,
                name=f"import-{import_id}",
            )
            self._registry[import_id] = {
                'queue': q,
                'thread': thread,
                'finished_at': None,
            }
            thread.start()
            logger.info(f"Started import thread id={import_id} "
                        f"range={date_start}..{date_end} dry_run={dry_run}")
            return import_id

    def get_queue(self, import_id: int) -> Optional[queue_module.Queue]:
        with self._lock:
            entry = self._registry.get(import_id)
            return entry['queue'] if entry else None

    def has_queue(self, import_id: int) -> bool:
        with self._lock:
            return import_id in self._registry

    def is_running(self, import_id: int) -> bool:
        with self._lock:
            entry = self._registry.get(import_id)
            if not entry:
                return False
            return entry['thread'].is_alive()

    # ── thread body ──────────────────────────────────────────────────────────
    def _run_thread(self, import_id: int, date_start: date, date_end: date,
                    dry_run: bool, q: queue_module.Queue) -> None:
        """Thread entry — runs DataImportService, ensures cleanup."""
        try:
            svc = DataImportService()
            svc.run_import(
                import_id=import_id,
                date_start=date_start,
                date_end=date_end,
                dry_run=dry_run,
                progress_callback=q.put,
            )
        except Exception as exc:
            # Service should have already marked failed and emitted status, but as a
            # belt-and-braces safety net, ensure the queue gets a failure status.
            logger.exception(f"Import {import_id} thread crashed")
            try:
                q.put({
                    'type': 'status',
                    'status': 'failed',
                    'message': str(exc) or type(exc).__name__,
                    'timestamp': datetime.now().isoformat(),
                })
                # Ensure DB reflects failure even if service didn't write
                ImportLogRepository().mark_failed(import_id, str(exc) or type(exc).__name__)
            except Exception:
                logger.exception("Could not record thread-crash failure")
        finally:
            # Sentinel: consumers know the stream is over
            try:
                q.put({'type': 'done', 'timestamp': datetime.now().isoformat()})
            except Exception:
                pass
            with self._lock:
                if import_id in self._registry:
                    self._registry[import_id]['finished_at'] = datetime.now()

    # ── cleanup ──────────────────────────────────────────────────────────────
    def _cleanup_stale_queues_locked(self) -> None:
        """Drop queues finished more than QUEUE_RETENTION ago. Caller holds lock."""
        now = datetime.now()
        stale = [
            iid for iid, entry in self._registry.items()
            if entry['finished_at'] is not None
            and (now - entry['finished_at']) > QUEUE_RETENTION
        ]
        for iid in stale:
            del self._registry[iid]
        if stale:
            logger.info(f"Reaped {len(stale)} stale import queue(s)")


# Module-level singleton
IMPORT_RUNNER = ImportRunner()
```

- [ ] Module docstring + class docstring explain the threading + single-process contract
- [ ] Lock-protected registry access
- [ ] Sentinel `done` event always pushed
- [ ] Logger lines on start + reap + crash

---

### Step 2: Verify Tests

- [ ] `pytest tests/services/test_data_import_runner.py -v` — all pass
- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `services/data_import_runner.py` exists with `ImportRunner` class + `IMPORT_RUNNER` singleton
- [ ] `start_import` returns immediately (< 100ms) — the thread does the work
- [ ] Concurrent imports prevented (ConflictError raised)
- [ ] Queue receives progress events from the service via the callback
- [ ] `done` sentinel always reaches the queue when the thread exits
- [ ] All tests pass

**Quality Gates:**

- [ ] No `print()` statements
- [ ] Lock acquired on every registry access
- [ ] Threads are daemon

**Integration:**

- [ ] Phase 06 SSE generator reads from `IMPORT_RUNNER.get_queue(id)` and yields events
- [ ] Phase 08 start endpoint calls `IMPORT_RUNNER.start_import(...)` and returns the id

---

## Quality Assurance

### Test Plan

#### Manual Testing

- [ ] **Manual concurrent check:** Start two imports from two browser tabs in quick succession.
  - Expected: Second one returns 409 `ConflictError` with the Polish message.
- [ ] **Manual queue inspection:** Start an import; in a Python REPL:
  ```python
  from services.data_import_runner import IMPORT_RUNNER
  q = IMPORT_RUNNER.get_queue(<id>)
  while not q.empty(): print(q.get_nowait())
  ```
  - Expected: Stream of `log`, `stats` events ending in `done`.

#### Automated Testing

```bash
pytest tests/services/test_data_import_runner.py -v
pytest tests/
```

#### Performance Testing

- [ ] `start_import` returns in < 100ms (timed in test)
- [ ] Registry cleanup runs in < 10ms even with 100 stale entries

### Review Checklist

- [ ] **Code Review Gate:**
  - [ ] Run `/code-review plans/260519-data-import-playwright/phase-05-background-runner.md` with files: `services/data_import_runner.py`, `tests/services/test_data_import_runner.py`
  - [ ] Read review at `plans/260519-data-import-playwright/reviews/code/phase-05.md`

- [ ] **Code Quality:**
  - [ ] Tests pass; type hints on public methods

- [ ] **Security:**
  - [ ] Thread top-level try/except prevents zombies
  - [ ] Logger lines do not leak PII

- [ ] **Documentation:**
  - [ ] Module docstring explains the single-process contract
  - [ ] Class docstring explains lock usage

- [ ] **Project Pattern Compliance:**
  - [ ] Module-level singleton at bottom of file (matches `scheduler.py`)
  - [ ] Daemon threads (matches `scheduler.py`)

---

## Dependencies

### Upstream (Required Before Starting)

- **Phase 04** — `DataImportService`
- **Phase 02** — `ImportLogRepository.find_running()` + `create()`

### Downstream (Will Use This Phase)

- **Phase 06** — SSE stream pulls events from the queue
- **Phase 08** — start endpoint calls `start_import`

### External Services

- None.

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 05 — background runner + progress queue`

---

## Notes

### Technical Considerations

- The `IMPORT_RUNNER` singleton is created at module import time. As long as `services/data_import_runner.py` is imported before the first request (which it is — Phase 08 imports it at module level), the singleton is always available.
- Locking is conservative — we hold the lock during `start_import`'s entire setup (find_running + create + thread.start). This is fine because the operation is < 50ms.

### Known Limitations

- Single-process only. See Q3 above.
- The 1-hour retention means a long-running SSE client (e.g. left open overnight) could try to read from a reaped queue. The generator handles this gracefully by falling back to status polling.

### Future Enhancements

- Add `cancel_import(import_id)` once a cancel button is wired in the UI
- Switch to Redis-backed queues for multi-worker deployments
- Add Prometheus metrics: `import_starts_total`, `import_failures_total`, `import_duration_seconds`

---

**Previous:** [[phase-04-import-service-core|Phase 04: Import Service — Core Pipeline]]
**Next:** [[phase-06-sse-progress-stream|Phase 06: SSE Progress Stream + Status Endpoint]]
