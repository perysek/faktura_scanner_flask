"""Widok administratora filtering in AppointmentRepository.

Locks in that the emp_exclusion_sql choke-point actually reaches the appointment
view queries (NOT IN clause emitted, hidden ids bound) when a hidden set exists,
and stays a no-op — with correct param ordering around LIMIT/OFFSET — when it
doesn't. hidden_ids_to_exclude is patched to simulate "admin view OFF, one hidden
employee" (returns ids) vs "admin view ON" (returns ()).
"""
from unittest.mock import Mock, patch
from datetime import date

REPO = 'repositories.appointments.appointment_repository'


def _conn(fetchall=None):
    cur = Mock()
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.fetchone.return_value = None
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


def _hidden(ids):
    """Patch the choke-point's hidden set + the repo's DB connection."""
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


class TestGetByDateRange:
    def test_excludes_hidden_employee(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn()
        with app.app_context(), _hidden((9,)), \
                patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().get_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
        sql, params = cur.execute.call_args.args[0], cur.execute.call_args.args[1]
        assert 'a.employee_id NOT IN' in sql
        assert 9 in list(params)

    def test_no_clause_when_admin_view_on(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn()
        with app.app_context(), _hidden(()), \
                patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().get_by_date_range(date(2026, 1, 1), date(2026, 1, 31))
        assert 'NOT IN' not in cur.execute.call_args.args[0]


class TestGetLatestParamOrder:
    def test_hidden_params_precede_limit_offset(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn()
        with app.app_context(), _hidden((9,)), \
                patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().get_latest(limit=50, offset=20)
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'a.employee_id NOT IN' in sql
        # LIMIT/OFFSET are the last two bound params; the hidden id sits before them
        assert params[-2:] == [50, 20]
        assert params[-3] == 9


class TestDailySchedule:
    def test_excludes_hidden_employee(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn()
        with app.app_context(), _hidden((9,)), \
                patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().get_daily_schedule(3, date(2026, 1, 15))
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'a.employee_id NOT IN' in sql
        assert params[-1] == 9


class TestMultiEmployeeSchedule:
    def test_employee_set_excludes_hidden(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        # No employees returned → the bulk appointments query is skipped; we only
        # need to inspect the first (employee-selection) execute call.
        conn, cur = _conn(fetchall=[])
        with app.app_context(), _hidden((9,)), \
                patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().get_multi_employee_schedule(date(2026, 1, 15))
        sql = cur.execute.call_args_list[0].args[0]
        params = list(cur.execute.call_args_list[0].args[1])
        assert 'e.id NOT IN' in sql
        assert 9 in params
