"""Tests for AppointmentRepository conflict-scan helpers:
get_candidates_for_conflict_scan() and soft_delete_as_superseded() —
back the past-visit reschedule-duplicate scanner on the import page.
"""
from datetime import date
from unittest.mock import Mock, patch

REPO = 'repositories.appointments.appointment_repository'


def _conn(fetchall_result=None, rowcount=1):
    cur = Mock()
    cur.fetchall.return_value = fetchall_result or []
    cur.rowcount = rowcount
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


class TestGetCandidatesForConflictScan:
    def test_builds_expected_query_and_params(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn([{'id': 1}])
        with app.app_context(), patch(f'{REPO}.get_db_connection', return_value=conn):
            result = AppointmentRepository().get_candidates_for_conflict_scan(
                date(2026, 1, 1), date(2026, 3, 31))

        sql, params = cur.execute.call_args.args[0], cur.execute.call_args.args[1]
        assert 'a.is_deleted = FALSE' in sql
        assert "a.status != 'cancelled'" in sql
        assert 'a.appointment_date BETWEEN %s AND %s' in sql
        assert 'aps.is_addon = FALSE' in sql
        assert params == ('2026-01-01', '2026-03-31')
        assert result == [{'id': 1}]

    def test_excludes_cancelled_via_enum_not_hardcoded_literal_in_other_status(self, app):
        # Sanity check the query never blanket-excludes no_show/completed — only cancelled.
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn([])
        with app.app_context(), patch(f'{REPO}.get_db_connection', return_value=conn):
            AppointmentRepository().get_candidates_for_conflict_scan(date(2026, 1, 1), date(2026, 1, 2))
        sql = cur.execute.call_args.args[0]
        assert 'no_show' not in sql
        assert "!= 'completed'" not in sql


class TestSoftDeleteAsSuperseded:
    def test_sets_is_deleted_and_stamps_note(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn(rowcount=1)
        with app.app_context(), patch(f'{REPO}.get_db_connection', return_value=conn), \
             patch(f'{REPO}.safe_commit') as mock_commit:
            result = AppointmentRepository().soft_delete_as_superseded(42, 'Nadpisana przez #99')

        sql, params = cur.execute.call_args.args[0], cur.execute.call_args.args[1]
        assert 'is_deleted = TRUE' in sql
        assert 'deleted_at = CURRENT_TIMESTAMP' in sql
        assert params == ('Nadpisana przez #99', 'Nadpisana przez #99', 42)
        assert result is True
        mock_commit.assert_called_once()

    def test_returns_false_when_no_row_matched(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _conn(rowcount=0)
        with app.app_context(), patch(f'{REPO}.get_db_connection', return_value=conn), \
             patch(f'{REPO}.safe_commit'):
            result = AppointmentRepository().soft_delete_as_superseded(999, 'note')
        assert result is False
