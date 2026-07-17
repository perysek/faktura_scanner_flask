"""
Shared "real capacity" engine for occupancy/utilisation KPIs — used by the
KPI matrix (repositories/analytics/kpi_matrix_repository.py) and the main
analytics dashboard (repositories/analytics/analytics_repository.py).

Replaces the old crude model (today's active headcount × a flat
`max_appointments_per_day` × calendar days) with:

  - **Historical headcount**: `employees.hire_date` / `termination_date`
    range-checked per day, not today's `is_active` snapshot — an employee
    who left in March still counts for January/February capacity, and one
    hired in October doesn't inflate January's.
  - **Real per-weekday working hours** from `employees.work_schedule`, via
    `utils/work_schedule.py` (the same source of truth the booking flow
    validates against) — not a flat "N appointments/day" guess.
  - **Approved absences subtracted per day** — whole-day absence rows
    remove that day's scheduled hours; hour-slot rows subtract exactly the
    booked-off hours. Pending/rejected/cancelled absences don't count.

Everything is expressed in **hours**, not "appointment slots" — a slot
count was never a real physical unit (self-reported ceiling, not derived
from anything). Booked demand is therefore also measured in hours
(`SUM(appointments.total_duration) / 60`), so both sides of any ratio
share a unit.

All lookups are bulk-fetched (employees range-check + one absences query),
not per-employee round-trips.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from config.database import DatabaseConnection
from config.admin_view import emp_exclusion_sql_inline
from utils.work_schedule import WEEKDAY_KEYS, work_hours_for_day

DailyHours = Dict[date, float]


def _employees_active_during(start_date: date, end_date: date) -> List[Dict]:
    """Employees whose employment overlapped [start_date, end_date] at all.

    `hire_date`/`termination_date` are both nullable — and in this app's
    real data, `hire_date` is NULL for almost every employee (rows were
    bulk-created during a Feb-Jun 2026 data migration; `created_at` reflects
    when the DB row was created, not when the person actually started
    working the floor — real appointment history goes back to 2024). A
    NULL `hire_date` therefore means "unknown, assume always employed"
    (open-ended on the start side, exactly like a NULL `termination_date`
    already means open-ended on the end side) — NOT "hired on the
    migration date". Falling back to `created_at` would silently zero out
    capacity for every historical month before the migration.
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, work_schedule, hire_date, termination_date
        FROM employees
        WHERE (hire_date IS NULL OR hire_date <= %s)
          AND (termination_date IS NULL OR termination_date >= %s)
          {emp_exclusion_sql_inline('id')}
    """, (end_date, start_date))
    return [dict(r) for r in cursor.fetchall()]


def _scheduled_hours_by_day(employee: Dict, start_date: date, end_date: date) -> DailyHours:
    """Per-day scheduled hours from `work_schedule`, clipped to the
    employee's employment window intersected with [start_date, end_date].
    Every day in range gets an entry (0.0 for off-days / outside
    employment) so downstream month-bucketing never has to guess at gaps.
    """
    emp_start = start_date if employee['hire_date'] is None else max(start_date, employee['hire_date'])
    emp_end = end_date if employee['termination_date'] is None else min(end_date, employee['termination_date'])

    out: DailyHours = {}
    d = start_date
    while d <= end_date:
        hours = 0.0
        if emp_start <= d <= emp_end:
            window = work_hours_for_day(employee['work_schedule'], WEEKDAY_KEYS[d.weekday()])
            if window:
                start_t, end_t = window
                hours = ((end_t.hour * 60 + end_t.minute) - (start_t.hour * 60 + start_t.minute)) / 60.0
        out[d] = hours
        d += timedelta(days=1)
    return out


def _all_approved_absences(employee_ids: List[int], start_date: date, end_date: date) -> Dict[int, List[Dict]]:
    """Bulk-fetch approved, non-deleted absences overlapping the range for
    every given employee in one query (no N+1)."""
    if not employee_ids:
        return {}
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    placeholders = ','.join(['%s'] * len(employee_ids))
    cursor.execute(f"""
        SELECT employee_id, date_from, date_to, time_from, time_to
        FROM employee_absences
        WHERE employee_id IN ({placeholders})
          AND status = 'approved'
          AND is_deleted = FALSE
          AND date_from <= %s AND date_to >= %s
    """, (*employee_ids, end_date, start_date))
    out: Dict[int, List[Dict]] = {}
    for row in cursor.fetchall():
        out.setdefault(row['employee_id'], []).append(dict(row))
    return out


def _subtract_absences(daily_hours: DailyHours, absences: List[Dict],
                        start_date: date, end_date: date) -> DailyHours:
    """Whole-day rows (`time_from IS NULL`) zero out that day's scheduled
    hours entirely; hour-slot rows subtract exactly `time_to - time_from`,
    clamped so a day never goes negative."""
    out = dict(daily_hours)
    for row in absences:
        af, at = row['date_from'], row['date_to']
        tf, tt = row['time_from'], row['time_to']
        if tf is None or tt is None:
            d = max(af, start_date)
            last = min(at, end_date)
            while d <= last:
                if d in out:
                    out[d] = 0.0
                d += timedelta(days=1)
        else:
            if start_date <= af <= end_date and af in out:
                hours = ((tt.hour * 60 + tt.minute) - (tf.hour * 60 + tf.minute)) / 60.0
                out[af] = max(0.0, out[af] - hours)
    return out


def get_daily_capacity(start_date: date, end_date: date) -> Dict[int, DailyHours]:
    """`{employee_id: {date: available_hours_after_absences}}` for every
    employee employed at any point in [start_date, end_date]."""
    employees = _employees_active_during(start_date, end_date)
    absences_by_emp = _all_approved_absences([e['id'] for e in employees], start_date, end_date)

    result: Dict[int, DailyHours] = {}
    for emp in employees:
        scheduled = _scheduled_hours_by_day(emp, start_date, end_date)
        result[emp['id']] = _subtract_absences(scheduled, absences_by_emp.get(emp['id'], []), start_date, end_date)
    return result


def get_booked_hours_by_employee_day(start_date: date, end_date: date) -> Dict[int, DailyHours]:
    """`{employee_id: {date: booked_hours}}` from completed appointments'
    real duration (`total_duration`), for the same range."""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT employee_id, appointment_date,
               COALESCE(SUM(total_duration), 0) / 60.0 AS hours
        FROM appointments
        WHERE status = 'completed'
          AND appointment_date BETWEEN %s AND %s
          {emp_exclusion_sql_inline('employee_id')}
        GROUP BY employee_id, appointment_date
    """, (start_date, end_date))
    result: Dict[int, DailyHours] = {}
    for row in cursor.fetchall():
        result.setdefault(row['employee_id'], {})[row['appointment_date']] = float(row['hours'])
    return result


def sum_hours(daily: Dict[int, DailyHours]) -> float:
    """Total hours across every employee and every day."""
    return sum(v for per_emp in daily.values() for v in per_emp.values())


def bucket_by_month(daily: Dict[int, DailyHours]) -> Dict[int, float]:
    """Sum across all employees, grouped by calendar month (1-12). Assumes
    the input covers a single year."""
    out: Dict[int, float] = {}
    for per_emp in daily.values():
        for d, v in per_emp.items():
            out[d.month] = out.get(d.month, 0.0) + v
    return out


def bucket_by_employee_month(daily: Dict[int, DailyHours]) -> Dict[Tuple[int, int], float]:
    """`(employee_id, month) -> summed hours`. Assumes a single year."""
    out: Dict[Tuple[int, int], float] = {}
    for emp_id, per_day in daily.items():
        for d, v in per_day.items():
            key = (emp_id, d.month)
            out[key] = out.get(key, 0.0) + v
    return out
