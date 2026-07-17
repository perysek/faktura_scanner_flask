"""Tests for AbsenceRepository.count_pending_for_approver() — backs the
sidebar pending-absences pill (context processor, app.py) shown to
supervisors on every page render.
"""
from unittest.mock import Mock, patch


def _ctx_conn(cnt):
    cur = Mock()
    cur.fetchone.return_value = {'cnt': cnt}
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


GDC = 'repositories.absences.absence_repository.get_db_connection'


class TestCountPendingForApprover:
    def test_returns_count_from_row(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn(3)
        with app.app_context(), patch(GDC, return_value=conn):
            result = AbsenceRepository().count_pending_for_approver(7)
        assert result == 3
        sql, params = cur.execute.call_args.args
        assert "status = 'pending'" in sql
        assert "is_deleted = FALSE" in sql
        assert params[0] == 7

    def test_zero_when_no_row(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        cur = Mock()
        cur.fetchone.return_value = None
        conn = Mock()
        conn.cursor.return_value = cur
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        with app.app_context(), patch(GDC, return_value=conn):
            result = AbsenceRepository().count_pending_for_approver(7)
        assert result == 0
