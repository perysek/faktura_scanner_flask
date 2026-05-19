---
title: "Caldis.pl Playwright Import — Master Plan"
description: "Integrate the existing scripts/import_appointments_playwright.py into the Flask web app as a first-class, PostgreSQL-backed, SSE-streamed import feature with admin-only access."
status: pending
priority: P1
tags: [import, playwright, postgresql, sse, background-task, admin-only]
created: 2026-05-19
updated: 2026-05-19
---

# Caldis.pl Playwright Import — Master Plan

## Executive Summary

**The Mission:** Move the standalone `scripts/import_appointments_playwright.py` workflow into the Flask app so admins can trigger imports from the browser, watch live progress over SSE, and audit past runs — all backed by PostgreSQL.

**The Big Shift:** The reference script targets **SQLite** (`sqlite3`, `?` placeholders, `conn.execute()`) and runs from the CLI. This feature replaces every DB call with the project's **PostgreSQL** stack (`psycopg2`, `%s` placeholders, `RealDictCursor`, `get_db_connection()`, `safe_commit()`) and wraps the entire pipeline in a background thread with SSE progress streaming and an `import_logs` audit trail.

> [!NOTE]
> The Playwright download logic in the reference script is fundamentally correct and reused. Only the DB layer, execution model, and user-facing surface change.

**Primary Deliverables:**

1. **Foundation:** `import_logs` table + repository + `data_import` module permission (superuser + admin only).
2. **Import Engine:** PostgreSQL-adapted lookup builders, xlsx parser, appointment + income_records inserter — same business rules as the SQLite script, but using the project's repositories and connection pool.
3. **Background Runner + SSE:** Thread-based task manager that runs the Playwright download and import outside the request/response cycle, pushing structured progress events to an in-memory queue per import_id; SSE endpoint relays them to the browser.
4. **HTTP Layer:** `routes/import_routes.py` blueprint exposing `/import` page, `POST /api/import/start`, `GET /api/import/<id>/stream`, `GET /api/import/<id>/status`, `POST /api/import/reconnect-session`, `GET /api/import/session-status`, `GET /api/import/history`.
5. **UI:** `templates/data_import/index.html` with date pickers, dry-run toggle, session status badge, reconnect button, live SSE log panel, result summary card, and a last-20-imports history table — plus a sidebar nav link gated on `user_permissions.data_import`.

---

## Phasing Strategy (Roadmap)

We follow a **Bottom-Up Stack** strategy: schema → repository → engine → background runner → HTTP → UI. Each layer is fully tested before the layer above is built. This matches the codebase's repository-first convention and the validator pipeline's expectation that DB migrations land first.

### Phase Constraints

- **Size:** 10–15 KB max per phase document
- **Scope:** Single implementation session target (~2–3 hours)
- **Dependencies:** Declared explicitly in each phase's frontmatter `dependencies` array
- **Review gate:** Code review via `code-review` skill before marking DONE; group-level audit after the last phase of each group

### Phase File Naming

- Pattern: `phase-NN-descriptive-slug.md`
- Examples: `phase-01-import-logs-migration.md`, `phase-05-sse-streaming.md`
- Flat sequential numbering — no sub-phases

### Phase Table

| Phase  | Title | Group | Focus | Status |
| :----- | :--------------------------------- | :----------------- | :----------------- | :-------- |
| **01** | [Import Logs Migration + Module Permission](./phase-01-import-logs-migration.md) | foundation | DB schema + RBAC seed | Pending |
| **02** | [Import Log Repository](./phase-02-import-log-repository.md) | foundation | CRUD + status transitions | Pending |
| **03** | [PostgreSQL Lookup Builders + Parser Helpers](./phase-03-postgres-lookup-builders.md) | import-engine | Port build_*_map + resolvers to psycopg2 | Pending |
| **04** | [Import Service — Core Pipeline](./phase-04-import-service-core.md) | import-engine | Orchestration + xlsx parsing + appointment insertion | Pending |
| **05** | [Background Runner + Progress Queue](./phase-05-background-runner.md) | background-task | Thread manager + progress event queue | Pending |
| **06** | [SSE Progress Stream + Status Endpoint](./phase-06-sse-progress-stream.md) | background-task | Live log + polling endpoints | Pending |
| **07** | [Session Management Endpoints](./phase-07-session-management.md) | http-layer | Reconnect (headed) + session-status | Pending |
| **08** | [Start Import + History Endpoints](./phase-08-import-routes.md) | http-layer | POST /start + GET /history + page route | Pending |
| **09** | [Import Page Template + Sidebar Link](./phase-09-import-template.md) | ui | Jinja template + sidebar nav entry | Pending |
| **10** | [Frontend JS — SSE Client + UI Wiring](./phase-10-frontend-js.md) | ui | Live log, status polling, history rendering | Pending |

### Group Summary

| Group | Phases | Description |
|-------|--------|-------------|
| foundation | P01–P02 | Database migration for `import_logs`, `data_import` module permission seed, repository for log CRUD |
| import-engine | P03–P04 | PostgreSQL-adapted lookup builders, xlsx parser, and the orchestration service that runs the pipeline |
| background-task | P05–P06 | Thread-based runner with per-import progress queue, SSE stream + status polling endpoints |
| http-layer | P07–P08 | Blueprint routes for starting imports, session reconnect, history, and page rendering |
| ui | P09–P10 | Jinja template, sidebar nav link, and frontend JavaScript wiring (SSE client, status display) |

**Group ordering:** foundation → import-engine → background-task → http-layer → ui. Dependencies flow top-to-bottom.

---

## Architectural North Star

**Purpose:** Define the immutable patterns every phase must follow.

### 1. PostgreSQL First, Always

- **Core Principle:** No `sqlite3`, no `?` placeholders, no `conn.execute()` shortcuts. The Flask app is PostgreSQL.
- **Enforcement:** All DB code uses `from config.database import get_db_connection, safe_commit`. SQL placeholders are `%s`. Cursors return `RealDictCursor` rows (already configured in the pool). Every repository inherits `BaseRepository` and uses `_execute`, `_fetch_one`, `_fetch_all`, `_execute_insert` where possible.

### 2. Repository Pattern Strictly Enforced

- **Core Principle:** Routes and services never touch SQL directly. Lookups against `clients`, `employees`, `services` go through their respective repositories — even when building bulk lookup maps.
- **Enforcement:** `services/data_import_service.py` calls into `ClientRepository`, `EmployeeRepository`, `ServiceRepository` (and `AppointmentRepository`, `IncomeRecordRepository` for inserts). New methods are added to these repositories if needed; no ad-hoc SQL in the service layer.

### 3. Background Work Stays Out of the Request Cycle

- **Core Principle:** A Playwright download + xlsx parse can take 30–120s. Holding a request thread that long blocks the worker pool and triggers proxy timeouts (Vultr nginx, Waitress on Windows).
- **Enforcement:** `POST /api/import/start` returns `{import_id}` immediately. A `threading.Thread` runs the pipeline. Progress events are pushed to a per-import `queue.Queue` and a status row in `import_logs`. SSE endpoint consumes the queue; polling endpoint reads the row.

### 4. SSE Mirrors the Existing `appointment_events` Pattern

- **Core Principle:** The codebase already has one working SSE endpoint (`routes/appointment_routes.py:244`). New SSE code must use the same shape: `stream_with_context`, `Response(generate(), mimetype='text/event-stream')`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`, periodic heartbeats (`": hb\n\n"`).
- **Enforcement:** SSE generator is structurally identical to `appointment_events`; only the data source (queue vs. row poll) differs.

### 5. Auth Decorators — No Exceptions

- **Core Principle:** Every import route is gated by `@login_required` + `@module_permission_required('data_import')`. The `data_import` module is restricted to `superuser` and `admin` in `MODULE_PERMISSIONS` and seeded in `role_permissions`.
- **Enforcement:** Mirror the SMS routes pattern — decorators on every endpoint, no per-handler auth checks. Sidebar link is gated on `user_permissions.data_import`.

### 6. Session File is a Server-Owned Secret

- **Core Principle:** `assets/temp/caldis_session.json` contains live caldis.pl auth cookies. It must never be served to clients, never logged, and never returned by an API endpoint.
- **Enforcement:** Only the server reads/writes the file. The `/api/import/session-status` endpoint returns `{status: "active"|"expired"|"missing"}` — never the file contents. Reconnect launches a **server-side headed browser** on the host machine (works on the local dev box / Windows Server; on Vultr headless mode this endpoint must surface a clear error — see Phase 07 Decision Log).

### 7. Errors Use the Project Exception Hierarchy

- **Core Principle:** No raw `Exception` raises in routes/services. Use `AppError`, `ValidationError`, `NotFoundError`, `ConflictError` from `exceptions.py`. The Flask error handler converts these to JSON for `/api/*`.
- **Enforcement:** Every route wraps user-facing logic in `try/except` and re-raises `AppError` subclasses. Unexpected errors are logged with `logging.exception(...)` before raising a generic `AppError`.

---

## Project Framework Alignment

This project is **Flask + Jinja2 + PostgreSQL (psycopg2 pool) + TailwindCSS + vanilla JS** with a strict repository/service split. Deviating from these patterns produces inconsistent code that's hard to maintain.

### Component Usage Priority

1. **First:** Existing repositories (`AppointmentRepository`, `ClientRepository`, etc.) and services (`AppointmentBusinessService`)
2. **Second:** New repositories under `repositories/<domain>/` that inherit `BaseRepository`
3. **Third:** Direct SQL via `get_db_connection()` + `safe_commit()` — only when the operation doesn't fit a repository (e.g. a JOIN across many tables for a one-off lookup builder)

### Required Utilities

| Task | Pattern |
|------|---------|
| Flask route | `Blueprint` + `@login_required` + `@module_permission_required('data_import')` + try/except + `jsonify` |
| DB connection | `from config.database import get_db_connection, safe_commit` |
| Repository | Inherit `repositories.base_repository.BaseRepository` |
| SSE | `stream_with_context` + `Response(..., mimetype='text/event-stream')` (see `appointment_events`) |
| Exceptions | `from exceptions import AppError, ValidationError, NotFoundError, ConflictError` |
| Auth | `@login_required` + `@module_permission_required('data_import')` |
| Templates | `{% extends "base.html" %}` + permission-gated sidebar link |
| Migrations | Alembic `op.create_table`/`op.execute` — see `alembic/versions/n8o9p0q1r2s3_*.py` |
| Logging | `import logging; logger = logging.getLogger(__name__)`; use `logger.exception()` for unexpected errors |

---

## Global Decision Log (Project ADRs)

### Background Execution Model (ADR-G-01)

**Status:** Accepted

**Context:** The Playwright download (10–60s) plus xlsx parse + DB inserts (5–30s) cannot run inside a normal Flask request. Options considered: (a) Celery, (b) RQ, (c) APScheduler, (d) raw `threading.Thread`.

**Decision:** Use **raw `threading.Thread`** with an in-process `dict[int, queue.Queue]` registry keyed by `import_id`. The app already runs a scheduler thread (`scheduler.py`) for SMS — this matches the existing concurrency model. No new infrastructure required.

**Consequences:**
- **Positive:** Zero new infra; simple to deploy on both Vultr (Linux/gunicorn) and Windows Server (Waitress); same approach as the existing scheduler.
- **Negative:** Imports are not durable across restarts — a server restart mid-import marks the row as orphaned (status remains `running`). Mitigation: Phase 02 includes a startup cleanup that flips orphaned `running` rows to `failed`.
- **Neutral:** With Waitress / gunicorn workers, one worker holds the thread; the in-memory queue is process-local. For now, the app runs as a single process per host — this is fine. If we ever scale to multiple workers, swap the queue for Redis pub/sub.

**Alternatives Considered:**
1. Celery: rejected — too much infra (broker + worker) for a single admin feature.
2. RQ: rejected — same reason; also adds Redis dependency.
3. APScheduler-only: rejected — APScheduler is for cron-style jobs, not one-shot user-triggered tasks.

### Playwright Session Persistence (ADR-G-02)

**Status:** Accepted

**Context:** caldis.pl uses reCAPTCHA v3, which blocks all programmatic login attempts. The reference script handles this by saving the post-login storage state to `assets/temp/caldis_session.json` and reusing it on subsequent runs. We must preserve this.

**Decision:** Keep the session file at `assets/temp/caldis_session.json` (already in `.gitignore` because `assets/temp/` is). The reconnect endpoint launches Playwright in **headed mode** on the **server's** host machine, the admin completes login in that visible browser window, and the resulting storage_state is written to the session file.

**Consequences:**
- **Positive:** Works perfectly for local dev and Windows Server (where the server is on a console the admin can access).
- **Negative:** Headed mode is impossible on a true headless Linux box (no display server). On Vultr, the reconnect endpoint returns a 503 with a clear message: "Headless server — run `python scripts/import_appointments_playwright.py --headed` once on a machine with a display, then upload `assets/temp/caldis_session.json` to the server." This is acceptable because the production deploy is currently Windows Server (per `DEPLOYMENT_WINDOWS_SERVER.md`).
- **Neutral:** Session expires every ~30 days based on caldis.pl cookie lifetime. The UI surfaces this clearly.

**Alternatives Considered:**
1. Solve reCAPTCHA with a paid service: rejected — cost + ToS concerns.
2. Store credentials and auto-login each run: rejected — reCAPTCHA blocks it; also stores plaintext password.

### Duplicate Detection Strategy (ADR-G-03)

**Status:** Accepted

**Context:** The reference script dedupes by `(employee_id, appointment_date, start_time)`. This is a business rule, not a DB constraint.

**Decision:** Keep the same dedupe key. Phase 04 implements it as a `SELECT 1` query before insert (same as the reference script), not as a DB unique index — the production `appointments` table already has manually-created same-key rows for blocked/recurring time, and a unique index would break existing data.

**Consequences:**
- **Positive:** Zero risk to existing data; matches the reference script exactly.
- **Negative:** A race condition exists if two import runs overlap. Mitigation: Phase 05 prevents two imports from running concurrently per server (queue check before starting a new thread).

---

## Security Requirements

This codebase doesn't use Supabase RLS — it uses **Flask-Login + role-based decorators**. Security patterns adapted accordingly.

### Authorization

- Every route in `routes/import_routes.py` carries `@login_required` + `@module_permission_required('data_import')`.
- `data_import` is added to both `MODULE_PERMISSIONS` in `config/auth_config.py` (static fallback) AND the `role_permissions` table (dynamic source of truth) — only `superuser` and `admin` get `has_access=TRUE`.
- The migration in Phase 01 seeds `role_permissions` with the same `ON CONFLICT DO NOTHING` pattern as `b0c1d2e3f4a5_add_data_correction_module.py`.

### Input Validation

- Date range inputs (`date_start`, `date_end`) are parsed with `datetime.strptime(..., '%Y-%m-%d').date()` and validated: `date_start <= date_end`, neither in the future beyond 1 day.
- `import_id` path params: typed as `<int:import_id>` in Flask routes — Flask raises 404 on non-int.
- Dry-run flag: cast to bool from the request JSON.
- Any user-supplied text never reaches SQL except via `%s` parameter binding.

### Secret Management

- `assets/temp/caldis_session.json` is server-only — never returned by any endpoint, never logged.
- No `CALDIS_EMAIL` / `CALDIS_PASSWORD` is required for the in-app flow (we only use session reuse). The credentials env vars stay as documentation for the CLI script path.
- All logging redacts paths inside `assets/temp/`.

### Error Handling

- Routes catch `AppError` subclasses and let the global handler in `app.py` format them.
- Unexpected errors are logged with `logging.exception()` before raising a generic `AppError('Wystapil blad serwera')`.
- Error messages returned to the browser never contain stack traces, internal paths, or DB error details.

### RBAC Audit Trail

- Every successful import writes a row to `import_logs` with `triggered_by_user_id` set to `current_user.id`. The history endpoint joins this against `users` to display who triggered which import.

---

## Implementation Standards

### Global Test Strategy

- **Unit:** Each new repository method has at least one mock-DB test in `tests/repositories/data_import/`. Each new service method has a mock-DB test in `tests/services/`. Both follow the existing `mock_db` fixture pattern in `tests/conftest.py`.
- **Integration:** One end-to-end test seeds a small xlsx file (fixture), runs the import in dry-run mode against a mocked Playwright download, asserts the parsed stats match expectations, and verifies no rows hit the DB.
- **Manual QA:** Admin runs a real headed reconnect against caldis.pl staging or production, then triggers a real import for a small date range and watches the SSE stream.

### Global Documentation Standard

After each phase:
1. Update `CLAUDE.md` if a new command, env var, or runtime pattern was added.
2. Update the module permission table in `MEMORY.md` if `data_import` permissions change.
3. The final phase adds a short section to `README.md` (or creates one) explaining the import workflow.

---

## Success Metrics & Quality Gates

### Project Success Metrics

- An admin can import 100 appointments from caldis.pl in under 90 seconds end-to-end (90% of the time is the Playwright download).
- The SSE log shows progress lines as they happen, no buffering delay > 2s.
- The history table accurately reflects every import attempt, including failures.
- Zero duplicate appointments inserted across multiple runs of the same date range.
- Zero permission bypasses: non-admin users can't reach `/import`, `/api/import/*`, or see the sidebar link.

### Global Quality Gates (Pre-Release)

- [ ] All `pytest tests/` pass
- [ ] No `print()` statements in `routes/`, `services/`, `repositories/` (use `logger.info/warning/error/exception`)
- [ ] Migration tested up + down on a copy of production
- [ ] `MODULE_PERMISSIONS['data_import']` matches `role_permissions` table contents
- [ ] Sidebar link only renders when `user_permissions.data_import` is truthy
- [ ] No `sqlite3` imports anywhere outside `scripts/`

---

## Resources & References

- **Reference script:** `scripts/import_appointments_playwright.py` — the full source of truth for the download + parse + insert logic (SQLite version)
- **PostgreSQL DB module:** `config/database.py` — pool, `get_db_connection`, `safe_commit`, `managed_transaction`
- **Auth config:** `config/auth_config.py` — `MODULE_PERMISSIONS`, `module_permission_required`
- **Existing SSE example:** `routes/appointment_routes.py:244–275` — the `appointment_events` endpoint
- **Repository base class:** `repositories/base_repository.py`
- **Existing repository example:** `repositories/appointments/appointment_repository.py`
- **Existing scheduler (concurrency model precedent):** `scheduler.py` (auto-started in `app.py:272`)
- **Existing migration format:** `alembic/versions/n8o9p0q1r2s3_create_absence_management_tables.py`
- **Existing module permission seed migration:** `alembic/versions/b0c1d2e3f4a5_add_data_correction_module.py`
- **Sidebar nav pattern:** `templates/components/sidebar.html` — gated on `user_permissions.<module>`

---

**Next:** [[phase-01-import-logs-migration|Phase 01: Import Logs Migration + Module Permission]]
