---
title: "Phase 03: PostgreSQL Lookup Builders + Parser Helpers"
description: "Port the reference script's build_*_map functions and resolvers from SQLite to PostgreSQL, keep parser helpers as pure functions."
skill: service-builder
status: pending
group: "import-engine"
dependencies: [phase-02-import-log-repository]
tags: [phase, implementation, postgres, parser, helpers]
created: 2026-05-19
updated: 2026-05-19
---

# Phase 03: PostgreSQL Lookup Builders + Parser Helpers

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 02 | **Status:** Pending

---

## Overview

Port the lookup-building logic (`build_employee_map`, `build_client_map`, `build_phone_map`, `build_service_map`) and the pure parser/resolver helpers (`resolve_employee_id`, `resolve_client_id`, `normalize_phone`, `resolve_service_id`, `parse_appointment_date`, `parse_time`, `parse_created_at`, `calc_duration_minutes`) from `scripts/import_appointments_from_excel.py` into a new module `services/data_import_helpers.py`.

**The critical change:** Every DB query is rewritten to PostgreSQL syntax — `%s` placeholders, `RealDictCursor` rows (already configured globally), `get_db_connection()` instead of `sqlite3.Connection`.

**Goal:** A pure-Python helper module that the service in Phase 04 can call without thinking about DB engine specifics.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** None.
- **Server Layer:** New module `services/data_import_helpers.py` (or `services/data_import/helpers.py` if we choose to make `data_import` its own package).
- **Database Layer:** Read-only queries against `employees`, `clients`, `services`.
- **Integrations:** None.

### User Workflow

No direct user surface. Internal flow:

**Trigger:** Phase 04 service calls `build_employee_map(conn)`, etc., before iterating xlsx rows.

**Steps:**
1. Service opens a connection at the start of an import
2. Calls each `build_*_map(conn)` — returns a dict/list usable for O(1) lookups
3. For each xlsx row, calls `resolve_employee_id(...)`, `resolve_client_id(...)`, `resolve_service_id(...)` — pure functions that take the prebuilt maps
4. For date/time cells, calls `parse_appointment_date(cell)`, `parse_time(cell)`, etc.

**Success Outcome:** Same business logic as the reference script, but every DB read uses PostgreSQL.

### Problem Being Solved

**Pain Point:** Directly copying the SQLite helpers into the Flask app would break at runtime — `?` placeholders don't work in psycopg2, and `sqlite3.Row` vs `RealDictCursor` have subtly different key-access semantics.

**Alternative Approach:** Have Phase 04 inline all the SQL. Rejected because:
1. The reference script's helpers are well-factored already; we just need to migrate the DB layer.
2. Pure-function resolvers are easy to test in isolation (no DB needed).

### Integration Points

**Upstream Dependencies:**
- `employees`, `clients`, `services` tables (existing)
- `get_db_connection()` from `config/database.py`

**Downstream Consumers:**
- Phase 04 imports every helper and resolver

**Data Flow:**

```
build_employee_map(conn)  ──► SELECT id, first_name FROM employees
                              └─► {first_name_lower: employee_id}

build_client_map(conn)    ──► SELECT id, first_name, last_name FROM clients
                              └─► {(fn_lower, ln_lower): client_id, ...}

build_phone_map(conn)     ──► SELECT id, phone FROM clients WHERE phone IS NOT NULL
                              └─► {normalized_phone: client_id}

build_service_map(conn)   ──► SELECT id, name FROM services ORDER BY id
                              └─► [(id, name_lower), ...]

resolve_*(value, lookup)  ──► pure function, returns int or None
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Module location:** Put helpers in `services/data_import_helpers.py` (flat) or create `services/data_import/` package with `helpers.py`, `service.py`, `runner.py`?
   - **Context:** The codebase has flat services so far (`absence_service.py`, `sms_service.py`). Only `routes/auth/`, `routes/users/`, `routes/roles/` use sub-packages.
   - **Assumptions if unanswered:** Flat — `services/data_import_helpers.py`, `services/data_import_service.py`, `services/data_import_runner.py`. Easier to grep.
   - **Impact:** Either works; flat matches majority pattern.

2. **DEFAULT_SERVICE_ID:** The reference script hardcodes `DEFAULT_SERVICE_ID = 20` (Manicure klasyczny). Is service id 20 still valid in production?
   - **Context:** This is the fallback when category lookup fails. A wrong id silently misclassifies imports.
   - **Assumptions if unanswered:** Keep 20, but log a WARNING every time the fallback is used so we can audit it.
   - **Impact:** Wrong fallback id would attach the import to the wrong service category, polluting downstream reports.

3. **KALENDARZ_OVERRIDES:** The reference script has `{"zrecepcja asia": (3, 24)}`. Should this stay in code or move to a DB table?
   - **Context:** It's hand-curated and tiny. Keeping it in code is fine; moving to a table is overkill.
   - **Assumptions if unanswered:** Keep as a module-level constant `KALENDARZ_OVERRIDES`.
   - **Impact:** A future override addition requires a code change + deploy. Acceptable for now.

4. **resolve_client_id phone fallback:** The reference script uses phone-matching as a fallback. Should we also try fuzzy name matching (e.g. Levenshtein) for typos?
   - **Context:** caldis.pl users sometimes have typos in client names. The current fallback handles "p. " prefix and word-order reversal, but not "Smyith" vs "Smith".
   - **Assumptions if unanswered:** No fuzzy matching in this phase. Add a TODO and revisit only if the skip-no-client rate is high in real imports.
   - **Impact:** Some clients will need manual creation. Surface this clearly in the UI.

### Validation Checklist

- [ ] Phase 02 merged (no hard dependency on `import_logs`, but we want a clean stack)
- [ ] `services/` directory writable; no name conflicts
- [ ] DEFAULT_SERVICE_ID verified against production service table

---

## Requirements

### Functional

**Lookup builders (one connection per call):**

- `build_employee_map(conn) -> dict[str, int]` — returns `{first_name_lower: employee_id}`
- `build_client_map(conn) -> dict[tuple[str, str], int]` — returns `{(first_name_lower, last_name_lower): client_id}` with both orderings
- `build_phone_map(conn) -> dict[str, int]` — returns `{normalized_phone: client_id}`
- `build_service_map(conn) -> list[tuple[int, str]]` — returns `[(service_id, name_lower), ...]` sorted by id

**Resolvers (pure functions):**

- `resolve_employee_id(kalendarz_cell: str, employee_map: dict) -> Optional[int]`
- `resolve_client_id(full_name_raw, client_map: dict, phone_raw=None, phone_map: dict | None = None) -> Optional[int]` — phone fallback
- `resolve_service_id(kategoria_cell: str, service_list: list) -> int` — always returns an int (falls back to `DEFAULT_SERVICE_ID`)
- `normalize_phone(raw_phone) -> Optional[str]` — normalizes to `48XXXXXXXXX` (11 digits)

**Date/time helpers (pure):**

- `parse_appointment_date(cell) -> Optional[str]` — returns `YYYY-MM-DD` or None
- `parse_time(cell) -> Optional[str]` — returns `HH:MM:SS` or None
- `parse_created_at(cell) -> str` — returns `YYYY-MM-DD HH:MM:SS`, falls back to `now()`
- `calc_duration_minutes(od_cell, do_cell) -> int` — returns minutes; 0 if invalid

**Constants:**

- `DEFAULT_SERVICE_ID: int = 20`
- `KALENDARZ_OVERRIDES: dict[str, tuple[int, int]] = {"zrecepcja asia": (3, 24)}`

### Technical

- New file: `services/data_import_helpers.py`
- All SQL uses `%s` placeholders (PostgreSQL)
- Pool-managed `RealDictCursor` is already set globally (in `config/database.py`); use `row['id']` and `row['first_name']` (dict-key access)
- Accept `conn` as the first parameter to each builder, not a cursor — matches `repositories/base_repository.py` convention of acquiring a cursor inside the function
- Pure resolvers must NOT import `psycopg2` or `pandas` — keep them testable without DB / without xlsx libraries. Move all `pd.isna()` checks to a small `_is_blank(value)` helper at the top of the file that accepts any value.
- `pandas.isna` is fine to import at module level since `pandas` is already a runtime dependency (used by the Playwright script). But isolate it to the file's top.

---

## Decision Log

### Keep Helpers Pure (No DB Inside Resolvers) (ADR-03-01)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** A naive port would have `resolve_client_id` query the DB on each row. Both for performance (thousands of rows) and testability, we keep the build-once / lookup-many pattern from the reference script.

**Decision:** All DB queries happen in `build_*_map`. Resolvers take the prebuilt map and are pure functions.

**Consequences:**
- **Positive:** Easy unit testing; fast O(1) lookups.
- **Negative:** Memory cost — `build_client_map` loads every client into memory. Acceptable: <10K clients at this salon.

### Hand-Coded `_is_blank` Instead of pd.isna Everywhere (ADR-03-02)

**Date:** 2026-05-19
**Status:** Accepted

**Context:** `pd.isna` works on NaN, None, and pandas NaT, but it's awkward when the value might be a clean string. Wrapping it in a single helper localizes the dependency.

**Decision:** Define `_is_blank(v) -> bool` at the top of the module; resolvers call it.

**Consequences:**
- **Positive:** One spot to change if we ever swap pandas for openpyxl directly.
- **Negative:** None.

---

## Implementation Steps

### Step 0: Test Definition (TDD)

#### 0.1: Helper unit tests

Create `tests/services/test_data_import_helpers.py`:

```python
"""
Unit tests for data_import_helpers — pure resolvers + DB lookup builders.
DB builders use the mock_db fixture; pure resolvers are tested without mocks.
"""
import pytest
from datetime import datetime


# ── pure resolvers (no DB needed) ────────────────────────────────────────────

class TestNormalizePhone:
    def test_9_digit_plain(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('504020116') == '48504020116'

    def test_with_spaces(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone(' 504 020 116') == '48504020116'

    def test_with_plus48(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('+48504020116') == '48504020116'

    def test_with_0048(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('0048504020116') == '48504020116'

    def test_blank(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('') is None
        assert normalize_phone(None) is None
        assert normalize_phone(float('nan')) is None


class TestResolveEmployeeId:
    def test_exact_match(self):
        from services.data_import_helpers import resolve_employee_id
        emp_map = {'anna': 1, 'kasia': 2}
        assert resolve_employee_id('Anna', emp_map) == 1
        assert resolve_employee_id('KASIA', emp_map) == 2

    def test_substring_longest_wins(self):
        from services.data_import_helpers import resolve_employee_id
        emp_map = {'anna': 1, 'annabelle': 2}
        # 'zRecepcja Annabelle' contains both 'anna' and 'annabelle';
        # the resolver must prefer the longer match
        assert resolve_employee_id('zRecepcja Annabelle', emp_map) == 2

    def test_unknown(self):
        from services.data_import_helpers import resolve_employee_id
        assert resolve_employee_id('Unknown Name', {'anna': 1}) is None


class TestResolveClientId:
    def test_strip_prefix_p_dot(self):
        from services.data_import_helpers import resolve_client_id
        client_map = {('anna', 'kowalska'): 5}
        assert resolve_client_id('p. Anna Kowalska', client_map) == 5

    def test_phone_fallback(self):
        from services.data_import_helpers import resolve_client_id
        phone_map = {'48504020116': 99}
        assert resolve_client_id('Unknown Person', {}, '504020116', phone_map) == 99

    def test_returns_none_when_nothing_matches(self):
        from services.data_import_helpers import resolve_client_id
        assert resolve_client_id('Unknown', {}, None, {}) is None


class TestResolveServiceId:
    def test_exact(self):
        from services.data_import_helpers import resolve_service_id
        svc_list = [(20, 'manicure klasyczny'), (47, 'uzupełnienie żelu')]
        assert resolve_service_id('Manicure klasyczny', svc_list) == 20

    def test_prefix_match(self):
        from services.data_import_helpers import resolve_service_id
        svc_list = [(47, 'uzupełnienie żelu 1')]
        assert resolve_service_id('Uzupełnienie żelu', svc_list) == 47

    def test_default_fallback(self):
        from services.data_import_helpers import resolve_service_id, DEFAULT_SERVICE_ID
        assert resolve_service_id('Nieznana usługa', []) == DEFAULT_SERVICE_ID


class TestDateTimeParsers:
    def test_parse_appointment_date(self):
        from services.data_import_helpers import parse_appointment_date
        assert parse_appointment_date('2026-05-19 10:30:00') == '2026-05-19'
        assert parse_appointment_date(datetime(2026, 5, 19, 10, 30)) == '2026-05-19'

    def test_parse_time(self):
        from services.data_import_helpers import parse_time
        assert parse_time('2026-05-19 10:30:00') == '10:30:00'

    def test_calc_duration_minutes(self):
        from services.data_import_helpers import calc_duration_minutes
        assert calc_duration_minutes('2026-05-19 10:00:00', '2026-05-19 11:30:00') == 90


# ── DB builders (mock_db) ────────────────────────────────────────────────────

class TestBuildersUsePostgresPlaceholders:
    """Every builder must use %s placeholders, never ?."""

    def test_build_employee_map(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 1, 'first_name': 'Anna'},
            {'id': 2, 'first_name': 'Kasia'},
        ]
        from services.data_import_helpers import build_employee_map
        emp_map = build_employee_map(mock_db.connection)
        assert emp_map == {'anna': 1, 'kasia': 2}
        sql = mock_db.cursor.execute.call_args[0][0]
        assert '?' not in sql
        assert 'employees' in sql.lower()

    def test_build_client_map_both_orderings(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 5, 'first_name': 'Anna', 'last_name': 'Kowalska'}
        ]
        from services.data_import_helpers import build_client_map
        cm = build_client_map(mock_db.connection)
        assert cm[('anna', 'kowalska')] == 5
        assert cm[('kowalska', 'anna')] == 5

    def test_build_phone_map_filters_null(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 1, 'phone': '48504020116'},
        ]
        from services.data_import_helpers import build_phone_map
        pm = build_phone_map(mock_db.connection)
        assert pm == {'48504020116': 1}
        sql = mock_db.cursor.execute.call_args[0][0]
        assert "phone IS NOT NULL" in sql or "phone != ''" in sql

    def test_build_service_map_sorted(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 20, 'name': 'Manicure'},
            {'id': 47, 'name': 'Pedicure'},
        ]
        from services.data_import_helpers import build_service_map
        sl = build_service_map(mock_db.connection)
        assert sl == [(20, 'manicure'), (47, 'pedicure')]
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'ORDER BY id' in sql
```

#### 0.2: Run Tests

- [ ] `pytest tests/services/test_data_import_helpers.py -v`
- [ ] All fail (module doesn't exist)

> [!WARNING]
> The test for `test_substring_longest_wins` catches a real bug — naive substring matching with `'recepcja'` could match `'r'` if there's a 1-letter first name. The reference script sorts by `key=len, reverse=True`; preserve this exactly.

---

### Step 1: Create the Helpers Module

#### 1.1: Write the file

Create `services/data_import_helpers.py`. Structure (full content provided here so it's clear what to write):

```python
"""
Lookup builders, resolvers, and parsers for the caldis.pl import pipeline.

DB layer: PostgreSQL via psycopg2 + RealDictCursor (configured globally in
config.database). All queries use %s placeholders. Builders take a connection
and run a single SELECT each.

Resolvers and date/time parsers are pure functions — they accept the prebuilt
lookup maps and individual cell values, returning ids or normalised strings.
No DB access inside resolvers.

Mirrors the business rules of scripts/import_appointments_from_excel.py,
ported to PostgreSQL.
"""
import re
import logging
from datetime import datetime, date
from typing import Optional, Any

import pandas as pd
import psycopg2.extensions

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_SERVICE_ID: int = 20
"""Fallback service id when category lookup fails. Verified against production."""

KALENDARZ_OVERRIDES: dict[str, tuple[int, int]] = {
    "zrecepcja asia": (3, 24),  # Joanna Asia → Masaż klasyczny
}
"""Hand-curated Kalendarz → (employee_id, service_id) overrides."""


# ── Utility ──────────────────────────────────────────────────────────────────
def _is_blank(v: Any) -> bool:
    """Return True if v is None, NaN, empty string, or 'nan' literal."""
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    s = str(v).strip()
    return not s or s.lower() == 'nan'


# ── DB Lookup Builders ───────────────────────────────────────────────────────

def build_employee_map(conn: psycopg2.extensions.connection) -> dict:
    """Return {first_name_lower: employee_id} for fast Kalendarz matching."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name FROM employees")
    rows = cursor.fetchall()
    return {r['first_name'].strip().lower(): r['id'] for r in rows}


def build_client_map(conn: psycopg2.extensions.connection) -> dict:
    """Return {(first_name_lower, last_name_lower): client_id} with reversed-order fallback."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name, last_name FROM clients")
    rows = cursor.fetchall()
    result: dict = {}
    for r in rows:
        fn = (r['first_name'] or '').strip().lower()
        ln = (r['last_name'] or '').strip().lower()
        result[(fn, ln)] = r['id']
        if ln:
            result.setdefault((ln, fn), r['id'])
    return result


def build_phone_map(conn: psycopg2.extensions.connection) -> dict:
    """Return {normalized_phone: client_id} for phone-fallback resolution."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, phone FROM clients WHERE phone IS NOT NULL AND phone != ''"
    )
    rows = cursor.fetchall()
    return {r['phone'].strip(): r['id'] for r in rows}


def build_service_map(conn: psycopg2.extensions.connection) -> list:
    """Return [(service_id, name_lower), ...] sorted ascending by id."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM services ORDER BY id")
    rows = cursor.fetchall()
    return [(r['id'], r['name'].strip().lower()) for r in rows]


# ── Resolvers (pure) ─────────────────────────────────────────────────────────

def resolve_employee_id(kalendarz: Any, employee_map: dict) -> Optional[int]:
    """Match the 'Kalendarz' xlsx cell to an employee.id.

    Strategy:
      1. Exact case-insensitive match
      2. Longest-first substring match (avoids false positives like 'a' ⊂ 'kasia')
    Returns None if nothing matches.
    """
    if _is_blank(kalendarz):
        return None
    val = str(kalendarz).strip().lower()
    if val in employee_map:
        return employee_map[val]
    for first_name_lower in sorted(employee_map, key=len, reverse=True):
        if first_name_lower in val:
            return employee_map[first_name_lower]
    return None


def normalize_phone(raw_phone: Any) -> Optional[str]:
    """Normalize to '48XXXXXXXXX'.

    Handles: '504020116', ' 504 020 116', '+48504020116', '0048504020116'.
    Returns None if not a valid Polish mobile.
    """
    if _is_blank(raw_phone):
        return None
    phone = str(raw_phone).strip().replace(' ', '').replace('-', '')
    if phone.startswith('+48'):
        phone = phone[3:]
    elif phone.startswith('0048'):
        phone = phone[4:]
    elif phone.startswith('+'):
        phone = phone[1:]
    phone = re.sub(r'\D', '', phone)
    if len(phone) == 9:
        return f'48{phone}'
    if len(phone) == 11 and phone.startswith('48'):
        return phone
    return None


def _strip_prefix(full_name: str) -> str:
    """Remove 'p.' prefix from full name."""
    cleaned = re.sub(r'^\s*p\.\s*', '', full_name.strip(), flags=re.IGNORECASE)
    return cleaned.strip()


def _resolve_by_phone(phone_raw: Any, phone_map: Optional[dict]) -> Optional[int]:
    if phone_map is None:
        return None
    normalized = normalize_phone(phone_raw)
    if normalized is None:
        return None
    return phone_map.get(normalized)


def resolve_client_id(full_name_raw: Any, client_map: dict,
                       phone_raw: Any = None,
                       phone_map: Optional[dict] = None) -> Optional[int]:
    """Match 'Imie i nazwisko' xlsx cell to a client.id.

    Order: prefix-stripped exact → reversed order → first-name-only → phone.
    """
    if _is_blank(full_name_raw):
        return _resolve_by_phone(phone_raw, phone_map)
    cleaned = _strip_prefix(str(full_name_raw))
    if not cleaned or cleaned.lower() == 'wolne':
        return None
    parts = cleaned.split(None, 1)
    if not parts:
        return _resolve_by_phone(phone_raw, phone_map)
    fn = parts[0].lower()
    ln = parts[1].lower() if len(parts) > 1 else ''
    if (fn, ln) in client_map:
        return client_map[(fn, ln)]
    if ln and (ln, fn) in client_map:
        return client_map[(ln, fn)]
    if (fn, '') in client_map:
        return client_map[(fn, '')]
    if ln and (ln, '') in client_map:
        return client_map[(ln, '')]
    return _resolve_by_phone(phone_raw, phone_map)


def resolve_service_id(kategoria: Any, service_list: list) -> int:
    """Match the 'Kategoria' xlsx cell to a service.id.

    Order: exact → service name starts with kategoria → kategoria starts with
    service name → DEFAULT_SERVICE_ID.
    """
    if _is_blank(kategoria):
        return DEFAULT_SERVICE_ID
    kat = str(kategoria).strip().lower()
    for svc_id, svc_name in service_list:
        if svc_name == kat:
            return svc_id
    for svc_id, svc_name in service_list:
        if svc_name.startswith(kat):
            return svc_id
    for svc_id, svc_name in service_list:
        if kat.startswith(svc_name):
            return svc_id
    logger.warning(f"resolve_service_id: no match for kategoria={kategoria!r}, "
                   f"falling back to DEFAULT_SERVICE_ID={DEFAULT_SERVICE_ID}")
    return DEFAULT_SERVICE_ID


# ── Date / Time Helpers ──────────────────────────────────────────────────────

def parse_appointment_date(cell_value: Any) -> Optional[str]:
    """Return 'YYYY-MM-DD' from a date/datetime/string cell, or None."""
    if _is_blank(cell_value):
        return None
    if isinstance(cell_value, (datetime, date)):
        return cell_value.strftime('%Y-%m-%d')
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None


def parse_time(cell_value: Any) -> Optional[str]:
    """Return 'HH:MM:SS' from a datetime/string cell, or None."""
    if _is_blank(cell_value):
        return None
    if isinstance(cell_value, datetime):
        return cell_value.strftime('%H:%M:%S')
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime('%H:%M:%S')
    except Exception:
        return None


def parse_created_at(cell_value: Any) -> str:
    """Return 'YYYY-MM-DD HH:MM:SS'. Falls back to current time."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if _is_blank(cell_value):
        return now_str
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return now_str


def calc_duration_minutes(od_cell: Any, do_cell: Any) -> int:
    """Calculate duration in minutes from Od/Do cells. Returns 0 on parse failure."""
    try:
        start = pd.to_datetime(str(od_cell))
        end = pd.to_datetime(str(do_cell))
        return max(int((end - start).total_seconds() / 60), 0)
    except Exception:
        return 0
```

- [ ] Mirror the docstring style from `services/absence_service.py` (module-level + per-function)
- [ ] Type hints on every public function
- [ ] No `print()` — use `logger.warning` for the DEFAULT_SERVICE_ID fallback

---

### Step 2: Verify Tests Pass

- [ ] `pytest tests/services/test_data_import_helpers.py -v` — all pass
- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `services/data_import_helpers.py` exists with all 13 functions
- [ ] Every SQL query uses `%s` (verified by grep: `grep "?" services/data_import_helpers.py` returns no parameter `?`)
- [ ] Every public function has a type hint
- [ ] `DEFAULT_SERVICE_ID = 20` and `KALENDARZ_OVERRIDES` are module-level constants
- [ ] All tests in `tests/services/test_data_import_helpers.py` pass

**Quality Gates:**

- [ ] No `print()` statements
- [ ] No `sqlite3` import
- [ ] `pd.isna` calls localized to `_is_blank()`
- [ ] Logging via `logger`, not `print`

**Integration:**

- [ ] Phase 04 service imports every public function and uses them without errors

---

## Quality Assurance

### Test Plan

#### Manual Testing

- [ ] **Build + resolve cycle:** From a Python REPL with the app loaded:
  ```python
  from config.database import get_db_connection
  from services.data_import_helpers import build_employee_map, resolve_employee_id
  conn = get_db_connection()
  em = build_employee_map(conn)
  resolve_employee_id('zRecepcja Anna', em)
  ```
  - Expected: returns an int (matching employee id) or None.

- [ ] **Phone normalization edge cases:** Try `'504 020 116'`, `'+48 504 020 116'`, `'504-020-116'`, `'12'` (too short), `''`, `None`.
  - Expected: first three return `'48504020116'`; last three return `None`.

#### Automated Testing

```bash
pytest tests/services/test_data_import_helpers.py -v
pytest tests/                                     # full suite
```

### Review Checklist

- [ ] **Code Review Gate:**
  - [ ] Run `/code-review plans/260519-data-import-playwright/phase-03-postgres-lookup-builders.md` with files: `services/data_import_helpers.py`, `tests/services/test_data_import_helpers.py`
  - [ ] Read review at `plans/260519-data-import-playwright/reviews/code/phase-03.md`

- [ ] **Code Quality:**
  - [ ] All tests pass
  - [ ] Type hints on every public function

- [ ] **Security:**
  - [ ] No raw user input concatenation
  - [ ] All SQL parameterized (though it's all read-only and uses no user input directly — still %s)

- [ ] **Documentation:**
  - [ ] Docstring at module level explains relationship to the reference script
  - [ ] DEFAULT_SERVICE_ID comment explains the fallback rationale

- [ ] **Project Pattern Compliance:**
  - [ ] DB calls use `%s`, `RealDictCursor` rows accessed via `row['key']`
  - [ ] Logging follows project convention (`logger = logging.getLogger(__name__)`)

---

## Dependencies

### Upstream (Required Before Starting)

- **Phase 02** — not a hard dependency on functions, but the foundation group should be done first for stack cleanliness

### Downstream (Will Use This Phase)

- **Phase 04** — Import service imports every public function from this module

### External Services

- None.

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 03 — PostgreSQL lookup builders + parser helpers`

---

## Notes

### Technical Considerations

- `RealDictCursor` is set on the pool (`cursor_factory=psycopg2.extras.RealDictCursor` in `config/database.py:55`), so every cursor in the app returns dict-like rows. `row['id']` works; `row[0]` does not.
- `pandas` is already a project dependency (`requirements.txt` includes it for the existing import script). Using it for date parsing here keeps the parsing identical to the reference script — important for matching the existing behavior bit-for-bit.

### Known Limitations

- No fuzzy name matching. If a client name in caldis.pl has a typo, the import skips that row and surfaces it as `skipped_no_client` — admin must create the client manually.

### Future Enhancements

- Add a `resolve_client_id_fuzzy` variant using rapidfuzz for typo tolerance
- Cache the lookup maps in Redis for multi-worker deployments

---

**Previous:** [[phase-02-import-log-repository|Phase 02: Import Log Repository]]
**Next:** [[phase-04-import-service-core|Phase 04: Import Service — Core Pipeline]]
