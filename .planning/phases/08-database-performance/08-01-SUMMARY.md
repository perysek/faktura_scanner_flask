---
phase: 08-database-performance
plan: 01
subsystem: database
tags: [index, performance, alembic, postgresql, SCAL-01]
dependency_graph:
  requires: [i3j4k5l6m7n8 (add_pending_to_appointment_status_check migration)]
  provides: [idx_appointments_employee_id]
  affects: [appointments table query plans for WHERE employee_id = %s]
tech_stack:
  added: []
  patterns: [Alembic manual migration, offline SQL generation for validation]
key_files:
  created:
    - alembic/versions/j4k5l6m7n8o9_add_employee_id_index.py
  modified: []
decisions:
  - "Used offline SQL generation (alembic upgrade --sql) to validate migration syntax when SSH tunnel to Vultr was unavailable"
metrics:
  duration: ~10 minutes
  completed: 2026-04-08
---

# Phase 08 Plan 01: Add Missing Employee_id Single-Column Index Summary

## One-liner

Single-column `idx_appointments_employee_id` index on `appointments(employee_id)` added via Alembic migration `j4k5l6m7n8o9` branching from `i3j4k5l6m7n8`, closing the SCAL-01 gap not covered by the existing composite `(employee_id, appointment_date)` index.

## What was implemented

Created Alembic migration `j4k5l6m7n8o9` that adds `idx_appointments_employee_id` — a dedicated single-column index on `appointments.employee_id`. This covers standalone `WHERE employee_id = %s` queries that do not filter by date, for which the composite `idx_appointments_employee_date (employee_id, appointment_date)` from migration `d5e6f7a8b9c0` requires a full index scan.

The migration file includes an `upgrade()` docstring that lists all indexes satisfying SCAL-01 across prior migrations for full traceability:

- `0c648f58079b`: `idx_appointments_date_employee`, `idx_appointments_status`, `idx_appointments_date`, `idx_income_appointment`
- `d5e6f7a8b9c0`: `idx_appointments_status_date`, `idx_appointments_employee_date`
- `j4k5l6m7n8o9` (this migration): `idx_appointments_employee_id`

## Commit hashes

| Commit   | Description                                              |
|----------|----------------------------------------------------------|
| a206f0a  | feat(08-01): add appointments.employee_id index for SCAL-01 |

## Files created/modified

| File                                                                 | Action  |
|----------------------------------------------------------------------|---------|
| alembic/versions/j4k5l6m7n8o9_add_employee_id_index.py              | Created |

## Verification

Task 2 (live DB verification) requires an active SSH tunnel to the Vultr server (local port 5433 → Vultr port 5432). The tunnel was not available during execution.

Offline validation was performed instead using `alembic upgrade j4k5l6m7n8o9 --sql`, which generated correct SQL:

```sql
CREATE INDEX idx_appointments_employee_id ON appointments (employee_id);
UPDATE alembic_version SET version_num='j4k5l6m7n8o9' WHERE alembic_version.version_num = 'i3j4k5l6m7n8';
```

The full migration chain (all 20+ migrations from `001` to `j4k5l6m7n8o9`) was validated end-to-end in offline mode with zero errors.

To apply when the tunnel is open:
```bash
ssh -i ssh_vultr -N -L 5433:localhost:5432 root@<VULTR_IP>
# (in another terminal)
cd C:/Projects/faktura_scanner_flask
alembic upgrade head
```

## Success criteria check

- [x] File `alembic/versions/j4k5l6m7n8o9_add_employee_id_index.py` exists
- [x] `idx_appointments_employee_id` appears in both `upgrade()` and `downgrade()`
- [x] `down_revision = 'i3j4k5l6m7n8'` confirmed
- [x] `alembic upgrade --sql` (offline) completes without error and generates correct DDL
- [ ] `alembic upgrade head` (live) — deferred: SSH tunnel to Vultr required

## Deviations from plan

**[Rule 3 - Blocking issue] Used offline SQL validation instead of live DB run**

- **Found during:** Task 2
- **Issue:** The `.env.local` DATABASE_URL points to port 5433 (SSH tunnel port) which was not active. Local PostgreSQL on port 5432 rejected the placeholder password `choose_a_strong_password_here`. No live DB connection was possible without establishing the SSH tunnel.
- **Fix:** Validated migration correctness using `alembic upgrade j4k5l6m7n8o9 --sql` in offline mode, which proved the migration generates correct DDL and chains correctly in the migration graph. Live application is deferred to when the SSH tunnel is available.
- **Impact:** None on file deliverable. Migration file is complete and correct. Live `alembic upgrade head` will apply it without modification.
