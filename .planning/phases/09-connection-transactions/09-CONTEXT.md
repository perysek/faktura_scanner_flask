# Phase 9: Connection & Transactions - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Database connection lifecycle hardening: pooling, request-scoped connections, timeout configuration, leak prevention, and dependency hygiene. Capstone phase — touches connection layer that all previous phases depend on.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices at Claude's discretion — infrastructure phase.

Key constraints from REQUIREMENTS.md (SCAL-04, MIGR-01, MIGR-02):

**SCAL-04 — Connection pooling:**
- Proper pool size management (min/max connections)
- Connection timeout configuration
- Health checks (connection validity before use)
- Cleanup on request end (return to pool, not leak)

**MIGR-01 — Dependency audit:**
- Run `pip check` for broken dependencies
- Run `pip list --outdated` for stale packages
- Apply critical updates with compatibility testing
- Document decisions (what was updated, what was deferred and why)

**MIGR-02 — psycopg2 lifecycle:**
- Connection lifecycle tied to request scope (not module-level or global)
- Timeout configuration (connect_timeout, statement_timeout)
- Leak prevention via context managers (with conn, with cursor)

</decisions>

<code_context>
## Existing Code Insights

### Key Files to Read
- `database.py` — current connection management (likely get_connection pattern)
- `requirements.txt` or `Pipfile` — current dependency versions
- Any `@app.teardown_appcontext` or `@app.before_request` hooks
- Repositories using `get_connection()` — how connections are consumed

### Established Patterns
- From Phase 7: startup validation in create_app() (RuntimeError for missing env vars)
- Repository pattern: repositories call get_connection() for database access
- Alembic for schema migrations (but pooling is runtime config, not migration)

### Integration Points
- database.py — pooling and connection lifecycle changes here
- All repositories — consumers of get_connection(), interface must be preserved
- app.py create_app() — teardown hooks for connection cleanup

</code_context>

<specifics>
## Specific Requirements

SCAL-04: Replace raw psycopg2.connect() with connection pool (psycopg2.pool or similar).
Pool config via env vars (DB_POOL_MIN, DB_POOL_MAX, DB_CONNECT_TIMEOUT).

MIGR-01: pip check + pip list --outdated → document results, apply critical updates.

MIGR-02: Ensure all database access uses context managers. No bare cursor.execute() without proper cleanup. Connection returned to pool on request end.

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
