"""
Tests for the AuditableMixin rollout to EmployeeRepository (improvement #7 Step 3).

EmployeeRepository was standalone (raw conn.commit + `with get_db_connection()`),
so this rollout had two parts:
  1. migrate its writes to safe_commit (so audit can be atomic inside a
     managed_transaction, and the raw-commit trap is gone);
  2. mix in AuditableMixin and emit 'employee' audit rows on real mutations —
     create / update / deactivate / activate / terminate_employee — which carry
     salary data (base_salary, employer_cost_rate) and were previously UNAUDITED.

Real EmployeeRepository against a mocked connection; AuditRepository is patched to
inspect the emitted audit payload (and to silence the audit write in the
commit-deferral test).
"""
from unittest.mock import Mock, patch

from config.database import managed_transaction


def _conn(*, fetchone=None, rowcount=1):
    cursor = Mock()
    cursor.rowcount = rowcount
    if fetchone is not None:
        cursor.fetchone.return_value = fetchone
    conn = Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


def _employee(**over):
    from database.models import Employee
    base = dict(first_name='Jan', last_name='Kowalski')
    base.update(over)
    return Employee(**base)


class TestEmployeeRepoSafeCommitMigration:
    """The migrated write defers its commit inside a managed_transaction."""

    def test_create_defers_commit_inside_transaction(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(fetchone={'id': 3})
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository'):  # silence audit write
                repo = EmployeeRepository()
                with managed_transaction():
                    assert repo.create(_employee()) == 3
                    conn.commit.assert_not_called()   # deferred inside the txn
                conn.commit.assert_called_once()       # single commit at txn exit

    def test_create_commits_immediately_outside_transaction(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(fetchone={'id': 4})
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository'):
                EmployeeRepository().create(_employee())
                conn.commit.assert_called_once()       # immediate commit, as before


class TestEmployeeRepoAuditWiring:
    """Real employee mutations emit an 'employee' audit row; non-mutations don't."""

    def test_create_emits_employee_create_audit(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(fetchone={'id': 3})
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                EmployeeRepository().create(_employee(first_name='Anna', last_name='Nowak'))
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['entity_type'] == 'employee'
                assert kw['action'] == 'CREATE'
                assert kw['entity_id'] == 3
                assert kw['entity_label'] == 'Anna Nowak'

    def test_update_emits_audit_when_changed(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = EmployeeRepository().update(5, _employee(base_salary=8000))
                assert ok is True
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['entity_type'] == 'employee'
                assert kw['action'] == 'UPDATE'
                assert kw['entity_id'] == 5

    def test_deactivate_emits_is_active_audit(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                EmployeeRepository().deactivate(5)
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['action'] == 'UPDATE'
                assert kw['field_name'] == 'is_active'
                assert kw['new_value'] == 'false'

    def test_terminate_emits_status_audit(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                EmployeeRepository().terminate_employee(5)
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['action'] == 'UPDATE'
                assert kw['field_name'] == 'employment_status'
                assert kw['new_value'] == 'terminated'

    def test_no_audit_when_no_row_changed(self, app):
        from repositories.employees.employee_repository import EmployeeRepository

        with app.app_context():
            conn, cursor = _conn(rowcount=0)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = EmployeeRepository().deactivate(999)
                assert ok is False
                MockAudit.return_value.safe_log_event.assert_not_called()
