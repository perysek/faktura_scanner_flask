# Improvement Areas — Deep Dive & Remediation Plan

> Companion to `codebase_analysis.md`.
> For each of the 7 weak areas: **what** the weakness is, **why** it is weak,
> a **real-life production scenario** it can cause, and a **detailed, codebase-grounded
> fix** with implementation steps.
>
> Project: MyWay Beauty Salon (Flask 3.1 · PostgreSQL · psycopg2 · Gunicorn on Vultr)

---

## Table of Contents

1. [Schema Dual-Track (schema.sql + Alembic)](#1-schema-dual-track) — 🟡 **PARTIAL 2026-06-03**
2. [Two Competing Repository Access Patterns](#2-two-competing-repository-access-patterns)
3. [Single-Worker Scaling Ceiling (SSE + Scheduler + Import Runner)](#3-single-worker-scaling-ceiling)
4. [No CSRF Protection](#4-no-csrf-protection) — ✅ **DONE 2026-06-03**
5. [Weak SECRET_KEY Lifecycle](#5-weak-secret_key-lifecycle) — ✅ **DONE 2026-06-03**
6. [Unmeasured Test Coverage](#6-unmeasured-test-coverage) — ✅ **DONE 2026-06-03**
7. [Opt-In, Failure-Swallowing Audit Log](#7-opt-in-failure-swallowing-audit-log) — 🟡 **PARTIAL 2026-06-04**

---

## 1. Schema Dual-Track

> 🟡 **PARTIAL — 2026-06-03.** The low-risk half is shipped: `assert_schema_current()`
> (`config/database.py`) runs at boot right after `initialize_database()` and **fails
> loud if a migrated DB is behind head** — turning the silent missing-column 500 into
> a clear boot error. It is conservative by design: *behind head* → raise; *no
> `alembic_version` table* (schema.sql baseline) → warn & continue; pool unavailable
> → skip; `SKIP_SCHEMA_CHECK=true` bypasses. Prod verified at head, so zero boot risk.
> Guard-test coverage in `tests/test_schema_guard.py`. **Deferred (own change):** the
> structural half — removing `initialize_database()`/`schema.sql` auto-run, adding a
> baseline migration, and baking `alembic upgrade head` into deploy — because the
> migration chain mixes `create_table` and `ALTER`s and must be proven to build a
> fresh DB from empty (a `create_table`-vs-`schema.sql` conflict risk) before it's
> safe to remove the bootstrap.

### What is the weakness

The database schema is defined in **two places that evolve independently**:

- **`database/schema.sql`** — a bootstrap script full of `CREATE TABLE IF NOT EXISTS`,
  executed on **every single app startup** by `initialize_database()` (`app.py:134`).
- **`alembic/versions/*.py`** — 30+ incremental migrations that `ALTER`/`CREATE` the same
  tables (`add_pdf_data_to_invoices`, `add_soft_delete_columns`, `add_performance_indexes`…).

`alembic/env.py` confirms there is **no autogenerate safety net**:

```python
# alembic/env.py:19
target_metadata = None   # manual migrations only — Alembic cannot diff against a model
```

So nothing mechanically keeps `schema.sql` and the migration chain in agreement. They are
two hand-maintained sources of truth for the same tables.

### Why it is weak

- `schema.sql` represents the **original baseline**. Every column added later (e.g.
  `invoices.pdf_data`, `is_deleted`, `deleted_at`) lives **only** in a migration, not in
  `schema.sql`.
- `CREATE TABLE IF NOT EXISTS` is a **no-op when the table already exists** — so on an
  existing database `schema.sql` silently does nothing, and the schema is whatever the
  migrations produced. On a **fresh** database, `schema.sql` runs first and produces the
  *baseline-only* shape, which is then (hopefully) patched up by `alembic upgrade head`.
- The two paths therefore produce **different schemas depending on database age**, and the
  divergence is invisible until a query hits a missing column.

### Real-life production scenario

You spin up a **staging server** (or a new developer clones the repo) and run the app.
`initialize_database()` creates every table from `schema.sql` — but the baseline
`invoices` table has **no `pdf_data` column** (that arrived in
`l6m7n8o9p0q1_add_pdf_data_to_invoices.py`). Someone forgets to run `alembic upgrade head`,
or runs it against the wrong `DATABASE_URL`.

The app boots cleanly. The dashboard loads. Then an accountant opens an invoice that tries
to render the stored PDF, and the repository runs:

```sql
SELECT pdf_data FROM invoices WHERE id = %s
```

→ `psycopg2.errors.UndefinedColumn: column "pdf_data" does not exist`.

Because `BaseRepository._fetch_one` only catches `OperationalError`/`InterfaceError`
(`base_repository.py:66-69`), this `ProgrammingError` propagates as a raw 500. Staging looks
"mostly working," so it ships — and the same omission bites in production the first time a
new table/column is exercised.

### How to fix it — make Alembic the single source of truth

**Goal:** one schema authority. `schema.sql` stops being a parallel definition.

**Step 1 — Stop auto-running `schema.sql` on startup.**
Remove the `initialize_database()` call from the app factory:

```python
# app.py — DELETE this line from create_app()
initialize_database()
```

Schema creation becomes an explicit, ordered deploy step, never a side effect of booting.

**Step 2 — Make a clean baseline migration the floor.**
If you want fresh databases to be created by Alembic too, capture the *current* baseline as
the first migration. Since `target_metadata = None`, generate it from the live schema:

```bash
# Dump the current production schema as the canonical baseline
pg_dump --schema-only --no-owner --no-privileges "$DATABASE_URL" > database/baseline_schema.sql
```

Then write one `0000_baseline.py` migration whose `upgrade()` executes that file, and
`alembic stamp 0000_baseline` on existing databases so they don't try to re-create tables.

**Step 3 — Bake migrations into the deploy.**
Add to your Vultr deploy sequence (and document it in `DEPLOYMENT_VULTR.md`):

```bash
source .venv/bin/activate
alembic upgrade head      # the ONLY way schema changes are applied
sudo systemctl restart my-way-beauty-salon
```

**Step 4 — Add a startup guard instead of a startup mutation.**
Rather than *creating* the schema at boot, *verify* it and fail loudly if migrations are
pending. This converts a silent runtime 500 into a clear boot-time error:

```python
# config/database.py
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

def assert_schema_current() -> None:
    """Refuse to boot if the DB is not migrated to head. Fail fast, fail clear."""
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()

    conn = get_pool().getconn()
    try:
        ctx = MigrationContext.configure(conn.cursor())
        current = ctx.get_current_revision()
    finally:
        get_pool().putconn(conn)

    if current != head:
        raise RuntimeError(
            f"Database schema is at '{current}', expected '{head}'. "
            f"Run: alembic upgrade head"
        )
```

Call `assert_schema_current()` in `create_app()` **instead of** `initialize_database()`.

**Step 5 — Delete `database/schema.sql`** once the baseline migration replaces it, or keep it
strictly as documentation with a header comment: `-- REFERENCE ONLY — not executed. Source of
truth is alembic/versions/.`

**Outcome:** schema age no longer matters. Every database — laptop, staging, production — is
exactly `head`, or the app refuses to start and tells you why.

---

## 2. Two Competing Repository Access Patterns

### What is the weakness

`create_app()` instantiates ~16 repositories once and attaches them to the app object:

```python
# app.py:137-152
app.invoice_repo = InvoiceRepository()
app.audit_repo   = AuditRepository()
app.seller_repo  = SellerRepository()
# … 13 more
```

But many routes **ignore those singletons and instantiate fresh repos per request**:

```python
# routes/import_routes.py:145
repo = ImportLogRepository()          # not current_app.import_log_repo

# routes/auth/routes.py:46
AuditRepository().log_event(...)      # not current_app.audit_repo
```

So the codebase has **two patterns for the same job**, with no rule about which to use.

### Why it is weak

- **Cognitive tax & inconsistency.** A new contributor cannot tell whether the "right" way is
  `current_app.invoice_repo` or `InvoiceRepository()`. Both appear in the code; both work.
- **The `app.*` singletons are a latent trap.** They work *today* only because repositories
  are stateless — every method pulls its connection from `g` via
  `DatabaseConnection.get_connection()`. The moment anyone adds instance state to a repo
  (a cached cursor, a per-user filter, a memoized lookup), the shared singleton silently
  leaks that state across requests and across threads (`gthread`, 4 threads).
- **Half the wiring is dead code.** `app.audit_repo` is attached at startup, then never used
  because routes build their own — so the startup cost and the attribute are pure noise.

### Real-life production scenario

Six months from now, someone optimizes `InvoiceRepository` by caching the seller lookup on
the instance to avoid repeated queries:

```python
class InvoiceRepository(BaseRepository):
    def __init__(self):
        super().__init__("invoices")
        self._seller_cache = {}        # <-- innocent-looking, deadly on a singleton
```

`app.invoice_repo` is **one object shared by all 4 Gunicorn threads**. Accountant A loads
invoices and populates `_seller_cache`. Accountant B (different request, same shared
instance, same dict) now sees A's cached sellers — and because plain `dict` is not
thread-safe, two simultaneous writes can corrupt it or raise `RuntimeError: dictionary
changed size during iteration`. The bug is intermittent, environment-dependent, and nearly
impossible to reproduce locally with one user. Classic Heisenbug born from "repos are
obviously stateless, so a singleton is fine."

### How to fix it — pick one pattern: stateless per-call instantiation

Repositories here are **cheap, stateless connection-borrowers**. The cleanest rule is:
*don't keep them as singletons at all — instantiate at point of use.* This makes the
statelessness a guarantee, not a hope.

**Step 1 — Remove the singleton attachments from `create_app()`:**

```python
# app.py — DELETE the whole repo block (lines ~137-152)
# app.invoice_repo = InvoiceRepository()
# app.audit_repo   = AuditRepository()
# … etc
```

(Keep service singletons that genuinely hold config/state, e.g. `app.ocr_service`,
`app.email_service` — those are legitimately long-lived.)

**Step 2 — Standardize routes on local instantiation** (the pattern `import_routes.py` and
`auth/routes.py` already use):

```python
@invoice_bp.route('/invoices/<int:id>')
@login_required
@module_permission_required('invoices')
def view_invoice(id):
    repo = InvoiceRepository()           # one rule, everywhere
    invoice = repo.get_by_id(id)
    ...
```

**Step 3 — Make statelessness structurally impossible to violate.** Forbid instance state in
`BaseRepository` so the trap can never be set:

```python
# repositories/base_repository.py
class BaseRepository:
    # Only class-level config is allowed. No per-instance mutable state.
    __slots__ = ('table_name',)        # AttributeError on any stray self.x = ...

    def __init__(self, table_name: str):
        self.table_name = table_name
```

With `__slots__`, the caching "optimization" from the scenario above raises immediately at
construction time instead of silently corrupting data in production.

**Step 4 — (Optional) Enforce with a lint rule.** Add a grep gate to CI to stop the singleton
pattern creeping back:

```bash
# fails the build if any code reads current_app.*_repo
! grep -rn "current_app\.\w*_repo" routes/ services/
```

**Outcome:** one obvious way to obtain a repository, statelessness guaranteed by `__slots__`,
no shared mutable objects across threads, and ~16 lines of dead wiring removed from boot.

---

## 3. Single-Worker Scaling Ceiling

### What is the weakness

Three pieces of **in-process, in-memory state** force the app to run as exactly one OS
process:

- `IMPORT_RUNNER` — an in-memory queue + background thread (`services/data_import_runner.py`)
  whose `get_queue(import_id)` feeds the SSE stream in `import_routes.py:150`.
- The **APScheduler** instance (`scheduler.py`) that fires SMS every 15 minutes.
- The SSE stream itself, which must be served by the **same process** that owns the import's
  queue.

`gunicorn.conf.py` correctly contains this today:

```python
# gunicorn.conf.py:9-11
workers = 1                 # single process required for in-memory state
worker_class = "gthread"
threads = 4
```

So this is **not currently a bug** — it is a deliberately enforced constraint. The weakness is
that it is a **hard scaling ceiling and a fragile invariant**: the correctness of imports,
SSE, and SMS *silently depends* on `workers == 1`, and nothing prevents someone from changing
that number.

### Why it is weak

- **No horizontal scaling.** All traffic — OCR (up to 180s), report exports, every page —
  shares **4 threads in one process**. Python's GIL means CPU-bound OCR blocks other threads.
  One accountant running a heavy import can stall the salon's booking screen.
- **The invariant is implicit.** A future deploy that bumps `workers = 4` for throughput will
  *appear* to work and then break in two specific ways below. The coupling lives only in a
  comment.

### Real-life production scenario

Black-Friday-equivalent for the salon: the owner bumps `workers = 3` to handle a rush.
Two things break immediately and confusingly:

1. **SMS sent triple.** APScheduler is started in `create_app()`, so **each of the 3 workers**
   now runs its own scheduler. Every client gets **3 identical appointment reminders** at the
   :00/:15/:30/:45 tick. Clients complain; Twilio bill triples; reputation hit.
2. **Import progress bar hangs forever.** The browser opens the SSE stream
   `/api/import/<id>/stream`, which Nginx load-balances to **worker B**. But the import is
   running in **worker A's** `IMPORT_RUNNER`. `IMPORT_RUNNER.get_queue(id)` returns `None` in
   worker B, so the stream emits a synthetic "done" (or nothing) while the real import grinds
   on invisibly. The admin sees a frozen bar, clicks "Start" again → `has_running_import()`
   blocks it with a confusing conflict, or worse, starts a duplicate against caldis.pl.

### How to fix it — externalize the shared state, then scale freely

You don't need this until you outgrow one process — but here is the migration path, smallest
blast radius first.

**Fix 3a — Make the scheduler safe under N workers (do this even at workers=1).**
Use a Postgres-backed lock so exactly one process owns the scheduler, regardless of worker
count:

```python
# scheduler.py
import os
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def start_scheduler(app):
    global _scheduler
    # Postgres advisory lock — only the first worker to grab it runs jobs.
    conn = get_pool().getconn()
    try:
        got = conn.cursor().execute("SELECT pg_try_advisory_lock(0x5M5)")  # arbitrary key
        if not conn.cursor().fetchone()[0]:
            return                         # another worker already owns the scheduler
    finally:
        get_pool().putconn(conn)

    _scheduler = BackgroundScheduler(
        timezone='Europe/Warsaw',
        jobstores={'default': SQLAlchemyJobStore(url=os.environ['DATABASE_URL'])},
    )
    _scheduler.add_job(..., id='sms_auto_send', replace_existing=True,
                       max_instances=1, coalesce=True)
    _scheduler.start()
```

`replace_existing=True` + a shared jobstore means even if two workers race, the job is
defined once. The advisory lock guarantees a single runner.

**Fix 3b — Move import progress to a process-shared transport.**
Replace the in-memory `queue.Queue` with a transport every worker can read:

- **Lightest:** the import worker writes progress rows/JSON into the existing `import_logs`
  table (or a new `import_progress` table); the SSE endpoint **polls the DB** every ~1s
  instead of draining an in-memory queue. No new infrastructure — you already have Postgres.
- **Best for real-time:** publish progress to **Redis Pub/Sub**; the SSE endpoint subscribes.
  Any worker can serve any stream because the queue lives in Redis, not process memory.

DB-polling version of the SSE generator:

```python
def _build_sse_generator(import_id, repo, heartbeat_seconds=2):
    last_seen = 0
    while True:
        events = repo.get_progress_since(import_id, last_seen)   # reads import_progress
        for ev in events:
            last_seen = ev['seq']
            yield f"data: {json.dumps(ev, default=str)}\n\n"
            if ev['type'] == 'done':
                return
        if not events:
            yield ": hb\n\n"
        time.sleep(heartbeat_seconds)
```

**Fix 3c — Move long imports out of the request process entirely.**
For real scale, run imports under a dedicated worker (Celery, RQ, or Dramatiq) so OCR and
caldis scraping never compete with web threads. The web process only *enqueues* and *reads
progress*; a separate process *does the work*.

**Then** you can safely set `workers = 3+` and add a **hard guard** so the invariant can never
be silently violated again:

```python
# app.py — refuse to boot the in-memory scheduler under multiple workers
import multiprocessing
if os.environ.get('WEB_CONCURRENCY', '1') != '1' and _scheduler_is_in_memory():
    raise RuntimeError("In-memory scheduler requires workers=1. Externalize first.")
```

**Outcome:** SMS fires exactly once, import progress survives load-balancing, OCR stops
blocking bookings, and the `workers=1` assumption is either removed or enforced in code rather
than trusted to a comment.

---

## 4. No CSRF Protection

> ✅ **COMPLETED — 2026-06-03.** Flask-WTF `CSRFProtect` enabled globally in
> `app.py`; `public_bp` + `booking_bp` exempted (token-URL / open-by-design);
> `CSRFError` handler returns clean JSON/HTML. A global `fetch`/`XMLHttpRequest`
> shim in `base.html` auto-attaches `X-CSRFToken` to every same-origin mutating
> request, and the 9 authenticated server-rendered forms (login, forgot/reset/
> change-password, absences ×2, SMS settings ×3) carry a hidden `csrf_token`.
> Session cookies hardened: `HttpOnly` + `SameSite=Lax` always, `Secure` env-gated
> (off on the HTTP server). Verified: `create_app()` boots, exemptions =
> `['booking', 'public']`, `csrf_token()` renders, shim passes `node --check`.

### What is the weakness

The app authenticates with **cookie-based Flask-Login sessions** but applies **no CSRF
token** to any state-changing request. Every mutation — `POST /auth/login`,
`POST /api/import/start`, every create/edit/delete form and `fetch()` — trusts the session
cookie alone. `auth/routes.py` reads `request.form` directly with no token check; there is no
`Flask-WTF`, no `CSRFProtect`, no double-submit cookie anywhere.

### Why it is weak

Browsers **automatically attach session cookies to every request to your domain**, including
requests triggered by *other* websites. Without a CSRF token, the server cannot distinguish
"the logged-in admin clicked this button on our site" from "the logged-in admin's browser was
tricked into firing this request by a malicious page." Session-cookie auth + no CSRF token =
textbook Cross-Site Request Forgery exposure on every mutation endpoint.

### Real-life production scenario

The salon admin is logged into the app (session cookie live in their browser). During lunch
they open a phishing email link — an innocent-looking page that contains:

```html
<!-- attacker's page -->
<form id="x" action="https://salon.example.com/api/import/start" method="POST">
  <input name="date_start" value="2020-01-01">
  <input name="date_end"   value="2026-01-01">
</form>
<script>document.getElementById('x').submit();</script>
```

The browser submits it **with the admin's session cookie automatically attached**. The server
sees a valid session and kicks off a 6-year caldis.pl import — hammering the upstream site,
filling the DB, and possibly tripping `has_running_import()` for legitimate users. Swap the
target for `POST /users/create` (creating a rogue superuser) or a delete endpoint and the
forged request becomes a full account takeover or data-loss event. The admin did nothing but
open a link.

### How to fix it — Flask-WTF CSRF, covering both forms and `fetch()`

**Step 1 — Install and enable global CSRF protection:**

```bash
pip install Flask-WTF        # add Flask-WTF to requirements.txt
```

```python
# app.py
from flask_wtf import CSRFProtect
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    ...
    csrf.init_app(app)       # now every POST/PUT/PATCH/DELETE requires a valid token
```

**Step 2 — Inject the token into every page** so JS can read it. Add to the existing context
processor in `app.py`:

```python
@app.context_processor
def inject_globals():
    from flask_wtf.csrf import generate_csrf
    return {
        ...,
        'csrf_token': generate_csrf,     # callable used in templates
    }
```

```html
<!-- templates/base.html — inside <head> -->
<meta name="csrf-token" content="{{ csrf_token() }}">
```

**Step 3 — Add a hidden field to every server-rendered `<form>`:**

```html
<form method="POST" action="{{ url_for('auth.login') }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  ...
</form>
```

**Step 4 — Make the JS `fetch()` wrapper send the token automatically.** You already have a
central `static/js/api.js` — add the header in one place and every AJAX call is covered:

```javascript
// static/js/api.js
const CSRF = document.querySelector('meta[name="csrf-token"]')?.content;

async function apiFetch(url, options = {}) {
    options.headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,           // Flask-WTF reads this header for JSON requests
        ...(options.headers || {}),
    };
    return fetch(url, options);
}
```

Flask-WTF checks the `X-CSRFToken` header for non-form requests by default, so JSON `POST`s
like `/api/import/start` are protected without changing their bodies.

**Step 5 — Exempt only true machine-to-machine endpoints**, explicitly and narrowly. Inbound
**Twilio status webhooks** have no browser session and must be exempted — but secure them with
Twilio request-signature validation instead:

```python
@csrf.exempt
@sms_bp.route('/sms/status-callback', methods=['POST'])
def twilio_status_callback():
    validate_twilio_signature(request)   # replace CSRF with signature auth
    ...
```

**Step 6 — Lock the session cookie down** as defense-in-depth (these also blunt CSRF):

```python
# app.py
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,        # HTTPS only (you're behind Nginx)
    SESSION_COOKIE_SAMESITE='Lax',     # browser won't send cookie on cross-site POSTs
)
```

`SameSite=Lax` alone defeats the lunch-break scenario above, and the token defeats the rest.

**Outcome:** every mutation requires a token the attacker's page cannot read (same-origin
policy), forged cross-site requests are rejected with 400, and webhooks are authenticated by
signature rather than left wide open.

---

## 5. Weak SECRET_KEY Lifecycle

> ✅ **COMPLETED — 2026-06-03.** `app.py` now rejects at boot any `SECRET_KEY`
> that is unset, shorter than 32 chars, or a known placeholder (incl. the old
> `.env.example` default). `.env.example` ships an empty `SECRET_KEY=` with an
> inline generator hint (no more copy-paste trap). `DEPLOYMENT_VULTR.md` documents
> the boot-time validation and adds a one-command rotation procedure (forces
> global logout for incident response). Verified: placeholder / `'dev'` / short /
> empty keys all rejected; a 64-char key boots cleanly.

### What is the weakness

`app.py` correctly **hard-fails if `SECRET_KEY` is unset** (`app.py:84-90`) — good. But the
surrounding lifecycle is weak:

- `.env.example` ships a **copy-pasteable placeholder**:
  `SECRET_KEY=change-this-to-a-long-random-string`. A literal copy passes the "is it set?"
  check while being a *publicly known* key.
- There is **no entropy/length validation** — a one-character key is accepted.
- There is **no documented rotation procedure**.

### Why it is weak

`SECRET_KEY` signs Flask session cookies (and Flask-WTF CSRF tokens). Anyone who knows the key
can **forge a session cookie for any user**, including a superuser — no password required.
A placeholder value committed to a public-ish repo is functionally a backdoor.

### Real-life production scenario

The app is deployed in a hurry. Someone copies `.env.example` to `.env`, fills in
`DATABASE_URL`, and **leaves `SECRET_KEY=change-this-to-a-long-random-string`** because the app
booted fine and nothing complained. That exact string is in the git history, readable by
anyone who ever had repo access (contractors, a leaked laptop, a public mirror).

An attacker who knows the placeholder forges a signed session cookie claiming `user_id = 1`:

```python
# attacker, offline — no server interaction needed until the final request
from itsdangerous import URLSafeTimedSerializer
s = URLSafeTimedSerializer("change-this-to-a-long-random-string",
                           salt="cookie-session")
forged = s.dumps({"_user_id": "1"})   # superuser
```

They paste it as their `session` cookie and are now logged in as the salon owner — full RBAC
access to invoices, client PII, employee salaries (`employer_cost_rate`), and SMS settings.
No brute force, no password, no log of a failed login.

### How to fix it — validate entropy at boot, kill the placeholder, document rotation

**Step 1 — Reject weak and placeholder keys at startup**, not just empty ones:

```python
# app.py — replace the existing SECRET_KEY block
secret_key = os.environ.get('SECRET_KEY')

_PLACEHOLDERS = {'change-this-to-a-long-random-string', 'changeme', 'secret', 'dev'}
if not secret_key:
    raise RuntimeError(
        'SECRET_KEY is not set. Generate one with:\n'
        '  python -c "import secrets; print(secrets.token_hex(32))"'
    )
if secret_key in _PLACEHOLDERS or len(secret_key) < 32:
    raise RuntimeError(
        'SECRET_KEY is a placeholder or too short (<32 chars). '
        'It must be a unique, high-entropy value. Generate one with:\n'
        '  python -c "import secrets; print(secrets.token_hex(32))"'
    )
app.config['SECRET_KEY'] = secret_key
```

Now a copied placeholder **cannot boot** — the failure happens at deploy time, in your face,
not silently in production.

**Step 2 — Remove the copy-paste trap from `.env.example`.** Make the value impossible to use
verbatim and put the generator command inline:

```bash
# .env.example
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=
```

An empty value triggers the "not set" error with instructions, instead of silently accepting a
known string.

**Step 3 — Document rotation in `DEPLOYMENT_VULTR.md`.** Rotating the key invalidates all
sessions (everyone is logged out) — that is the *intended* effect after a suspected leak:

```bash
# Rotate SECRET_KEY (forces global logout — use after any suspected exposure)
NEW=$(python -c "import secrets; print(secrets.token_hex(32))")
sudo sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$NEW/" /opt/faktura-scanner/.env
sudo systemctl restart my-way-beauty-salon
```

**Step 4 — Scrub the placeholder from git history** if it was ever a real value anywhere
(`.env` should already be gitignored — verify it never slipped in):

```bash
git log -p --all -S 'change-this-to-a-long-random-string' -- .env   # confirm it's only in .env.example
```

**Outcome:** the only way to run the app is with a unique, 32+ byte key; the placeholder is
unusable; and there is a one-command rotation play for incident response.

---

## 6. Unmeasured Test Coverage

> ✅ **COMPLETED — 2026-06-03.** Coverage is now measured and gated. Reality
> differed from this section's assumptions: a real pytest suite already existed
> (~375 tests across `repositories/`, `routes/`, `services/`, `utils/`, including
> the exact `managed_transaction` invariant test Step 3 proposes) — but it was
> **silently broken**. Improvement #5's `SECRET_KEY` boot check rejected
> `conftest.py`'s 15-char test key, erroring 16 tests; two transaction-rollback
> tests had rotted against later appointment features (missing `appointment_date`
> mock + un-stubbed working-hours/absence validators); one IBAN test was stale
> (validator was broadened to all EU IBANs in P2-6). All fixed → **375 green**.
> Added `.coveragerc` (the gate lives in CI, *not* in `pytest.ini addopts`, so
> single-file local runs aren't punished with a threshold) and a real
> **`.github/workflows/ci.yml`** that runs the suite with `--cov-fail-under=25`
> (today's baseline: 28%). No Postgres service needed — the suite is fully
> mock-based (`conftest.py` patches the pool; the `integration` marker is unused).
> Cleaned up the stale root scripts: deleted the SQLite-era `test_db_schema.py`
> and moved the two live-server smoke scripts to `scripts/manual/`.

### What is the weakness

Tests exist (`tests/`, plus root-level `test_api_endpoints.py`, `test_db_schema.py`,
`test_session_debug.py`) but there is:

- **No coverage measurement** — nobody knows if it's 5% or 60%.
- **No CI gate** — the GitHub Actions workflows are Claude review bots, not a `pytest` run.
- **No clear unit/integration split** — the root `test_*.py` files look like ad-hoc scripts
  that need a live DB, so they likely don't run in CI at all.

### Why it is weak

This is a **financial and PII application** — invoices, salaries (`employer_cost_rate`),
client phone numbers, SMS billing. Without a coverage signal and a CI gate, every refactor is
a leap of faith. The intricate, high-risk logic — `managed_transaction()` commit suppression,
the OCR 4-profile retry, RBAC fallback in `module_permission_required`, soft-delete filtering
in `BaseRepository` — is exactly the kind of code that breaks silently and is never caught by
manual clicking.

### Real-life production scenario

A developer "simplifies" `safe_commit()` (`config/database.py:101`), not realizing
`managed_transaction()` relies on it being a **no-op** while `g._in_transaction` is `True`.
Their change makes `safe_commit()` always commit. Every multi-table operation that *looks*
atomic is now committing mid-way. There is no test asserting "inside `managed_transaction`,
individual repo calls do **not** commit," so CI is green.

In production, an absence approval that writes to `absences` **and** `absence_balance_adjustments`
fails halfway. The first table commits, the second rolls back — but the rollback no longer
undoes the first because it was already committed. An employee's leave is recorded with **no
matching balance deduction**. The books are now wrong, quietly, and you find out at year-end
reconciliation.

### How to fix it — measure, split, and gate

**Step 1 — Add coverage tooling:**

```bash
pip install pytest-cov     # add to requirements-dev.txt
```

```ini
# pytest.ini
[pytest]
testpaths = tests
addopts = --cov=. --cov-report=term-missing --cov-fail-under=50
markers =
    integration: requires a live PostgreSQL database
```

**Step 2 — Separate unit from integration.** Move the root `test_*.py` DB-dependent scripts
into `tests/integration/` and mark them, so unit tests run anywhere and integration runs only
where a DB exists:

```python
# tests/integration/test_api_endpoints.py
import pytest
pytestmark = pytest.mark.integration
```

Run fast unit tests with `pytest -m "not integration"`.

**Step 3 — Write the characterization tests that guard the dangerous invariants first.** The
highest-value test, given the scenario above:

```python
# tests/test_managed_transaction.py
from unittest.mock import MagicMock, patch
from config.database import managed_transaction, safe_commit

def test_safe_commit_is_suppressed_inside_managed_transaction(app):
    conn = MagicMock()
    with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
        with app.test_request_context():
            with managed_transaction():
                safe_commit(conn)            # must NOT commit here
                safe_commit(conn)
                conn.commit.assert_not_called()
            conn.commit.assert_called_once()  # exactly one commit, at the end
```

This single test would have turned the silent year-end discrepancy into a red CI build.

**Step 4 — Add a real CI job** (`.github/workflows/ci.yml`) with a Postgres service so
integration tests run on every PR:

```yaml
name: CI
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: test_db }
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          SECRET_KEY: ${{ '0'*64 }}
        run: |
          alembic upgrade head
          pytest --cov=. --cov-fail-under=50
```

**Step 5 — Ratchet the threshold.** Start `--cov-fail-under` at today's real number, then raise
it a few points per PR. Coverage only goes up, never down.

**Outcome:** a known coverage number, fast unit tests on every push, integration tests against
a real Postgres, and a CI gate that turns the most dangerous silent regressions into loud red
builds.

---

## 7. Opt-In, Failure-Swallowing Audit Log

> 🟡 **PARTIAL — 2026-06-04.** Flaws #2 (silent swallowing) **and** the headline of
> Step 2 (atomic audit on the financial path) are now fixed; only Step 3 (the
> data-layer mixin) remains.
>
> **Step 1 — de-swallow (2026-06-03).** Added `AuditRepository.safe_log_event(critical=False)`:
> a failed audit write is now logged at ERROR (or re-raised when `critical=True`),
> never silently dropped. Converted **all 9** `try/except: pass` audit sites
> (`auth` ×5, `users` ×3, `upload` ×1) to it, plus a guard test
> (`tests/repositories/test_audit_repository.py`). (2026-06-04) Also routed the
> `api_routes._audit` helper — a 10th swallow site that printed failures to stderr
> instead of monitoring — through `safe_log_event`, so every audit failure now
> surfaces through one logger path.
>
> **Step 2 — atomic audit (2026-06-04).** The canonical financial mutation — invoice
> create + update in `routes/api_routes.py` — now wraps its data write **and** its
> audit row(s) in one `managed_transaction()`. Both share a single commit on the
> per-request connection, so an invoice amount/seller edit can never commit without
> its forensic audit record, and an audit failure rolls the edit back. Locked by
> `TestInvoiceAuditAtomicity` (3 tests, real `AuditRepository` so `safe_commit`
> suppression is genuinely exercised). **384 green.**
>
> **Deferred (own change):** Step 3 (`AuditableMixin` for automatic data-layer audit)
> — it directly conflicts with the existing route-level `log_change` calls (wiring it
> into `InvoiceRepository` would double-log every mutation), so it requires a
> coordinated move of audit *out* of the routes and *into* the repos, which is a
> larger, separately-reviewed refactor.
>
> **Step 2b — absence-balance atomic audit (2026-06-04).** Extended the same atomic
> pattern to HR/payroll: `AbsenceBalanceService.set_limit / remove_limit /
> create_adjustment / delete_adjustment` now wrap their data write + audit row in one
> `managed_transaction`, so a leave-balance change (a payroll liability) can never move
> without a forensic record of who moved it. This needed a prerequisite migration:
> `absence_limit_repository` and `absence_adjustment_repository` were converted from
> `with get_db_connection() as conn: ... conn.commit()` — which committed immediately
> *and* (via psycopg2's connection context-manager) auto-committed on block exit,
> ignoring the transaction flag — to the `BaseRepository` pattern
> (`conn = get_db_connection(); ...; safe_commit(conn)`). Behaviour-preserving outside
> a transaction; correct deferral inside. Locked by
> `tests/services/test_absence_balance_atomicity.py` (6 tests, real repos + real
> AuditRepository on a shared mocked connection). **390 green.**
>
> **Remaining consistency follow-up:** the sibling absence repos (`absence_repository`,
> `absence_category_repository`, `employee_supervisor_repository`) still call raw
> `conn.commit()` — harmless today (no audited transaction wraps them yet), but the
> same `safe_commit` conversion should be applied for consistency when convenient.

### What is the weakness

`AuditRepository.log_event()` is a solid, generic audit primitive — it accepts any
`entity_type`/`action` and supports invoices, appointments, logins, imports, etc. But its
**usage** has two structural flaws, both visible in `auth/routes.py`:

1. **It is opt-in.** Audit rows are written only where a developer *remembers* to call
   `log_event()`. There is no enforcement, so coverage is patchy by construction.
2. **It silently swallows its own failures:**

```python
# routes/auth/routes.py:45-53
try:
    AuditRepository().log_event(entity_type='login', action='LOGIN', ...)
except Exception:
    pass        # <-- a failed audit write is indistinguishable from a successful one
```

### Why it is weak

For a system tracking money and PII, the audit trail is a **compliance and forensic
artifact** — "who changed this invoice's amount, and when?" The `try/except: pass` pattern
means:

- If the `audit_log` table is missing a column, locked, or the write fails for any reason, the
  business operation **succeeds with no trace**. You cannot tell a clean operation from one
  whose audit was dropped.
- Because logging is manual, the riskiest mutations (a direct invoice amount edit, an absence
  balance adjustment, a role permission change) may have **no audit call at all** — and nobody
  notices until they're asked to produce the trail.

### Real-life production scenario

A dispute arises: an invoice's `amount` was changed from 12,000 PLN to 1,200 PLN and marked
paid. The accountant swears they didn't touch it. You open the audit trail to see who did —
and there's **nothing**, because either (a) the edit route never called `log_event()`, or
(b) it did, but the call raised (e.g. a stale `audit_log` schema after the dual-track issue
from §1) and `except: pass` ate it. Either way you have **no forensic record** of a financial
change. In a tax audit or an internal fraud investigation, "our system doesn't reliably log
changes" is a serious finding.

### How to fix it — centralize, never swallow, and automate at the data layer

**Step 1 — Stop swallowing audit failures.** A failed audit write on a sensitive action should
*at minimum* be logged loudly; for the most sensitive actions it should fail the operation.
Replace `except: pass` with a helper:

```python
# repositories/audit_repository.py
import logging
logger = logging.getLogger(__name__)

def safe_log_event(self, *, critical: bool = False, **kwargs):
    """Log an audit event. Never silently lose it.
    critical=True  -> re-raise on failure (the business op must not proceed un-audited)
    critical=False -> log the failure at ERROR so it surfaces in monitoring
    """
    try:
        self.log_event(**kwargs)
    except Exception:
        logger.error("AUDIT WRITE FAILED: %s", kwargs, exc_info=True)
        if critical:
            raise
```

Login attempts can be `critical=False` (don't lock users out if audit hiccups), but an invoice
amount change should be `critical=True`.

**Step 2 — Audit *in the same transaction* as the change** so the two cannot diverge. Using the
existing `managed_transaction()`:

```python
with managed_transaction():
    invoice_repo.update_amount(invoice_id, new_amount)
    AuditRepository().log_event(
        entity_type='invoice', action='UPDATE', entity_id=invoice_id,
        field_name='amount', old_value=str(old), new_value=str(new_amount),
        user_id=current_user.id, user_name=current_user.full_name,
    )
# both commit together, or both roll back — the audit row can never be orphaned or missing
```

This is the single most important change: the audit write and the data write share one commit,
so "changed but not logged" becomes structurally impossible.

**Step 3 — Make audit automatic for write repos instead of relying on memory.** Add an opt-in
mixin that logs at the data layer, so any repo that mixes it in audits *every* mutation without
the route remembering:

```python
# repositories/auditable.py
from flask_login import current_user
from repositories.audit_repository import AuditRepository

class AuditableMixin:
    """Repos that mix this in get automatic CREATE/UPDATE/DELETE audit rows."""
    audit_entity_type: str = None     # e.g. 'invoice'

    def _audit(self, action, entity_id, *, field_name=None, old=None, new=None, label=None):
        uid  = getattr(current_user, 'id', None)
        name = getattr(current_user, 'full_name', None)
        AuditRepository().log_event(
            entity_type=self.audit_entity_type, action=action, entity_id=entity_id,
            entity_label=label, field_name=field_name,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            user_id=uid, user_name=name,
        )

# Usage:
class InvoiceRepository(AuditableMixin, BaseRepository):
    audit_entity_type = 'invoice'
    def update_amount(self, id, new_amount):
        old = self.get_by_id(id)['amount']
        self._execute("UPDATE invoices SET amount=%s WHERE id=%s", (new_amount, id))
        self._audit('UPDATE', id, field_name='amount', old=old, new=new_amount)
```

**Step 4 — Add a coverage check.** A simple test asserts that the sensitive routes produce an
audit row, so a future refactor that drops the `log_event` call fails CI:

```python
def test_invoice_amount_edit_writes_audit_row(client, db):
    edit_invoice(client, invoice_id=1, amount=999)
    rows = AuditRepository().get_all(entity_type='invoice')
    assert any(r['field_name'] == 'amount' and r['new_value'] == '999' for r in rows)
```

**Outcome:** audit failures are loud (or fatal for critical actions), the audit row commits
atomically with the change it describes, sensitive repos log every mutation automatically, and
a test guards the trail against future regressions — turning a best-effort log into a
trustworthy forensic record.

---

## Priority Summary

| # | Area | Severity | Effort | Do first because… |
|---|------|----------|--------|-------------------|
| 4 | No CSRF | **Critical** | Low | ✅ DONE 2026-06-03 — CSRFProtect + shim + form tokens |
| 5 | Weak SECRET_KEY | **Critical** | Low | ✅ DONE 2026-06-03 — boot-time validation + rotation doc |
| 7 | Audit swallows failures | High | Medium | 🟡 PARTIAL 2026-06-04 — swallowing + atomic-write (invoice **and** absence-balance paths) done; only data-layer mixin remains |
| 1 | Schema dual-track | High | Medium | 🟡 PARTIAL 2026-06-03 — boot guard added (`assert_schema_current`); schema.sql removal deferred |
| 6 | Unmeasured tests | High | Medium | ✅ DONE 2026-06-03 — suite repaired (375 green), `.coveragerc` + CI gate |
| 2 | Repo pattern split | Medium | Low | Latent thread-safety trap; cheap to standardize now |
| 3 | Single-worker ceiling | Medium | High | Already contained at workers=1; only urgent when you must scale |

**Suggested order:** 4 → 5 (a day, closes the two critical security holes) → 6 (so the rest is
regression-guarded) → 7 → 1 → 2 → 3 (when scaling demands it).

**Progress:** 4 ✅ · 5 ✅ · 6 ✅ · 7 🟡 (swallowing + atomic-write on invoice **and**
absence-balance paths done; data-layer mixin deferred) · 1 🟡 (boot guard added;
schema.sql removal deferred).
Remaining: 7 (mixin only) · 1 (finish) · 2 (repo pattern split — note: 290 call sites,
not "Low" effort) · 3 (single-worker ceiling).
