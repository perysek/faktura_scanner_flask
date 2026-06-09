"""Tests for EmployeeRepository permanent (hard) delete — superuser test cleanup.

``hard_delete()`` is destructive: it removes the employee row plus its absence /
balance data (and that data's audit history) and emits a DELETE audit entry.
``count_blocking_references()`` is the pre-flight guard that keeps RESTRICT-protected
``appointments`` / ``income_records`` intact by letting the route refuse first.

Real EmployeeRepository against a mocked connection. Two AuditRepository import
sites are patched: the mixin's (``repositories.auditable``) and the balance-history
cleanup's (``repositories.employees.employee_repository``).
"""
from unittest.mock import MagicMock, patch


def _conn(*, fetchone=None, rowcount=1):
    cursor = MagicMock()
    cursor.rowcount = rowcount
    cursor.fetchone.return_value = fetchone   # None ⇒ "row not found"
    conn = MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__.return_value = conn        # `with get_db_connection() as conn`
    return conn, cursor


class TestCountBlockingReferences:
    def test_returns_restrict_counts(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, _ = _conn(fetchone={'appointments': 2, 'income_records': 3})
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                out = EmployeeRepository().count_blocking_references(7)
                assert out == {'appointments': 2, 'income_records': 3}


class TestHardDelete:
    def test_emits_delete_audit_and_returns_true(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, _ = _conn(fetchone={'first_name': 'Test', 'last_name': 'User'}, rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.employees.employee_repository.AuditRepository'), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = EmployeeRepository().hard_delete(5)
                assert ok is True
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['entity_type'] == 'employee'
                assert kw['action'] == 'DELETE'
                assert kw['entity_id'] == 5
                assert kw['entity_label'] == 'Test User'

    def test_wipes_balance_history_then_absences_then_employee(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(fetchone={'first_name': 'Test', 'last_name': 'User'}, rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.employees.employee_repository.AuditRepository') as MockBal, \
                 patch('repositories.auditable.AuditRepository'):
                EmployeeRepository().hard_delete(5)
                # balance audit history wiped while limit/adjustment rows still exist
                MockBal.return_value.delete_for_employee_balance.assert_called_once_with(5)
                executed = ' '.join(str(c.args[0]) for c in cursor.execute.call_args_list)
                assert 'DELETE FROM employee_absences' in executed
                assert 'DELETE FROM employees' in executed

    def test_returns_false_and_no_audit_when_not_found(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, _ = _conn(fetchone=None, rowcount=0)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.employees.employee_repository.AuditRepository') as MockBal, \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = EmployeeRepository().hard_delete(999)
                assert ok is False
                MockBal.return_value.delete_for_employee_balance.assert_not_called()
                MockAudit.return_value.safe_log_event.assert_not_called()
