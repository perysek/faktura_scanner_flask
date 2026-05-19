---
title: "Phase 04: Import Service — Core Pipeline"
description: "Build services/data_import_service.py — orchestrates Playwright download, xlsx parse, appointment+income inserts, and progress event emission."
skill: service-builder
status: pending
group: "import-engine"
dependencies: [phase-03-postgres-lookup-builders]
tags: [phase, implementation, service, postgres, playwright, sse]
created: 2026-05-19
updated: 2026-05-19
---

# Phase 04: Import Service — Core Pipeline

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 03 | **Status:** Pending

---

## Overview

Build `services/data_import_service.py` — the orchestration layer that ties everything together: invokes `fetch_xlsx_playwright()` (reused from the reference script), parses the xlsx, runs lookups, inserts appointments + appointment_services + income_records, updates `clients.last_visit_date`, and emits progress events on a callback for the SSE stream to consume.

**Critical change vs reference script:** Every INSERT/SELECT uses `%s` placeholders, `RETURNING id` for new appointment ids, and `safe_commit(conn)`. Dry-run mode performs the full parse but skips INSERTs entirely (the reference script uses `conn.rollback()` — we want to never write the rows in the first place, so the import_logs row stays accurate).

**Goal:** A `DataImportService` class with a single public entry point `run_import(import_id, date_start, date_end, dry_run, progress_callback)` that runs synchronously from a thread.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** None directly. Progress events feed the SSE stream in Phase 06.
- **Server Layer:** New service module called by the background runner (Phase 05).
- **Database Layer:** Inserts into `appointments`, `appointment_services`, `income_records`; updates `clients.last_visit_date`; reads from `employees.commission_rate` for commission calculation.
- **Integrations:** Calls `fetch_xlsx_playwright()` from `scripts/import_appointments_playwright.py` (imported, not copied) for the download step.

### User Workflow

No direct user surface. Internal flow:

**Trigger:** Phase 05 runner spawns a thread that calls `DataImportService().run_import(...)`.

**Steps:**
1. Service emits "Starting import" event
2. Service runs `fetch_xlsx_playwright(...)` (async, wrapped via `asyncio.run` inside the thread) → downloads `caldis_pw_rezerwacje_<dates>.xlsx`
3. Service checks session status (from Playwright result or a probe) → calls `repo.update_session_status(import_id, ...)`
4. Service opens a thread-local DB connection
5. Service builds the 4 lookup maps (Phase 03 helpers)
6. For each xlsx row:
   - Parse, resolve, dedupe
   - If valid + not duplicate: INSERT appointment, appointment_services, income_records; UPDATE clients.last_visit_date
   - Increment the appropriate counter
   - Every N rows (default 10), emit a progress event with current stats
7. On success: commit, call `repo.mark_completed(import_id, final_stats)`, emit "Done" event
8. On failure: rollback, call `repo.mark_failed(import_id, str(exc), partial_stats)`, emit "Error" event
9. Cleanup xlsx file unless `keep_xlsx=True` (this phase: always cleanup)

**Success Outcome:** `import_logs` row reflects final state; the SSE consumer sees a stream of progress events ending in "completed" or "failed".

### Problem Being Solved

**Pain Point:** Without this service, the reference script can't run inside the Flask app — it uses SQLite, prints to stdout, and runs synchronously from `__main__`. We need a class that's thread-safe, PostgreSQL-native, and emits structured events.

**Alternative Approach:** Have the runner thread directly call helpers and write SQL inline. Rejected — too much logic for a thread function; we want a testable service class.

### Integration Points

**Upstream Dependencies:**
- Phase 03 helpers (`build_*_map`, `resolve_*`, parsers)
- Phase 02 `ImportLogRepository`
- `scripts/import_appointments_playwright.py:fetch_xlsx_playwright` (Playwright download function)
- `config/database.py:get_pool` (for thread-local connection)

**Downstream Consumers:**
- Phase 05 runner spawns a thread that calls `run_import(...)`

**Data Flow:**

```
run_import(import_id, dates, dry_run, callback)
  │
  ├─► emit("playwright_start")
  ├─► fetch_xlsx_playwright(...)  ──► xlsx_path
  ├─► emit("playwright_done")
  │
  ├─► pool.getconn() ──► thread-local conn
  ├─► build_employee_map(conn) + others
  │
  ├─► for each row in xlsx:
  │     ├─► parse + resolve
  │     ├─► if valid:
  │     │     ├─► INSERT appointments RETURNING id ──► appointment_id
  │     │     ├─► INSERT appointment_services
  │     │     ├─► INSERT income_records
  │     │     └─► UPDATE clients.last_visit_date
  │     └─► emit progress every 10 rows
  │
  ├─► repo.mark_completed(import_id, stats) (or mark_failed)
  ├─► emit("done")
  ├─► xlsx_path.unlink()
  └─► pool.putconn(conn)
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Playwright async wrapping:** The reference script's `fetch_xlsx_playwright` is async. The service runs in a thread. Use `asyncio.run(fetch_xlsx_playwright(...))` inside the thread, or refactor to sync via `sync_api` from Playwright?
   - **Context:** `asyncio.run()` in a thread works but spins up a new event loop each call. Playwright also has a sync API (`playwright.sync_api`) that requires no event loop. Sync API is simpler.
   - **Assumptions if unanswered:** Use `asyncio.run(...)` to minimize changes to the reference script — keep `fetch_xlsx_playwright` as-is and just call it. The cost (one event loop per import) is negligible.
   - **Impact:** Wrong choice could cause "RuntimeError: There is no current event loop" failures.

2. **Thread-local DB connection:** The service runs in a thread; `DatabaseConnection.get_connection()` uses Flask's `g`, which is request-scoped and NOT thread-safe outside a request. How do we get a connection?
   - **Context:** Two options: (a) `pool.getconn()` directly and pass it through; (b) `with app.app_context(): ...` to fake a request context.
   - **Assumptions if unanswered:** Option (a) — acquire from pool, pass explicitly, return on cleanup. Avoids Flask request context entanglement.
   - **Impact:** Wrong choice means the import either uses a stale connection or blocks the request pool.

3. **Progress event format:** What's the schema?
   - **Context:** SSE consumers parse `data: <json>\n\n`. We need a consistent shape.
   - **Assumptions if unanswered:**
     ```json
     {
       "type": "log" | "stats" | "status",
       "message": "Human-readable line",
       "stats": {...},          // optional, only on type=stats
       "status": "running" | "completed" | "failed",  // optional, only on type=status
       "timestamp": "ISO-8601"
     }
     ```
   - **Impact:** Frontend in Phase 10 must match this schema.

4. **Stats update frequency:** Every row, every 10 rows, or every batch?
   - **Context:** Updating `import_logs.stats` every row hammers the DB. Updating every 10 rows is a reasonable middle ground.
   - **Assumptions if unanswered:** Every 10 rows + always at end.
   - **Impact:** Too frequent → DB load; too rare → UI feels frozen.

### Validation Checklist

- [ ] Phase 03 helpers tested + merged
- [ ] `scripts/import_appointments_playwright.py:fetch_xlsx_playwright` is importable (verify path)
- [ ] `playwright` is in `requirements.txt` and `python -m playwright install chromium` has been run on the host
- [ ] Phase 02 `ImportLogRepository` is available

> [!CAUTION]
> Connections from the pool MUST be returned even on exception. Wrap the import logic in `try/finally` with `pool.putconn(conn)` in `finally`.

---

## Requirements

### Functional

- Class `DataImportService` with constructor taking no required args (uses default repos)
- Method `run_import(import_id, date_start, date_end, dry_run, progress_callback)`:
  - `progress_callback: Callable[[dict], None]` — pushes events to the queue (provided by Phase 05 runner)
  - Returns the final stats dict
  - Catches all exceptions, marks the log failed, re-raises a wrapped `AppError` so the runner can log it
- Stats schema (matches the reference script exactly):
  ```python
  {
    "inserted": int,
    "skipped_zero": int,
    "skipped_no_client": int,
    "skipped_no_employee": int,
    "skipped_duplicate": int,
    "errors": int,
  }
  ```
- Dry-run mode: parse + resolve + dedupe-check, but skip all INSERTs and UPDATEs entirely. Still emits stats events.
- Session-status detection: based on Playwright outcome (success = 'active'; "Sesja wygasla" exception = 'expired'; "Brak zapisanej sesji" exception = 'missing'). Call `repo.update_session_status(import_id, ...)` accordingly.

### Technical

- New file: `services/data_import_service.py`
- New exception class: `ImportError(AppError)` with `status_code = 400` (matches `AbsenceError` pattern)
- Use `from config.database import get_pool` (pool directly, not `get_db_connection()`)
- Connection: acquire once at start, pass to every helper + repo call, return in `finally`
- INSERTs use the existing patterns from `repositories/appointments/appointment_repository.py:create` — `%s` placeholders, `RETURNING id`, `safe_commit(conn)` is NOT used here (we manage commits explicitly in this service because it's outside request context)
- Wrap the whole row-loop in a try/except per-row — one bad row should not abort the import. Increment `errors` counter and continue.

---

## Decision Log

### Direct Pool Acquisition, Not g-context (ADR-04-01)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** The service runs in a thread. Flask's `g` is per-request. Two viable patterns:
- (a) `pool.getconn()` directly, manage connection lifecycle manually
- (b) `with app.app_context(): ...` — works but couples the thread to Flask state

**Decision:** Option (a). The service knows it's stateless w.r.t. Flask; it just needs a Postgres connection.

**Consequences:**
- **Positive:** No Flask coupling; trivial to unit test.
- **Negative:** Must remember to `putconn` in `finally`. Code review enforces this.
- **Neutral:** Same approach as `scheduler.py` uses for its background SMS work.

### Dry-Run Skips INSERTs Entirely (ADR-04-02)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** Reference script does `conn.rollback()` at end of dry-run. That's fine for SQLite but in Postgres with `safe_commit`, a previous commit might already have flushed some rows.

**Decision:** Dry-run mode short-circuits before the INSERT block. Counters are incremented as if the insert succeeded.

**Consequences:**
- **Positive:** Zero risk of accidental writes. `import_logs.dry_run=TRUE` is honored exactly.
- **Negative:** None.

### Per-Row Try/Except, Don't Abort on Single Failure (ADR-04-03)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** A single bad row (e.g. a NULL `employee_id` constraint violation) shouldn't kill an entire import.

**Decision:** Wrap each row's INSERT block in try/except. Increment `errors` counter, log with `logger.exception`, continue.

**Consequences:**
- **Positive:** Resilient imports; admins still get most of the data even with bad rows.
- **Negative:** If 100% of rows error, the import "succeeds" with `errors=N`. Mitigation: if `errors > inserted`, log a WARNING in `mark_completed`.

---

## Implementation Steps

### Step 0: Test Definition (TDD)

#### 0.1: Service unit tests

Create `tests/services/test_data_import_service.py`. The test mocks Playwright via patch and uses a small in-memory xlsx fixture:

```python
"""
Tests for DataImportService.
- Playwright is mocked (we don't hit caldis.pl during tests).
- DB is mocked via mock_db fixture.
- pandas read_excel is mocked to return a small DataFrame.
"""
import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock
import pandas as pd


def _build_xlsx_df():
    """Small in-memory DataFrame mimicking the caldis.pl xlsx structure."""
    return pd.DataFrame([
        {
            'Data utworzenia': '2026-01-10 08:00:00',
            'Od': '2026-01-15 10:00:00',
            'Do': '2026-01-15 11:30:00',
            'Imię i nazwisko': 'Anna Kowalska',
            'Telefon': '504020116',
            'Kalendarz': 'Kasia',
            'Kategoria': 'Manicure',
            'Suma brutto': '120.00',
        },
        {
            'Data utworzenia': '2026-01-10 08:00:00',
            'Od': '2026-01-15 12:00:00',
            'Do': '2026-01-15 13:00:00',
            'Imię i nazwisko': 'Jan Nowak',
            'Telefon': '',
            'Kalendarz': 'Kasia',
            'Kategoria': 'Pedicure',
            'Suma brutto': '0',     # → skipped_zero
        },
    ])


class TestDataImportService:

    @patch('services.data_import_service.fetch_xlsx_playwright')
    @patch('services.data_import_service.pd.read_excel')
    def test_dry_run_does_not_insert(self, mock_read_excel, mock_fetch,
                                      mock_db):
        mock_read_excel.return_value = _build_xlsx_df()
        mock_fetch.return_value = '/tmp/fake.xlsx'

        # Mock the lookup builders to return non-empty maps
        mock_db.cursor.fetchall.side_effect = [
            [{'id': 1, 'first_name': 'Kasia'}],                  # employees
            [{'id': 5, 'first_name': 'Anna', 'last_name': 'Kowalska'}],  # clients
            [{'id': 5, 'phone': '48504020116'}],                  # phones
            [{'id': 20, 'name': 'Manicure'}],                     # services
        ]

        callback = Mock()
        from services.data_import_service import DataImportService
        svc = DataImportService()
        stats = svc.run_import(
            import_id=42, date_start=date(2026, 1, 1), date_end=date(2026, 1, 31),
            dry_run=True, progress_callback=callback,
        )

        assert stats['inserted'] == 1     # one valid row
        assert stats['skipped_zero'] == 1  # the 0-amount row
        # No INSERT statements should have been executed
        for call in mock_db.cursor.execute.call_args_list:
            sql = call[0][0].upper()
            assert 'INSERT INTO APPOINTMENTS' not in sql

    @patch('services.data_import_service.fetch_xlsx_playwright')
    @patch('services.data_import_service.pd.read_excel')
    def test_skipped_duplicate_increments(self, mock_read_excel, mock_fetch,
                                           mock_db):
        mock_read_excel.return_value = _build_xlsx_df()
        mock_fetch.return_value = '/tmp/fake.xlsx'

        # Builders return lookups; the dup-check returns a row (duplicate exists)
        mock_db.cursor.fetchall.side_effect = [
            [{'id': 1, 'first_name': 'Kasia'}],
            [{'id': 5, 'first_name': 'Anna', 'last_name': 'Kowalska'}],
            [{'id': 5, 'phone': '48504020116'}],
            [{'id': 20, 'name': 'Manicure'}],
        ]
        mock_db.cursor.fetchone.return_value = {'exists': 1}  # dup found

        callback = Mock()
        from services.data_import_service import DataImportService
        svc = DataImportService()
        stats = svc.run_import(
            import_id=42, date_start=date(2026, 1, 1), date_end=date(2026, 1, 31),
            dry_run=True, progress_callback=callback,
        )
        assert stats['skipped_duplicate'] >= 1

    @patch('services.data_import_service.fetch_xlsx_playwright')
    def test_session_expired_marks_status(self, mock_fetch, mock_db):
        mock_fetch.side_effect = RuntimeError("Sesja wygasla. Brak ...")

        callback = Mock()
        from services.data_import_service import DataImportService
        from exceptions import AppError

        svc = DataImportService()
        with pytest.raises(AppError):
            svc.run_import(
                import_id=42, date_start=date(2026, 1, 1), date_end=date(2026, 1, 31),
                dry_run=False, progress_callback=callback,
            )
        # Verify update_session_status('expired') was called
        # (implementation detail — assert via spy on the repo)

    @patch('services.data_import_service.fetch_xlsx_playwright')
    @patch('services.data_import_service.pd.read_excel')
    def test_callback_emits_log_and_stats(self, mock_read_excel, mock_fetch,
                                            mock_db):
        mock_read_excel.return_value = _build_xlsx_df()
        mock_fetch.return_value = '/tmp/fake.xlsx'
        mock_db.cursor.fetchall.side_effect = [
            [{'id': 1, 'first_name': 'Kasia'}],
            [{'id': 5, 'first_name': 'Anna', 'last_name': 'Kowalska'}],
            [{'id': 5, 'phone': '48504020116'}],
            [{'id': 20, 'name': 'Manicure'}],
        ]
        callback = Mock()
        from services.data_import_service import DataImportService
        svc = DataImportService()
        svc.run_import(
            import_id=42, date_start=date(2026, 1, 1), date_end=date(2026, 1, 31),
            dry_run=True, progress_callback=callback,
        )
        # At least one 'log' event and one 'stats' event
        emitted_types = [call.args[0]['type'] for call in callback.call_args_list]
        assert 'log' in emitted_types
        assert 'stats' in emitted_types
```

#### 0.2: Run Tests

- [ ] `pytest tests/services/test_data_import_service.py -v` — all fail (module doesn't exist)

> [!WARNING]
> Don't run real Playwright in unit tests — always patch `fetch_xlsx_playwright`. A real Playwright call hangs CI and costs real network egress.

---

### Step 1: Create the Service Module

#### 1.1: File scaffold

Create `services/data_import_service.py`:

```python
"""
Data import service — orchestrates the caldis.pl Playwright download +
xlsx parse + PostgreSQL INSERTs for the Flask app's import feature.

This is the in-app equivalent of scripts/import_appointments_playwright.py:
  - DB layer: PostgreSQL via psycopg2 (not SQLite)
  - Execution: synchronous from a background thread (not __main__)
  - Output: structured progress events via callback (not stdout)
  - Audit: writes to import_logs (not just printing summary)

Reuses fetch_xlsx_playwright() from the reference script unchanged.
"""
import asyncio
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional, Any

import pandas as pd
import psycopg2.extensions

from config.database import get_pool
from exceptions import AppError
from repositories.data_import.import_log_repository import ImportLogRepository
from services.data_import_helpers import (
    DEFAULT_SERVICE_ID, KALENDARZ_OVERRIDES,
    build_employee_map, build_client_map, build_phone_map, build_service_map,
    resolve_employee_id, resolve_client_id, resolve_service_id,
    parse_appointment_date, parse_time, parse_created_at,
    calc_duration_minutes,
)

# Imported here so tests can patch it on this module's namespace
from scripts.import_appointments_playwright import fetch_xlsx_playwright

logger = logging.getLogger(__name__)


class ImportError(AppError):
    """Import pipeline failure — maps to HTTP 400."""
    status_code = 400


class DataImportService:
    """Orchestrates a single import run end-to-end."""

    def __init__(self, log_repo: Optional[ImportLogRepository] = None):
        self.log_repo = log_repo or ImportLogRepository()
        self.temp_dir = Path(__file__).resolve().parent.parent / 'assets' / 'temp'

    # ── entry point ──────────────────────────────────────────────────────────
    def run_import(self, import_id: int,
                    date_start: date, date_end: date,
                    dry_run: bool,
                    progress_callback: Callable[[dict], None]) -> dict:
        """Run the full pipeline. Returns the final stats dict.

        Errors are caught, the log row is marked failed, and ImportError is raised
        so the runner can log it.
        """
        stats = self._zero_stats()
        conn: Optional[psycopg2.extensions.connection] = None
        pool = get_pool()
        xlsx_path: Optional[Path] = None

        try:
            self._emit(progress_callback, 'log',
                       f"Start importu (zakres {date_start} → {date_end}, dry_run={dry_run})")

            # ── Phase 1: Playwright download ─────────────────────────────────
            xlsx_path = self._download_xlsx(import_id, date_start, date_end,
                                             progress_callback)

            # ── Phase 2: open thread-local DB connection ─────────────────────
            conn = pool.getconn()

            # ── Phase 3: build lookup maps ───────────────────────────────────
            self._emit(progress_callback, 'log', 'Budowanie tablic wyszukiwania...')
            employee_map = build_employee_map(conn)
            client_map   = build_client_map(conn)
            phone_map    = build_phone_map(conn)
            service_list = build_service_map(conn)
            self._emit(progress_callback, 'log',
                       f"Pracownicy: {len(employee_map)}, "
                       f"klienci: {len(client_map)//2}, "
                       f"klienci z telefonem: {len(phone_map)}, "
                       f"usługi: {len(service_list)}")

            # ── Phase 4: parse xlsx + insert ─────────────────────────────────
            df = pd.read_excel(xlsx_path, engine='openpyxl', dtype=str)
            df.columns = [c.strip() for c in df.columns]
            self._emit(progress_callback, 'log',
                       f"Wierszy do przetworzenia: {len(df)}")

            for idx, row in df.iterrows():
                self._process_row(row, idx, conn, dry_run, stats,
                                  employee_map, client_map, phone_map, service_list)
                # Update stats every 10 rows
                if (stats['inserted'] + stats['skipped_zero'] + stats['skipped_no_client']
                        + stats['skipped_no_employee'] + stats['skipped_duplicate']
                        + stats['errors']) % 10 == 0:
                    self.log_repo.update_stats(import_id, stats, conn=conn)
                    self._emit(progress_callback, 'stats', None, stats=stats)

            # ── Phase 5: commit + mark completed ─────────────────────────────
            if not dry_run:
                conn.commit()
            else:
                conn.rollback()  # defensive — should be no writes in dry-run

            self.log_repo.mark_completed(import_id, stats, conn=conn)
            self._emit(progress_callback, 'log',
                       f"Zakończono. Dodano: {stats['inserted']}, "
                       f"pominięto: {stats['skipped_zero'] + stats['skipped_no_client'] + stats['skipped_no_employee'] + stats['skipped_duplicate']}, "
                       f"błędy: {stats['errors']}")
            self._emit(progress_callback, 'status', None, status='completed')
            return stats

        except Exception as exc:
            logger.exception(f"Import {import_id} failed")
            error_message = str(exc) or type(exc).__name__
            # Try to mark failed (best effort — might fail if conn is dead)
            try:
                self.log_repo.mark_failed(import_id, error_message,
                                            stats=stats, conn=conn)
            except Exception:
                logger.exception("Could not write failure status to import_logs")
            # Detect session-related errors → update session_status
            if conn is not None:
                if 'Sesja wygasla' in error_message:
                    try:
                        self.log_repo.update_session_status(import_id, 'expired', conn=conn)
                    except Exception:
                        pass
                elif 'Brak zapisanej sesji' in error_message:
                    try:
                        self.log_repo.update_session_status(import_id, 'missing', conn=conn)
                    except Exception:
                        pass
            self._emit(progress_callback, 'log', f"BŁĄD: {error_message}")
            self._emit(progress_callback, 'status', None, status='failed')
            raise ImportError(error_message) from exc

        finally:
            if conn is not None:
                try:
                    pool.putconn(conn)
                except Exception:
                    logger.exception("Could not return connection to pool")
            if xlsx_path is not None and xlsx_path.exists():
                try:
                    xlsx_path.unlink()
                except Exception:
                    logger.warning(f"Could not delete xlsx {xlsx_path}")

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _zero_stats() -> dict:
        return {
            'inserted': 0,
            'skipped_zero': 0,
            'skipped_no_client': 0,
            'skipped_no_employee': 0,
            'skipped_duplicate': 0,
            'errors': 0,
        }

    @staticmethod
    def _emit(callback: Callable[[dict], None], event_type: str,
              message: Optional[str], **extra) -> None:
        """Build a progress event dict and call the callback."""
        event = {
            'type': event_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            **extra,
        }
        callback(event)

    def _download_xlsx(self, import_id: int, date_start: date, date_end: date,
                       progress_callback: Callable[[dict], None]) -> Path:
        """Run Playwright download, update session_status accordingly."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        xlsx_name = f"caldis_pw_rezerwacje_{date_start}_{date_end}_{import_id}.xlsx"
        xlsx_path = self.temp_dir / xlsx_name
        self._emit(progress_callback, 'log', 'Pobieranie xlsx z caldis.pl (Playwright)...')
        # fetch_xlsx_playwright is async — run it via asyncio.run in this thread
        asyncio.run(
            fetch_xlsx_playwright(
                email=None, password=None,
                date_start=date_start, date_end=date_end,
                output_path=xlsx_path,
                headed=False,
            )
        )
        # If we got here, the session is active
        try:
            self.log_repo.update_session_status(import_id, 'active')
        except Exception:
            pass
        self._emit(progress_callback, 'log', f"Pobrano: {xlsx_path.name}")
        return xlsx_path

    def _process_row(self, row, idx: int,
                     conn: psycopg2.extensions.connection,
                     dry_run: bool, stats: dict,
                     employee_map: dict, client_map: dict,
                     phone_map: dict, service_list: list) -> None:
        """Parse + dedupe + insert a single xlsx row. Updates stats in place."""
        try:
            suma_brutto_raw = row.get('Suma brutto', '0')
            try:
                suma_brutto = float(str(suma_brutto_raw).replace(',', '.')) if suma_brutto_raw else 0.0
            except (ValueError, TypeError):
                suma_brutto = 0.0
            if suma_brutto == 0:
                stats['skipped_zero'] += 1
                return

            od_cell = row.get('Od', '')
            do_cell = row.get('Do', '')
            imie_cell = row.get('Imię i nazwisko', row.get('Imie i nazwisko', ''))
            telefon_cell = row.get('Telefon', '')
            kalendarz_cell = row.get('Kalendarz', '')
            kategoria_cell = row.get('Kategoria', '')

            appointment_date = parse_appointment_date(od_cell)
            start_time = parse_time(od_cell)
            end_time = parse_time(do_cell)
            created_at = parse_created_at(row.get('Data utworzenia', ''))
            duration_minutes = calc_duration_minutes(od_cell, do_cell)

            if not (appointment_date and start_time and end_time):
                stats['errors'] += 1
                return

            kal_lower = str(kalendarz_cell).strip().lower() if kalendarz_cell else ''
            if kal_lower in KALENDARZ_OVERRIDES:
                employee_id, forced_service_id = KALENDARZ_OVERRIDES[kal_lower]
            else:
                employee_id = resolve_employee_id(kalendarz_cell, employee_map)
                forced_service_id = None

            if employee_id is None:
                stats['skipped_no_employee'] += 1
                return

            client_id = resolve_client_id(imie_cell, client_map, telefon_cell, phone_map)
            if client_id is None:
                stats['skipped_no_client'] += 1
                return

            # Duplicate check
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM appointments
                WHERE employee_id = %s AND appointment_date = %s AND start_time = %s
                  AND is_deleted = FALSE
                """,
                (employee_id, appointment_date, start_time),
            )
            if cursor.fetchone() is not None:
                stats['skipped_duplicate'] += 1
                return

            service_id = forced_service_id if forced_service_id is not None \
                else resolve_service_id(kategoria_cell, service_list)

            cursor.execute("SELECT commission_rate FROM employees WHERE id = %s",
                           (employee_id,))
            emp_row = cursor.fetchone()
            commission_rate = float(emp_row['commission_rate'] or 0) if emp_row else 0.0
            commission_amount = round(suma_brutto * commission_rate / 100, 2)
            total_price = round(suma_brutto, 2)

            if dry_run:
                stats['inserted'] += 1
                return

            # INSERT appointments
            cursor.execute(
                """
                INSERT INTO appointments (
                    client_id, employee_id, status,
                    appointment_date, start_time, end_time,
                    total_price, total_duration, discount_amount,
                    created_at, updated_at
                ) VALUES (%s, %s, 'completed', %s, %s, %s, %s, %s, 0, %s, %s)
                RETURNING id
                """,
                (client_id, employee_id,
                 appointment_date, start_time, end_time,
                 total_price, duration_minutes,
                 created_at, created_at),
            )
            appointment_id = cursor.fetchone()['id']

            # INSERT appointment_services
            cursor.execute(
                """
                INSERT INTO appointment_services (
                    appointment_id, service_id, price_charged, duration_minutes,
                    commission_rate, commission_amount, is_addon
                ) VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                """,
                (appointment_id, service_id, total_price, duration_minutes,
                 commission_rate, commission_amount),
            )

            # INSERT income_records
            cursor.execute(
                """
                INSERT INTO income_records (
                    appointment_id, client_id, employee_id,
                    total_amount, discount_amount, net_amount, commission_total,
                    payment_date, created_at
                ) VALUES (%s, %s, %s, %s, 0, %s, %s, %s, %s)
                """,
                (appointment_id, client_id, employee_id,
                 total_price, total_price, commission_amount,
                 appointment_date, created_at),
            )

            # UPDATE clients.last_visit_date
            cursor.execute(
                """
                UPDATE clients
                SET last_visit_date = %s
                WHERE id = %s
                  AND (last_visit_date IS NULL OR last_visit_date < %s)
                """,
                (appointment_date, client_id, appointment_date),
            )

            stats['inserted'] += 1

        except Exception:
            logger.exception(f"Error processing row {idx}")
            stats['errors'] += 1
```

- [ ] Mirror the docstring style from `services/absence_service.py`
- [ ] All exceptions caught per row → `stats['errors']` increment + continue
- [ ] `is_deleted = FALSE` filter in the duplicate-check query (matches the rest of the codebase)

---

### Step 2: Verify Tests

- [ ] `pytest tests/services/test_data_import_service.py -v` — all pass
- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `services/data_import_service.py` exists with `DataImportService` class + `ImportError` exception
- [ ] `run_import` returns the final stats dict on success
- [ ] `run_import` calls `log_repo.mark_completed` on success and `log_repo.mark_failed` on error
- [ ] Dry-run executes no INSERT/UPDATE on appointments, appointment_services, income_records, clients
- [ ] Connection returned to pool in `finally`
- [ ] xlsx file deleted in `finally`

**Quality Gates:**

- [ ] No `print()` statements
- [ ] Every SQL placeholder is `%s`
- [ ] Per-row try/except in place
- [ ] All tests pass

**Integration:**

- [ ] Phase 05 runner can call `run_import` from a thread and receive progress events via callback

---

## Quality Assurance

### Test Plan

#### Manual Testing

- [ ] **Real dry-run:** From a Python REPL, run:
  ```python
  from services.data_import_service import DataImportService
  from datetime import date
  svc = DataImportService()
  # Create a log row first (or mock)
  log_id = svc.log_repo.create(date(2026,1,1), date(2026,1,31), True, 1)
  events = []
  svc.run_import(log_id, date(2026,1,1), date(2026,1,31), True, lambda e: events.append(e))
  ```
  - Expected: Runs end-to-end (assuming a valid Playwright session), stats returned, `import_logs` row updated to `completed`, no appointments inserted.

- [ ] **Force failure:** Move/rename the session file. Run a real import.
  - Expected: `mark_failed` is called, `session_status='missing'` is set, progress events end with `status='failed'`.

#### Automated Testing

```bash
pytest tests/services/test_data_import_service.py -v
pytest tests/                                          # full suite
```

#### Performance Testing

- [ ] **100-row import:** Target completion (excluding Playwright download) < 5s. Actual: to be measured.
- [ ] **DB stat updates throttled:** Every 10 rows. Verify by inspecting `import_logs.stats` evolution during a real run.

### Review Checklist

- [ ] **Code Review Gate:**
  - [ ] Run `/code-review plans/260519-data-import-playwright/phase-04-import-service-core.md` with files: `services/data_import_service.py`, `tests/services/test_data_import_service.py`
  - [ ] Read review at `plans/260519-data-import-playwright/reviews/code/phase-04.md`

- [ ] **Code Quality:**
  - [ ] All tests pass; type hints on every public method

- [ ] **Security:**
  - [ ] No raw user input concatenated into SQL
  - [ ] `xlsx_path` is server-controlled (not user-supplied)
  - [ ] No secrets logged

- [ ] **Documentation:**
  - [ ] Module docstring explains the relationship to the reference script

- [ ] **Project Pattern Compliance:**
  - [ ] All SQL uses `%s` + `RealDictCursor` row access
  - [ ] Exception inherits from `AppError`
  - [ ] Logging follows project convention

---

## Dependencies

### Upstream (Required Before Starting)

- **Phase 03** — helpers and resolvers
- **Phase 02** — `ImportLogRepository`
- **Reference script** — `scripts/import_appointments_playwright.py` (already in repo, imported unchanged)

### Downstream (Will Use This Phase)

- **Phase 05** — runner spawns the thread that calls `run_import`

### External Services

- caldis.pl (via Playwright) — must have a valid session file on the host

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 04 — DataImportService core pipeline`

---

## Notes

### Technical Considerations

- `asyncio.run(...)` inside a thread is safe as long as each call gets its own event loop. We never call it concurrently from the same thread, so this is fine.
- `pool.getconn()` outside of Flask's request context bypasses the per-request `g.db` machinery — that's intentional. The thread manages the lifecycle.
- The xlsx file lives in `assets/temp/` and is unique per import (`_{import_id}` suffix) to prevent collisions if (somehow) two imports run concurrently.

### Known Limitations

- A connection acquired by the thread holds a pool slot for the duration of the import (30–120s). If multiple imports run in parallel and exhaust the pool, the next request will block briefly. Phase 05 prevents concurrent imports, so this is a non-issue.
- xlsx is parsed entirely into memory via `pd.read_excel`. For 10K+ row imports this could spike memory by 50–100MB. Acceptable for the salon's expected scale.

### Future Enhancements

- Add bulk INSERT batching (currently inserts one row at a time)
- Add row-level "skip reason" detail to stats for better UI feedback
- Support incremental updates (re-import = update existing instead of skip-duplicate)

---

**Previous:** [[phase-03-postgres-lookup-builders|Phase 03: PostgreSQL Lookup Builders + Parser Helpers]]
**Next:** [[phase-05-background-runner|Phase 05: Background Runner + Progress Queue]]
