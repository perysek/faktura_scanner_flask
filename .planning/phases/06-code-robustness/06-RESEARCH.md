# Phase 6: Code Robustness - Research

**Researched:** 2026-04-01
**Domain:** Python exception hierarchy, enum adoption, repository column projection, IMAP error handling
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Exception handling (IMPR-03):** Refactor ALL route handlers — `str(e)` leaks internal errors to clients; replace with `AppError` subclasses + generic user-facing messages. Reparent `AppointmentError` and `OCRExtractionError` to inherit from `AppError`. Use existing `ConflictError(AppError)` (HTTP 409) for appointment scheduling conflicts. Add `DatabaseConnectionError(AppError)` — catch connection failures in `BaseRepository._execute()` single catch point. Global error handler already works, routes just need to raise `AppError` subclasses.
- **Appointment Status Enum (IMPR-04):** `AppointmentStatus` exists in `config/appointment_statuses.py` — wire it into ALL production files (appointment_repository, analytics_repository, appointment_routes, appointment_service). Remove duplicate `VALID_TRANSITIONS` dict from `appointment_service.py`. Fix bug: `excluded_placeholders()` method referenced in docstring but not defined — remove the reference.
- **SELECT * Replacement (IMPR-05):** Override `BaseRepository._columns` in 4 critical repos ONLY: clients, employees, users, income_records. Other repos keep `SELECT *`. Use existing `_columns` mechanism.
- **EmailService Error Handling (FIX-03 expanded):** `disconnect()` is already correctly implemented. Extend scope: fix ALL EmailService error handling — replace bare `except:` in `_extract_email_body_text()`, replace `print()` with `logging` throughout all methods, replace broad `except Exception` in `connect()`, `fetch_pdf_attachments()`, `_process_email()`, `_save_attachment()`. Do NOT change return value patterns (False/[]/None).
- **SQL IN Clause & Credential Masking (IMPR-06):** SQL IN clause safety already resolved by `_in_clause()`. Redirect scope to email credential masking — ensure email passwords/tokens never appear in log output. Check `connect()` and error messages for credential leaks.

### Claude's Discretion

- Exact column lists for each critical repository (derived from schema/models)
- Error message wording for user-facing error responses (generic, non-leaking)
- Specific IMAP exception types to catch in each EmailService method
- Order of implementation across plans

### Deferred Ideas (OUT OF SCOPE)

- Refactoring remaining repos (beyond 4 critical) to use explicit column lists
- Adding structured logging (JSON format) across the application
- Error monitoring/alerting integration (Sentry, etc.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| IMPR-03 | Custom exception hierarchy — business logic errors vs infrastructure errors, routes catch specific types | `AppError` hierarchy in `exceptions.py` fully defined; `AppointmentError` and `OCRExtractionError` are bare `Exception` subclasses needing reparenting; 140 `except Exception as e` sites across 9 route files need migration |
| IMPR-04 | Appointment status values defined as Python enum with PostgreSQL CHECK constraint — replaces hardcoded strings | `AppointmentStatus` class fully defined but imported in zero production files; 8+ hardcoded strings in appointment_repository; 30+ in analytics_repository; duplicate `STATUS_TRANSITIONS` in appointment_service.py |
| IMPR-05 | `SELECT *` replaced with explicit column lists in critical repositories (clients, employees, users, income_records) | `BaseRepository._columns = '*'` override mechanism exists and works; column lists fully derivable from migrations and model dataclasses; UserRepository already has `_columns` set as proof of pattern |
| IMPR-06 | Safe SQL IN clause helper + email credential masking | `_in_clause()` already correct everywhere; email password masking needed in `connect()` error log |
| FIX-03 | EmailService bare `except: pass` replaced with specific IMAP exception handlers and logging | `disconnect()` already fixed; 3 bare `except:` blocks remain in `_extract_email_body_text()`; multiple `print()` calls in `connect()`, `fetch_pdf_attachments()`, `_process_email()`, `_save_attachment()` |
</phase_requirements>

---

## Summary

Phase 6 is a **wiring and adoption phase**, not a greenfield build. All major infrastructure already exists: the `AppError` hierarchy (`exceptions.py`), the `AppointmentStatus` class (`config/appointment_statuses.py`), and the `BaseRepository._columns` override mechanism (`base_repository.py:15-17`). The work is making production code use these assets.

The dominant effort is the exception refactor across 140 `except Exception as e` sites in 9 route files. Most of these are trivial replacements — the global `@app.errorhandler(AppError)` in `app.py:172` means routes can simply `raise NotFoundError(...)` and delete their own JSON error-building code entirely. This is net code reduction.

The status enum adoption touches 3 files intensively: `appointment_repository.py` (8+ sites), `analytics_repository.py` (30+ sites), `appointment_service.py` (1 duplicate dict to remove). The pattern is mechanical: import `AppointmentStatus` at module level, replace string literals with attribute references.

**Primary recommendation:** Implement in three sequential plans — Plan A (exceptions infrastructure + route migration), Plan B (enum adoption + SELECT * column projection), Plan C (EmailService cleanup + credential masking). This ordering ensures the exception types exist before they are raised/caught everywhere.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg2 | existing | PostgreSQL driver — `OperationalError`, `InterfaceError` are the DB exception types to catch | Already used throughout; these are the specific exceptions for `DatabaseConnectionError` |
| imaplib | stdlib | IMAP protocol — `IMAP4.error`, `IMAP4.abort`, `OSError` are the specific exceptions | Already imported in EmailService |
| logging | stdlib | Replace `print()` calls in EmailService | `logging` already imported in email_service.py; just not used in most methods |

### No New Dependencies
This phase requires zero new packages. All patterns use existing imports and project infrastructure.

---

## Architecture Patterns

### Pattern 1: Exception Hierarchy Extension

Add `DatabaseConnectionError` to `exceptions.py`:

```python
# Source: exceptions.py (verified — existing hierarchy)
class DatabaseConnectionError(AppError):
    """Database unreachable or connection failed — maps to HTTP 503."""
    status_code = 503
```

Reparent existing service exceptions:

```python
# services/appointment_service.py — BEFORE
class AppointmentError(Exception):
    pass

# AFTER (reparented — global handler now catches it)
from exceptions import AppError

class AppointmentError(AppError):
    status_code = 400
```

```python
# services/ocr_service.py — BEFORE
class OCRExtractionError(Exception):
    pass

# AFTER
from exceptions import AppError

class OCRExtractionError(AppError):
    status_code = 422
```

### Pattern 2: Route Handler Simplification

The global handler in `app.py:172-177` converts any `AppError` subclass to the right JSON automatically. Routes that currently do:

```python
# BEFORE — leaks internal error text, duplicates response building
try:
    result = do_something()
    return jsonify({'success': True, 'data': result})
except AppointmentError as e:
    return jsonify({'success': False, 'error': str(e)}), 400
except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
```

Should become:

```python
# AFTER — AppError subclasses bubble to global handler
@appointment_bp.route(...)
def create_appointment():
    data = request.get_json()
    if not data:
        raise ValidationError('Brak danych')
    result = do_something()   # raises AppointmentError (now AppError subclass) on failure
    return jsonify({'success': True, **result}), 201
```

**IMPORTANT:** The global handler only handles `/api/` paths with JSON. Non-API routes rendering HTML templates need their own try/except or a different error page. The handler is:
```python
# app.py:172-177 (verified)
@app.errorhandler(AppError)
def handle_app_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': str(e)}), e.status_code
    return render_template('errors/500.html'), e.status_code
```

**CRITICAL:** The 5 handlers in `appointment_routes.py` that already do `except AppointmentError as e: return jsonify(...), 400` must be updated alongside reparenting. After reparenting, these handlers become redundant because the global handler would fire. They should be deleted — not left as dead code.

### Pattern 3: AppointmentStatus Enum Adoption

Import at module level (not per-query) for readability:

```python
# At top of file
from config.appointment_statuses import AppointmentStatus

# In query
query = """
    WHERE a.status = %s
"""
cursor.execute(query, (AppointmentStatus.COMPLETED,))

# For IN clauses using existing _in_clause helper
clause, params = self._in_clause(list(AppointmentStatus.EXCLUDED_FROM_SCHEDULE))
query = f"WHERE status NOT IN {clause}"
cursor.execute(query, params)
```

For SQL strings that embed status literals (not parameterized), use f-string substitution:

```python
# analytics_repository.py pattern — status in COUNT(CASE WHEN ...) cannot be parameterized
query = f"""
    COUNT(CASE WHEN status = '{AppointmentStatus.COMPLETED}' THEN 1 END) AS completed,
    COUNT(CASE WHEN status = '{AppointmentStatus.CANCELLED}' THEN 1 END) AS cancelled,
    COUNT(CASE WHEN status = '{AppointmentStatus.NO_SHOW}' THEN 1 END) AS no_shows
"""
```

### Pattern 4: DatabaseConnectionError Catch Point

Catch psycopg2 connection errors at `BaseRepository._execute()` (single choke point):

```python
# base_repository.py
import psycopg2
from exceptions import DatabaseConnectionError

def _execute(self, query: str, params: tuple = ()) -> Any:
    try:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor
    except psycopg2.OperationalError as e:
        raise DatabaseConnectionError(f'Database unreachable: {type(e).__name__}') from e
    except psycopg2.InterfaceError as e:
        raise DatabaseConnectionError(f'Database connection lost: {type(e).__name__}') from e
```

Apply same pattern to `_fetch_one()`, `_fetch_all()`, and `_execute_insert()`.

**Note:** `EmployeeRepository`, `AppointmentRepository`, `IncomeRepository`, and `AnalyticsRepository` use `get_db_connection()` directly (not `BaseRepository` methods). They need separate `DatabaseConnectionError` wrapping at their own query points, or a shared helper.

### Pattern 5: SELECT * Column Projection

`UserRepository` already demonstrates the correct pattern (line 17):

```python
# repositories/users/user_repository.py (verified)
class UserRepository(BaseRepository):
    _columns = 'id, email, password_hash, full_name, role, is_active, last_login, created_at, updated_at'
```

The remaining three repos need this added. The `_columns` value is consumed by `get_by_id()` and `get_all()` in BaseRepository. Custom queries in the repo (e.g., `search()`, `find_by_email()`) use `SELECT *` directly — those are NOT changed by `_columns` override. Only `get_by_id()` and `get_all()` are affected.

### Anti-Patterns to Avoid

- **Catching and re-wrapping AppError:** Never `except AppError: raise AppError(...)` — this loses the original exception type and HTTP status.
- **Leaking stack traces to clients:** Never `str(e)` in JSON responses for production. Use generic messages; log the full exception server-side.
- **Parameterizing SQL keywords:** Status values in CASE/FILTER expressions cannot use `%s` placeholders — use f-string with enum attribute (safe since values come from our enum, not user input).
- **Changing EmailService return values:** `connect()` returns `bool`, `fetch_pdf_attachments()` returns `list`. Callers depend on these. Only change internal exception handling, not the return contract.
- **Removing the `except AppointmentError` handlers before reparenting:** The transition must be atomic — reparent the class AND update the route handlers in the same change.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP status code mapping | Custom status dict | `AppError.status_code` class attribute | Already in `exceptions.py`, global handler reads it |
| IMAP exception list | Catch-all `except Exception` | `imaplib.IMAP4.error`, `imaplib.IMAP4.abort`, `OSError` | These three cover all IMAP failure modes |
| Status string validation | Custom validator | `AppointmentStatus.FINAL`, `.ACTIVE`, `.EXCLUDED_FROM_SCHEDULE`, `.VALID_TRANSITIONS`, `.can_transition()` | All semantic groups and state machine already in `config/appointment_statuses.py` |
| Column list introspection | Reflection queries | Hardcoded `_columns` string | Stable schema, explicit is better than dynamic here |

---

## Common Pitfalls

### Pitfall 1: Forgetting Non-BaseRepository Repos
**What goes wrong:** `DatabaseConnectionError` is wired into `BaseRepository._execute()` but `AppointmentRepository`, `EmployeeRepository`, `IncomeRepository`, and `AnalyticsRepository` use `get_db_connection()` directly. Their queries remain unwrapped.
**Why it happens:** These repos were written before the BaseRepository pattern was fully established; they access `get_db_connection()` with context managers.
**How to avoid:** For Phase 6, apply `DatabaseConnectionError` wrapping to `BaseRepository` only (covers `ClientRepository`, `UserRepository`, `InvoiceRepository`, `AuditRepository`). Document that the other repos are out of scope for this pattern in Phase 6 — they're future Phase 9 work when connection management is refactored.

### Pitfall 2: Dead AppointmentError Handlers After Reparenting
**What goes wrong:** After making `AppointmentError` inherit from `AppError`, the 5 existing `except AppointmentError as e: return jsonify(...)` blocks in `appointment_routes.py` still execute — they just now catch an `AppError` subclass and build their own response instead of letting the global handler do it. This means two code paths produce the same result, but the explicit handler takes precedence.
**Why it happens:** Python exception handling is hierarchical. The explicit `except AppointmentError` fires before the global Flask handler.
**How to avoid:** Delete the explicit `except AppointmentError` blocks from `appointment_routes.py` after reparenting. Let the global handler produce consistent JSON.

### Pitfall 3: Status Strings Embedded in CASE Expressions
**What goes wrong:** Replacing `'completed'` with `AppointmentStatus.COMPLETED` in `COUNT(CASE WHEN status = %s THEN 1 END)` fails — CASE expression values in aggregation cannot be parameterized.
**Why it happens:** psycopg2 parameterization only works for WHERE clause values that are compared, not for inline string literals in CASE branches.
**How to avoid:** Use f-string substitution: `f"COUNT(CASE WHEN status = '{AppointmentStatus.COMPLETED}' THEN 1 END)"`. This is safe because the value comes from our own enum, not user input.

### Pitfall 4: Email Password in Logs
**What goes wrong:** `connect()` currently logs: `print(f"❌ Błąd połączenia: {e}")`. If the IMAP server echoes credentials in its error message (some do), the password appears in stdout.
**Why it happens:** IMAP error messages from `imaplib.IMAP4.error` sometimes include the server response which can contain the AUTH command with credentials.
**How to avoid:** Log only `type(e).__name__` and a generic description, not `str(e)`. The credential masking required by IMPR-06 applies here.

### Pitfall 5: `excluded_placeholders()` Ghost Reference
**What goes wrong:** The `AppointmentStatus` class docstring references `excluded_placeholders()` (line 9 of `config/appointment_statuses.py`) but no such method exists on the class. Any code that follows the docstring example will fail with `AttributeError`.
**Why it happens:** Method was planned but never implemented.
**How to avoid:** Remove the reference from the docstring. Use `_in_clause()` from `BaseRepository` for parameterized IN clauses with enum sets.

### Pitfall 6: 248/249 Tests Still Pass After Changes
**What goes wrong:** The existing `TestEmailServiceConnect.test_connect_failure_sets_connected_false` uses `Exception("Connection refused")` as the mock side effect. After changing `connect()` to catch specific exceptions only, this test still passes (broad `Exception` is still caught by `except Exception`). False confidence.
**Why it happens:** Tests mock at too broad a level.
**How to avoid:** Add new tests that mock `imaplib.IMAP4.error` and `OSError` specifically to verify the specific catch branches work.

---

## Code Examples

### Verified Column Lists (from migrations + models)

```python
# clients — from migration ee7039bc78b2 + soft-delete migration e9f0a1b2c3d4
_columns = (
    'id, first_name, last_name, phone, email, date_of_birth, '
    'notes, preferences, first_visit_date, last_visit_date, '
    'is_active, is_deleted, deleted_at, created_at, updated_at'
)

# employees — from migration 001 + ba16fcdbb066 (employer_cost_rate)
# NOTE: no is_deleted column — soft delete not applied to employees table
_columns = (
    'id, user_id, forma_zatrudnienia_id, first_name, last_name, phone, email, '
    'position, employment_status, hire_date, termination_date, '
    'base_salary, commission_rate, employer_cost_rate, '
    'skills, specializations, work_schedule, max_appointments_per_day, '
    'notes, photo_path, is_active, created_at, updated_at'
)

# users — already set (verified line 17 of user_repository.py)
_columns = 'id, email, password_hash, full_name, role, is_active, last_login, created_at, updated_at'

# income_records — from migration 0c648f58079b
_columns = (
    'id, appointment_id, client_id, employee_id, '
    'total_amount, discount_amount, net_amount, commission_total, '
    'payment_method, payment_date, notes, created_at'
)
```

### AppointmentStatus — Correct Usage for ALLOWED_FINAL_STATUSES

```python
# appointment_routes.py — replace local list with enum group
# BEFORE (line 749):
ALLOWED_FINAL_STATUSES = ['completed', 'cancelled', 'no_show']
if new_status not in ALLOWED_FINAL_STATUSES:

# AFTER:
from config.appointment_statuses import AppointmentStatus
if new_status not in AppointmentStatus.FINAL:
```

### EmailService — Specific Exception Handling Pattern

```python
# services/email_service.py — connect() pattern
import logging
import imaplib

def connect(self, email_address: str, password: str, imap_server: str, imap_port: int) -> bool:
    try:
        self.imap = imaplib.IMAP4_SSL(imap_server, imap_port)
        self.imap.login(email_address, password)
        self.connected = True
        logging.info("Connected to %s as %s", imap_server, email_address)
        return True
    except imaplib.IMAP4.error as e:
        # Masks credentials: log type only, not str(e) which may include server response
        logging.error("IMAP login failed for %s: %s", imap_server, type(e).__name__)
        self.connected = False
        return False
    except OSError as e:
        logging.error("Cannot reach %s: %s", imap_server, type(e).__name__)
        self.connected = False
        return False
```

```python
# _extract_email_body_text — replace bare except: with specific
@staticmethod
def _extract_email_body_text(message) -> str:
    body_text = ''
    try:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text += payload.decode('utf-8', errors='ignore')
                    except (UnicodeDecodeError, LookupError) as e:
                        logging.debug("Failed to decode email part: %s", type(e).__name__)
        else:
            try:
                payload = message.get_payload(decode=True)
                if payload:
                    body_text = payload.decode('utf-8', errors='ignore')
            except (UnicodeDecodeError, LookupError) as e:
                logging.debug("Failed to decode email body: %s", type(e).__name__)
    except AttributeError as e:
        logging.debug("Malformed email message: %s", type(e).__name__)
    return body_text
```

### export_service.py Bare Except (Bonus Fix)

```python
# services/export_service.py:79 — bare except: in column width calculation
# BEFORE:
try:
    if len(str(cell.value)) > max_length:
        max_length = len(cell.value)
except:
    pass

# AFTER (correct logic — original had a bug: len(str(...)) vs len(cell.value)):
try:
    if cell.value is not None and len(str(cell.value)) > max_length:
        max_length = len(str(cell.value))
except TypeError:
    pass
```

---

## Key Findings: Exact Scope Per File

### Files Requiring Changes

| File | What Changes | Scope |
|------|-------------|-------|
| `exceptions.py` | Add `DatabaseConnectionError(AppError)` | 5 lines |
| `services/appointment_service.py` | Reparent `AppointmentError` to `AppError`; remove `STATUS_TRANSITIONS` dict | ~10 lines changed |
| `services/ocr_service.py` | Reparent `OCRExtractionError` to `AppError` | 2 lines |
| `repositories/base_repository.py` | Wrap `_execute()`, `_fetch_one()`, `_fetch_all()`, `_execute_insert()` with `DatabaseConnectionError` | ~20 lines |
| `repositories/clients/client_repository.py` | Add `_columns` class attribute | 1 line |
| `repositories/employees/employee_repository.py` | Add `_columns` class attribute; note: does NOT extend BaseRepository currently | see note below |
| `repositories/appointments/income_repository.py` | Add `_columns` if extended to BaseRepository; currently standalone | see note below |
| `config/appointment_statuses.py` | Remove `excluded_placeholders()` docstring reference | 2 lines |
| `routes/appointment_routes.py` | Import `AppointmentStatus`; replace hardcoded status checks; delete redundant `except AppointmentError` handlers; replace 20 `except Exception` sites | major |
| `routes/api_routes.py` | Replace 81 `except Exception as e: return jsonify({'error': str(e)})` sites | major |
| `routes/employee_service_routes.py` | Replace 7 `except Exception` sites | moderate |
| `routes/income_routes.py` | Replace 3 `except Exception` sites | minor |
| `routes/client_preference_routes.py` | Replace 5 `except Exception` sites | minor |
| `routes/service_addon_routes.py` | Replace 6 `except Exception` sites | minor |
| `routes/upload_routes.py` | Replace 13 `except Exception` sites | moderate |
| `routes/roles/routes.py` | Replace 2 `except Exception` sites | minor |
| `routes/users/routes.py` | Replace 3 `except Exception` sites | minor |
| `repositories/appointments/appointment_repository.py` | Replace 8+ hardcoded status strings | moderate |
| `repositories/analytics/analytics_repository.py` | Replace 30+ hardcoded status strings | moderate |
| `services/email_service.py` | Replace 3 bare `except:`, replace all `print()` with `logging`, mask credentials | moderate |
| `services/export_service.py` | Fix bare `except:` at line 79 | minor (bonus) |

**Critical architectural note on employees and income_records:** `EmployeeRepository` and `IncomeRepository` do NOT extend `BaseRepository`. They use `get_db_connection()` directly. The `_columns` override mechanism only works for repos that inherit `BaseRepository`. For Phase 6, the IMPR-05 requirement is "override `_columns` in 4 critical repos" — this is straightforward for `ClientRepository` and `UserRepository` (both extend `BaseRepository`). For `EmployeeRepository` and `IncomeRepository`, the planner must decide: either extend `BaseRepository` (larger change) or apply `_columns`-equivalent manually to their `get_by_id()` and `get_all()` queries. Recommendation: add `BaseRepository` inheritance to both repos as part of this task, since the migration is clean and the benefit is significant.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `except Exception as e: return jsonify({'error': str(e)})` | `raise AppError_subclass(...)` + global handler | Phase 6 | Routes become ~30% shorter; consistent error format; no more leaking |
| Hardcoded `'completed'`, `'cancelled'`, `'no_show'` strings | `AppointmentStatus.COMPLETED` etc. | Phase 6 | Single definition, grep-safe, typo-proof |
| `SELECT *` in `get_by_id()`, `get_all()` | Explicit column list via `_columns` | Phase 6 | Protects against schema drift, prevents accidental exposure of new columns |
| `print()` in EmailService | `logging.info/error/debug()` | Phase 6 | Output goes to app logger, level-controlled, suppressible in production |

**Already done (do not re-implement):**
- `disconnect()` specific exception handling — verified correct at lines 85-88 of `email_service.py`
- `_in_clause()` parameterized IN helper — verified in use at `base_repository.py:81-90`
- Global `@app.errorhandler(AppError)` — verified working at `app.py:172`
- `UserRepository._columns` — already set at `user_repository.py:17`
- `AppointmentStatus` class — fully defined at `config/appointment_statuses.py`

---

## Open Questions

1. **Should `EmployeeRepository` and `IncomeRepository` extend `BaseRepository`?**
   - What we know: They currently use `get_db_connection()` directly with context managers; `BaseRepository` uses `DatabaseConnection.get_connection()` which is the same connection but accessed differently.
   - What's unclear: Whether adding `BaseRepository` inheritance would break their `with get_db_connection() as conn:` patterns since `BaseRepository` does not use context managers.
   - Recommendation: Extend both repos to `BaseRepository` and remove the `with get_db_connection()` patterns — they already auto-commit in `_execute()`. This is clean and unifies connection management. If the planner considers this out of scope for Phase 6, apply `_columns` logic manually to `get_by_id()` and `get_all()` in each file instead.

2. **Which IMAP exception types for `_process_email()` and `fetch_pdf_attachments()`?**
   - What we know: The inner per-folder `except Exception as e: continue` in `fetch_pdf_attachments()` serves a legitimate purpose — one bad folder should not abort the entire scan.
   - What's unclear: Whether to narrow to `(imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError)` or keep broad here for defensive resilience.
   - Recommendation: Narrow to the three IMAP types + log with `logging.warning()`. A truly unexpected exception (e.g., memory error) should not be silently swallowed by continuing to the next folder.

3. **Route handler error message wording**
   - What we know: `str(e)` currently leaks internal error details (DB query fragments, Python exceptions) to clients.
   - Recommendation: Use Polish user-facing messages matching existing UI tone. Examples: `'Wystąpił błąd serwera'` (500), `'Zasób nie istnieje'` (404), `'Brak uprawnień'` (403), `'Nieprawidłowe dane'` (400). Keep specific messages for business logic errors (e.g., appointment conflict messages from `AppointmentError` are already user-facing Polish text).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (9.0.2 — verified from test cache filenames) |
| Config file | none — runs with `pytest tests/` from project root |
| Quick run command | `python -m pytest tests/services/test_email_service.py tests/repositories/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IMPR-03 | `AppointmentError` is now an `AppError` subclass; global handler catches it | unit | `pytest tests/services/test_appointment_service.py -x -q` | ❌ Wave 0 |
| IMPR-03 | `DatabaseConnectionError` raised on psycopg2.OperationalError in `_execute()` | unit | `pytest tests/repositories/test_base_repository.py -x -q` | ❌ Wave 0 |
| IMPR-03 | Route handler returns generic message, not `str(e)` on unhandled exception | unit | `pytest tests/routes/test_api_routes.py -x -q` | ✅ exists (partial) |
| IMPR-04 | `AppointmentStatus.COMPLETED` used in appointment_repository queries | unit | `pytest tests/repositories/test_appointment_repository.py -x -q` | ❌ Wave 0 |
| IMPR-04 | `AppointmentStatus.FINAL` used in appointment_routes status validation | unit | `pytest tests/routes/test_appointment_routes.py -x -q` | ❌ Wave 0 |
| IMPR-05 | `ClientRepository.get_by_id()` does not include unspecified columns | unit | `pytest tests/repositories/test_client_repository.py -x -q` | ❌ Wave 0 |
| IMPR-06 | Email password not present in log output when `connect()` fails | unit | `pytest tests/services/test_email_service.py::TestEmailServiceConnect -x -q` | ✅ exists |
| FIX-03 | `_extract_email_body_text()` does not raise on malformed email | unit | `pytest tests/services/test_email_service.py -x -q` | ✅ exists (partial) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/services/test_email_service.py tests/repositories/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green (248 passing + new tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/services/test_appointment_service.py` — covers IMPR-03 exception reparenting
- [ ] `tests/repositories/test_base_repository.py` — covers IMPR-03 `DatabaseConnectionError`
- [ ] `tests/repositories/test_appointment_repository.py` — covers IMPR-04 enum usage
- [ ] `tests/routes/test_appointment_routes.py` — covers IMPR-04 route status validation
- [ ] `tests/repositories/test_client_repository.py` — covers IMPR-05 column projection
- [ ] `tests/services/test_email_service.py` — extend with credential masking tests (file exists, needs new test methods)

**Baseline:** 249 tests collected, 248 passing, 1 failing (pre-existing `test_iban_inny_kraj_nie_pl` — unrelated to Phase 6).

---

## Sources

### Primary (HIGH confidence)
- `exceptions.py` — `AppError` hierarchy verified in full; 5 subclasses, HTTP status codes, global handler wired
- `config/appointment_statuses.py` — `AppointmentStatus` class verified complete; FINAL, ACTIVE, EXCLUDED_FROM_SCHEDULE sets; `VALID_TRANSITIONS` dict; `can_transition()` method
- `repositories/base_repository.py` — `_columns = '*'` override mechanism verified at line 17; used in `get_by_id()` line 95, `get_all()` line 101
- `repositories/users/user_repository.py:17` — proof that `_columns` override works in production
- `services/email_service.py` — full file verified; `disconnect()` already correct; 3 bare `except:` blocks in `_extract_email_body_text()`; all `print()` locations identified
- `app.py:172-177` — global `@app.errorhandler(AppError)` verified; API-path check confirmed
- `alembic/versions/*.py` — column schemas for clients, employees, income_records verified from migration files
- `tests/conftest.py` — test fixture patterns verified; 249 tests, baseline 248 passing

### Secondary (MEDIUM confidence)
- `routes/appointment_routes.py` — 20 `except Exception` sites counted via grep; 5 `except AppointmentError` blocks confirmed at lines 168, 373, 411, 439, 484; `ALLOWED_FINAL_STATUSES` local list at line 749 confirmed
- `routes/api_routes.py` — 81 `except Exception` sites (largest single file); all return `jsonify({'success': False, 'error': str(e)})` pattern
- `repositories/analytics/analytics_repository.py` — 30+ hardcoded status string sites confirmed via grep
- `repositories/appointments/appointment_repository.py` — 8+ hardcoded status strings in WHERE/AND clauses confirmed

### Tertiary (LOW confidence)
- `imaplib` IMAP exception coverage — based on Python stdlib knowledge and existing pattern in `disconnect()`. The three types (`IMAP4.error`, `IMAP4.abort`, `OSError`) match what `disconnect()` already catches, which provides code-level validation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all patterns verified in existing code
- Architecture: HIGH — all patterns verified with working examples in codebase
- Column lists: HIGH — derived from Alembic migrations (authoritative schema source)
- Pitfalls: HIGH — most derived from direct code reading, not speculation
- Exception type coverage for EmailService: MEDIUM — IMAP4.error/abort/OSError are correct but coverage of all possible failure modes is best-effort without live IMAP testing

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable schema; no fast-moving dependencies)
