---
phase: 08-database-performance
plan: 02
subsystem: analytics
tags: [performance, sql, analytics, index-usage]
key-files:
  modified:
    - repositories/analytics/analytics_repository.py
decisions:
  - "180-day CTE lookback chosen to cover the 90-day retention window with comfortable buffer"
  - "first_appointments CTE left intentionally unfiltered — bounding it would mis-classify existing clients as new"
metrics:
  duration: ~5 minutes
  completed: 2026-04-08T03:30:00Z
  tasks-completed: 2
  files-modified: 1
---

# Phase 08 Plan 02: Bound Analytics Repository Unbounded Queries Summary

## What Was Implemented

Fixed one unbounded full-table scan in `analytics_repository.py` and added an explanatory
comment to a second CTE that is intentionally unfiltered.

### Task 1 — Bound `client_visits` CTE in `get_client_metrics()` (perf fix)

The `retention_query` CTE previously read every completed appointment ever recorded with
no date constraint:

```sql
WHERE status = 'completed'
```

This prevented the `idx_appointments_status_date` composite index from being used, causing
a full table scan that would degrade linearly with appointment history growth.

Fix: added a 180-day lower bound to the CTE's WHERE clause:

```sql
WHERE status = 'completed'
  AND appointment_date >= %s - INTERVAL '180 days'
```

The 180-day buffer is intentional — LAG() needs the previous visit, which may predate the
selected period's `start_date`. 180 days comfortably covers the 90-day retention window
used in the outer SELECT.

The `cursor.execute` call was updated from 2 parameters to 3:

```python
# Before
cursor.execute(retention_query, (start_date, end_date))

# After — start_date passed twice: once for CTE bound, once for outer BETWEEN
cursor.execute(retention_query, (start_date, start_date, end_date))
```

### Task 2 — Comment `first_appointments` CTE in `get_new_clients_monthly()` (docs)

The `first_appointments` CTE is intentionally unfiltered because `MIN(appointment_date)`
must be the all-time first visit. Adding a date filter here would incorrectly classify
existing clients as "new" for any month where their first recorded visit falls within the
filter window.

Added a three-line SQL comment directly above the SELECT to make this intent explicit and
prevent well-meaning future "optimisations" from breaking the metric:

```sql
-- Intentionally unfiltered: MIN(appointment_date) must be the all-time first visit
-- to correctly classify a client as "new" vs "returning" in the given month.
-- Filtering by date here would incorrectly mark existing clients as new.
```

## Commits

| Hash    | Type | Description                                                    |
|---------|------|----------------------------------------------------------------|
| c686b68 | perf | bound client_visits CTE with 180-day lookback window          |
| 2221438 | docs | comment unfiltered first_appointments CTE in get_new_clients_monthly |

## Files Modified

| File | Changes |
|------|---------|
| `repositories/analytics/analytics_repository.py` | +6 lines, -2 lines |

## Success Criteria — Verification Results

- [x] `grep "180 days"` returns line 246 inside `retention_query` CTE
- [x] `grep "cursor.execute(retention_query"` shows 3 params: `(start_date, start_date, end_date)`
- [x] `grep "Intentionally unfiltered"` returns line 819 inside `get_new_clients_monthly`
- [x] `python -c "import repositories.analytics.analytics_repository"` — no error

## Deviations from Plan

None — plan executed exactly as written.
