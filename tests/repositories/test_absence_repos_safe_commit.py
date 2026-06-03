"""
Guard tests for the safe_commit migration of the absence repositories (#7).

The five absence repos were converted from raw ``conn.commit()`` (inside a
``with get_db_connection() as conn:`` block that also auto-committed on exit) to
the ``BaseRepository`` shape (``conn = get_db_connection(); ...; safe_commit(conn)``).
These tests lock that in for the three "sibling" repos that have no managed
transaction wrapping them yet: a write must DEFER its commit inside an enclosing
``managed_transaction`` and commit exactly once at block exit. A future revert to
``conn.commit()`` would re-break atomicity silently — and fail these tests.

One representative write per repo (the simplest signature) is enough: every
migrated write now shares the identical commit shape.
"""
from unittest.mock import Mock, patch

from config.database import managed_transaction


def _conn_with_rowcount(rowcount=1):
    cursor = Mock()
    cursor.rowcount = rowcount
    conn = Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


class TestAbsenceSiblingReposDeferCommit:
    """Each sibling repo's write defers to an enclosing managed_transaction."""

    def test_supervisor_add_link_defers_commit(self, app):
        from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository

        with app.app_context():
            conn, cursor = _conn_with_rowcount(1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                repo = EmployeeSupervisorRepository()
                with managed_transaction():
                    repo.add_link(employee_id=1, supervisor_employee_id=2)
                    cursor.execute.assert_called_once()   # INSERT issued...
                    conn.commit.assert_not_called()        # ...commit deferred
                conn.commit.assert_called_once()           # one commit at txn exit
                conn.rollback.assert_not_called()

    def test_absence_respond_defers_commit(self, app):
        from repositories.absences.absence_repository import AbsenceRepository

        with app.app_context():
            conn, cursor = _conn_with_rowcount(1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                repo = AbsenceRepository()
                with managed_transaction():
                    repo.respond(absence_id=1, status='approved', approver_id=2)
                    conn.commit.assert_not_called()
                conn.commit.assert_called_once()

    def test_category_soft_delete_defers_commit(self, app):
        from repositories.absences.absence_category_repository import AbsenceCategoryRepository

        with app.app_context():
            conn, cursor = _conn_with_rowcount(1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                repo = AbsenceCategoryRepository()
                with managed_transaction():
                    repo.soft_delete(category_id=1)
                    conn.commit.assert_not_called()
                conn.commit.assert_called_once()

    def test_supervisor_add_link_commits_immediately_outside_transaction(self, app):
        """Behaviour-preserving: outside a transaction the write still commits now."""
        from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository

        with app.app_context():
            conn, cursor = _conn_with_rowcount(1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                EmployeeSupervisorRepository().add_link(employee_id=1, supervisor_employee_id=2)
                conn.commit.assert_called_once()
