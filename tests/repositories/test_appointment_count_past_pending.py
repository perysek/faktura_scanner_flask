"""Tests for AppointmentRepository.count_past_pending_appointments() — backs
the sidebar past-pending-visits pill (context processor, app.py) shown to
users with write access to the appointments module.
"""
from unittest.mock import Mock, patch

REPO = 'repositories.appointments.appointment_repository'


def _conn(cnt):
    cur = Mock()
    cur.fetchone.return_value = {'cnt': cnt}
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


def _hidden(ids):
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


class TestCountPastPendingAppointments:
    def test_returns_count_from_row(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn(4)
        with app.app_context(), _hidden(()), patch(f'{REPO}.get_db_connection', return_value=conn):
            result = AppointmentRepository().count_past_pending_appointments()
        assert result == 4
        sql = cur.execute.call_args.args[0]
        assert '(a.appointment_date + a.end_time) < NOW()' in sql
        assert "a.status NOT IN ('completed', 'cancelled', 'no_show')" in sql
        assert 'a.is_deleted = FALSE' in sql

    def test_zero_when_no_row(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        cur = Mock()
        cur.fetchone.return_value = None
        conn = Mock()
        conn.cursor.return_value = cur
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        with app.app_context(), _hidden(()), patch(f'{REPO}.get_db_connection', return_value=conn):
            result = AppointmentRepository().count_past_pending_appointments()
        assert result == 0

    def test_excludes_hidden_employee(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn(2)
        with app.app_context(), _hidden((9,)), patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().count_past_pending_appointments()
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'a.employee_id NOT IN' in sql
        assert 9 in params
