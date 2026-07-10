"""Widok administratora filtering in the employee selection lists + service pickers.

The owner's employee must vanish from every picker / list / stat feed
(/employees, calendar dropdown, direct-report chooser, "who can do this service")
while admin view is OFF, so they don't exist for anyone by default.
"""
from unittest.mock import Mock, patch


def _ctx_conn():
    cur = Mock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = {'cnt': 0}
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


def _hidden(ids):
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


EMP = 'repositories.employees.employee_repository.get_db_connection'
ES = 'repositories.employees.employee_service_repository.get_db_connection'


class TestEmployeeLists:
    def test_get_all_active_excludes_owner(self, app):
        from repositories.employees.employee_repository import EmployeeRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(EMP, return_value=conn):
            EmployeeRepository().get_all(active_only=True)
        assert 'id NOT IN (9)' in cur.execute.call_args.args[0]

    def test_get_all_inactive_branch_excludes_owner(self, app):
        from repositories.employees.employee_repository import EmployeeRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(EMP, return_value=conn):
            EmployeeRepository().get_all(active_only=False)
        sql = cur.execute.call_args.args[0]
        assert 'WHERE TRUE' in sql and 'id NOT IN (9)' in sql

    def test_search_excludes_owner(self, app):
        from repositories.employees.employee_repository import EmployeeRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(EMP, return_value=conn):
            EmployeeRepository().search('Kowalski')
        assert 'id NOT IN (9)' in cur.execute.call_args.args[0]

    def test_statistics_excludes_owner(self, app):
        from repositories.employees.employee_repository import EmployeeRepository
        conn, cur = _ctx_conn()
        cur.fetchone.return_value = {
            'total_employees': 0, 'active_employees': 0, 'employed': 0,
            'on_leave': 0, 'terminated': 0, 'linked_to_users': 0, 'avg_salary': None,
        }
        with app.app_context(), _hidden((9,)), patch(EMP, return_value=conn):
            EmployeeRepository().get_statistics()
        assert 'id NOT IN (9)' in cur.execute.call_args.args[0]

    def test_no_filter_when_admin_view_on(self, app):
        from repositories.employees.employee_repository import EmployeeRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden(()), patch(EMP, return_value=conn):
            EmployeeRepository().get_all(active_only=True)
        assert 'NOT IN' not in cur.execute.call_args.args[0]


class TestEmployeeServicePickers:
    def test_employees_for_service_excludes_owner(self, app):
        from repositories.employees.employee_service_repository import EmployeeServiceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(ES, return_value=conn):
            EmployeeServiceRepository().get_employees_for_service(4)
        assert 'e.id NOT IN (9)' in cur.execute.call_args.args[0]

    def test_services_for_employee_defense_filter(self, app):
        from repositories.employees.employee_service_repository import EmployeeServiceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), patch(ES, return_value=conn):
            EmployeeServiceRepository().get_services_for_employee(9)
        assert 'es.employee_id NOT IN (9)' in cur.execute.call_args.args[0]


class TestEmployeeRouteGuard:
    def test_is_employee_hidden_true_for_owner_when_off(self, app):
        from config import admin_view
        with app.test_request_context():
            with patch('config.admin_view.hidden_ids_to_exclude', return_value=(9,)):
                assert admin_view.is_employee_hidden(9) is True
                assert admin_view.is_employee_hidden(4) is False

    def test_is_employee_hidden_false_when_admin_view_on(self, app):
        from config import admin_view
        with app.test_request_context():
            with patch('config.admin_view.hidden_ids_to_exclude', return_value=()):
                assert admin_view.is_employee_hidden(9) is False
