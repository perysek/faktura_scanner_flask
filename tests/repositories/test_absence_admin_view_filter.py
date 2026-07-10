"""Widok administratora filtering across the absence repositories.

The owner's absences must not appear in an approver's queue, the admin/calendar
absence feed, the owner's own "Moje nieobecności" list, or the leave-balance
summary while admin view is OFF.
"""
from unittest.mock import Mock, patch


def _ctx_conn():
    cur = Mock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


def _hidden(ids):
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


ABS = 'repositories.absences.absence_repository.get_db_connection'
BAL = 'repositories.absences.absence_balance_repository.get_db_connection'


class TestAbsenceLists:
    def test_list_for_employee_hides_owner(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(ABS, return_value=conn):
            AbsenceRepository().list_for_employee(9, status_in=['approved'])
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'ea.employee_id NOT IN' in sql
        assert 9 in params

    def test_list_for_approver_hides_owner_requests(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(ABS, return_value=conn):
            AbsenceRepository().list_for_approver(3)
        assert 'ea.employee_id NOT IN' in cur.execute.call_args.args[0]

    def test_list_all_hides_owner(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(ABS, return_value=conn):
            AbsenceRepository().list_all(status_in=['approved'])
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'ea.employee_id NOT IN' in sql
        assert 9 in params

    def test_list_all_unfiltered_when_admin_view_on(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden(()), patch(ABS, return_value=conn):
            AbsenceRepository().list_all(status_in=['approved'])
        assert 'employee_id NOT IN' not in cur.execute.call_args.args[0]


class TestBalanceSummary:
    def test_bulk_summary_excludes_owner(self, app):
        from repositories.absences.absence_balance_repository import AbsenceBalanceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(BAL, return_value=conn):
            AbsenceBalanceRepository().bulk_summary_for_list()
        assert 'e.id NOT IN (9)' in cur.execute.call_args.args[0]
