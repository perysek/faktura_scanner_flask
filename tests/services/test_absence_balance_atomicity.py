"""
Atomicity tests for the absence-balance audit path (improvement #7).

Background: the absence repos used to call raw ``conn.commit()`` inside a
``with get_db_connection() as conn:`` block, which committed the data write
*immediately* and ignored any enclosing ``managed_transaction``. That made the
balance-service audit non-atomic — a leave-balance change could commit while its
audit row was lost. The repos were migrated to ``safe_commit(conn)`` (so writes
defer to an enclosing transaction), and the four balance-service mutations
(``set_limit`` / ``remove_limit`` / ``create_adjustment`` / ``delete_adjustment``)
now wrap their data write + audit row in one ``managed_transaction``.

These tests prove the migration actually achieved deferral + atomicity. They use
REAL repositories against a mocked connection so ``safe_commit`` suppression is
genuinely exercised; only the connection (and, where noted, the audit write) is
mocked.

Key fact that makes this work: both ``get_db_connection()`` (used by the absence
repos) and ``DatabaseConnection.get_connection()`` (used by managed_transaction
and by AuditRepository via BaseRepository) resolve to the SAME per-request
``g.db`` connection — so all writes share one transaction and one commit.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from config.database import managed_transaction


def _mock_conn(row_id=7):
    """A mock connection whose cursor.fetchone() yields a RETURNING-id row.

    Uses MagicMock for the connection so reads that still use
    ``with get_db_connection() as conn:`` (e.g. set_limit's pre-read) work — the
    context manager returns the same connection and does NOT auto-commit (the mock
    __exit__ is a no-op, unlike a real psycopg2 connection)."""
    cursor = Mock()
    cursor.fetchone.return_value = {'id': row_id}
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.cursor.return_value = cursor
    return conn, cursor


class TestAbsenceRepoSafeCommitMigration:
    """The repo writes now defer to an enclosing managed_transaction, and still
    commit immediately when there is none (behaviour-preserving outside a txn)."""

    def test_limit_upsert_defers_commit_inside_transaction(self, app):
        from repositories.absences.absence_limit_repository import AbsenceLimitRepository
        from database.models import EmployeeAbsenceLimit

        with app.app_context():
            conn, cursor = _mock_conn(row_id=7)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                repo = AbsenceLimitRepository()
                limit = EmployeeAbsenceLimit(employee_id=1, category_id=2,
                                             max_value=26, notes=None, created_by=1)
                with managed_transaction():
                    rid = repo.upsert(limit)
                    assert rid == 7
                    cursor.execute.assert_called_once()   # INSERT was issued...
                    conn.commit.assert_not_called()        # ...but commit deferred
                conn.commit.assert_called_once()           # one commit at txn exit
                conn.rollback.assert_not_called()

    def test_limit_upsert_commits_immediately_outside_transaction(self, app):
        from repositories.absences.absence_limit_repository import AbsenceLimitRepository
        from database.models import EmployeeAbsenceLimit

        with app.app_context():
            conn, cursor = _mock_conn(row_id=9)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                repo = AbsenceLimitRepository()
                repo.upsert(EmployeeAbsenceLimit(employee_id=1, category_id=2,
                                                 max_value=26, notes=None, created_by=1))
                conn.commit.assert_called_once()           # immediate commit, as before

    def test_adjustment_create_defers_commit_inside_transaction(self, app):
        from repositories.absences.absence_adjustment_repository import AbsenceAdjustmentRepository
        from database.models import AbsenceBalanceAdjustment

        with app.app_context():
            conn, cursor = _mock_conn(row_id=55)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                repo = AbsenceAdjustmentRepository()
                adj = AbsenceBalanceAdjustment(employee_id=1, category_id=2,
                                               delta_value=5.0, reason='korekta',
                                               period_label=None, created_by=1)
                with managed_transaction():
                    new_id = repo.create(adj)
                    assert new_id == 55
                    conn.commit.assert_not_called()        # deferred inside the txn
                conn.commit.assert_called_once()


class TestBalanceServiceAtomicity:
    """The headline guarantee: a leave-balance mutation and its audit row commit
    together, or roll back together. Real AbsenceBalanceService + real repos
    against a mocked connection; only the connection (and, in the failure test,
    the audit write) is mocked."""

    def test_create_adjustment_commits_once_on_success(self, app):
        from services.absence_balance_service import AbsenceBalanceService

        with app.app_context():
            conn, cursor = _mock_conn(row_id=55)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                svc = AbsenceBalanceService()
                adj_id = svc.create_adjustment(
                    employee_id=1, category_id=2, delta_value=5.0,
                    reason='korekta roczna', period_label=None, created_by=1,
                    employee_name='Jan Kowalski', category_name='Urlop',
                )
                assert adj_id == 55
                # adjustment INSERT + audit INSERT both issued on the shared conn...
                assert cursor.execute.call_count >= 2
                # ...and committed exactly once, together.
                conn.commit.assert_called_once()
                conn.rollback.assert_not_called()

    def test_create_adjustment_audit_failure_rolls_back_the_adjustment(self, app):
        from services.absence_balance_service import AbsenceBalanceService

        with app.app_context():
            conn, cursor = _mock_conn(row_id=55)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                svc = AbsenceBalanceService()
                # Force the audit write to fail AFTER the adjustment insert ran.
                svc.audit_repo.log_event = Mock(side_effect=Exception("audit_log INSERT failed"))

                with pytest.raises(Exception, match="audit_log INSERT failed"):
                    svc.create_adjustment(
                        employee_id=1, category_id=2, delta_value=5.0,
                        reason='korekta', period_label=None, created_by=1,
                        employee_name='Jan Kowalski', category_name='Urlop',
                    )

                # The adjustment INSERT was issued on the shared connection...
                assert cursor.execute.called
                # ...but the whole transaction rolled back — the balance change is
                # undone, so there is no "balance moved, nobody logged it" state.
                conn.rollback.assert_called_once()
                conn.commit.assert_not_called()

    def test_set_limit_audit_failure_rolls_back_the_limit(self, app):
        from services.absence_balance_service import AbsenceBalanceService

        with app.app_context():
            conn, cursor = _mock_conn(row_id=7)
            # set_limit reads the existing limit first (returns None = no prior limit),
            # then the upsert inside the transaction returns the new id.
            cursor.fetchone.side_effect = [None, {'id': 7}]
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                svc = AbsenceBalanceService()
                svc.audit_repo.log_event = Mock(side_effect=Exception("audit down"))

                with pytest.raises(Exception, match="audit down"):
                    svc.set_limit(
                        employee_id=1, category_id=2, max_value=26.0,
                        notes=None, created_by=1,
                        employee_name='Jan', category_name='Urlop',
                    )

                conn.rollback.assert_called_once()
                conn.commit.assert_not_called()
