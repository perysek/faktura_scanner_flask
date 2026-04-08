# Phase 8: Database Performance - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Database-level performance hardening. Three specific improvements:
1. Add indexes on frequently filtered columns (appointments + income_records)
2. Optimize analytics repository heavy queries (aggregations, STRING_AGG, date range)
3. Refactor employee schedule from N+1 per-employee queries to single JOIN query

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices at Claude's discretion — requirements are prescriptive.

Key constraints from REQUIREMENTS.md (SCAL-01, SCAL-02, SCAL-03):

**SCAL-01 — Indexes:**
- appointments.appointment_date (frequently filtered)
- appointments.employee_id (JOIN target + filter)
- appointments.status (filtered in most queries)
- income_records.appointment_id (JOIN target)
- Composite indexes for multi-column WHERE + ORDER BY patterns

**SCAL-02 — Analytics optimization:**
- Heavy aggregations in analytics repository refactored
- STRING_AGG operations bounded (LIMIT or TOP-N)
- Date range filtering enforced (no unbounded full-table scans)

**SCAL-03 — Employee schedule:**
- Current: separate query per employee (N+1)
- Target: single JOIN query with date range filter

</decisions>

<code_context>
## Existing Code Insights

### Key Files to Read
- `alembic/versions/` — existing migrations for migration pattern
- `repositories/analytics/` — analytics repository with heavy queries
- Any employee schedule fetching code (search for `schedule` or per-employee loop)
- `alembic/env.py` — migration configuration

### Established Patterns
- Alembic migrations in `alembic/versions/`
- Repository pattern: `repositories/<domain>/<name>_repository.py`
- From Phase 6: `self._columns` projection pattern in repositories

### Integration Points
- New migration: add indexes (no data changes, safe to run on existing data)
- Analytics repository: refactor queries in place, same interface
- Employee schedule: likely in `repositories/employees/` or `routes/`

</code_context>

<specifics>
## Specific Requirements

SCAL-01: Alembic migration adding indexes:
- `CREATE INDEX` on appointments(appointment_date), appointments(employee_id), appointments(status)
- `CREATE INDEX` on income_records(appointment_id)
- Composite: e.g., (employee_id, appointment_date) for schedule queries

SCAL-02: Analytics queries — find STRING_AGG and heavy GROUP BY, add date range WHERE clauses

SCAL-03: Employee schedule N+1 → single JOIN (find existing N+1 loop first)

</specifics>

<deferred>
## Deferred Ideas

None.

</deferred>
