"""Tests for permanent (hard) delete of absences and absence categories.

Superuser-only cleanup, mirroring the employees permanent-delete. Covers:
  * AbsenceService.hard_delete()          — removes an absence of any status, marks
                                            approved ones as slots-freed, audits.
  * AbsenceService.hard_delete_category() — purges a soft-deleted category, refusing
                                            when still active or still referenced by
                                            absences (FK RESTRICT), audits.
  * Repo methods defer their commit inside an enclosing managed_transaction and
    issue the expected DELETE statement.
"""
from unittest.mock import Mock, patch

import pytest

from config.database import managed_transaction


def _svc_with_mocks():
    from services.absence_service import AbsenceService
    svc = AbsenceService()
    svc.absence_repo = Mock()
    svc.category_repo = Mock()
    svc.employee_repo = Mock()
    svc.audit_repo = Mock()
    svc.employee_repo.get_by_id.return_value = {'first_name': 'Jan', 'last_name': 'Kowalski'}
    return svc


def _conn_with_rowcount(rowcount=1):
    cursor = Mock()
    cursor.rowcount = rowcount
    conn = Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


class TestServiceHardDeleteAbsence:
    def test_approved_reports_slots_freed_and_audits(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = {
                'status': 'approved', 'employee_id': 5, 'category_name': 'L4',
                'date_from': '2026-06-01', 'date_to': '2026-06-03',
            }
            svc.absence_repo.hard_delete.return_value = True
            with patch('config.database.DatabaseConnection.get_connection',
                       return_value=_conn_with_rowcount()[0]):
                out = svc.hard_delete(42, deleted_by=9)
            assert out == {'status': 'approved', 'slots_freed': True}
            svc.absence_repo.hard_delete.assert_called_once_with(42)
            kw = svc.audit_repo.log_event.call_args.kwargs
            assert kw['entity_type'] == 'absence'
            assert kw['action'] == 'DELETE_PERMANENT'
            assert kw['entity_id'] == 42

    def test_pending_no_slots_freed(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = {
                'status': 'pending', 'employee_id': 5, 'category_name': 'Urlop',
                'date_from': '2026-06-01', 'date_to': '2026-06-01',
            }
            svc.absence_repo.hard_delete.return_value = True
            with patch('config.database.DatabaseConnection.get_connection',
                       return_value=_conn_with_rowcount()[0]):
                out = svc.hard_delete(7)
            assert out['slots_freed'] is False

    def test_missing_absence_raises_and_no_delete(self, app):
        from services.absence_service import AbsenceError
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = None
            with pytest.raises(AbsenceError):
                svc.hard_delete(999)
            svc.absence_repo.hard_delete.assert_not_called()
            svc.audit_repo.log_event.assert_not_called()


class TestServiceHardDeleteCategory:
    def test_refuses_when_referenced_by_absences(self, app):
        from services.absence_service import AbsenceError
        with app.app_context():
            svc = _svc_with_mocks()
            svc.category_repo.get_by_id.return_value = {'is_deleted': True, 'name': 'L4'}
            svc.category_repo.count_absence_references.return_value = 3
            with pytest.raises(AbsenceError) as ei:
                svc.hard_delete_category(2)
            assert '3' in str(ei.value)
            svc.category_repo.hard_delete.assert_not_called()
            svc.audit_repo.log_event.assert_not_called()

    def test_refuses_when_still_active(self, app):
        from services.absence_service import AbsenceError
        with app.app_context():
            svc = _svc_with_mocks()
            svc.category_repo.get_by_id.return_value = {'is_deleted': False, 'name': 'L4'}
            with pytest.raises(AbsenceError):
                svc.hard_delete_category(2)
            svc.category_repo.count_absence_references.assert_not_called()
            svc.category_repo.hard_delete.assert_not_called()

    def test_purges_soft_deleted_unreferenced_and_audits(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.category_repo.get_by_id.return_value = {'is_deleted': True, 'name': 'Stara'}
            svc.category_repo.count_absence_references.return_value = 0
            svc.category_repo.hard_delete.return_value = True
            with patch('config.database.DatabaseConnection.get_connection',
                       return_value=_conn_with_rowcount()[0]):
                svc.hard_delete_category(2, deleted_by=9)
            svc.category_repo.hard_delete.assert_called_once_with(2)
            kw = svc.audit_repo.log_event.call_args.kwargs
            assert kw['entity_type'] == 'absence_category'
            assert kw['action'] == 'DELETE_PERMANENT'
            assert kw['entity_id'] == 2


class TestRepoHardDeletesDeferCommit:
    def test_absence_hard_delete_issues_delete_and_defers_commit(self, app):
        from repositories.absences.absence_repository import AbsenceRepository
        with app.app_context():
            conn, cursor = _conn_with_rowcount(1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                with managed_transaction():
                    assert AbsenceRepository().hard_delete(1) is True
                    conn.commit.assert_not_called()
                conn.commit.assert_called_once()
            assert 'DELETE FROM employee_absences' in cursor.execute.call_args.args[0]

    def test_category_hard_delete_issues_delete_and_defers_commit(self, app):
        from repositories.absences.absence_category_repository import AbsenceCategoryRepository
        with app.app_context():
            conn, cursor = _conn_with_rowcount(1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                with managed_transaction():
                    assert AbsenceCategoryRepository().hard_delete(1) is True
                    conn.commit.assert_not_called()
                conn.commit.assert_called_once()
            assert 'DELETE FROM absence_categories' in cursor.execute.call_args.args[0]
