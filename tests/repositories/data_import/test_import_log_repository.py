"""
Tests for ImportLogRepository — CRUD + status transitions + orphan cleanup.
Uses the mock_db fixture from tests/conftest.py.
safe_commit is patched to avoid Flask application context requirement.
"""
import json
import pytest
from datetime import date
from unittest.mock import Mock, patch


@pytest.fixture(autouse=True)
def patch_safe_commit():
    """Patch safe_commit so it doesn't call flask.g.is_in_transaction."""
    with patch('repositories.data_import.import_log_repository.safe_commit'):
        yield


class TestImportLogRepository:

    def test_create_inserts_running_row(self, mock_db):
        mock_db.cursor.fetchone.return_value = {'id': 42}
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()

        new_id = repo.create(
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            dry_run=False,
            triggered_by_user_id=7,
        )

        assert new_id == 42
        sql = mock_db.cursor.execute.call_args[0][0]
        params = mock_db.cursor.execute.call_args[0][1]
        assert 'INSERT INTO import_logs' in sql
        assert '%s' in sql
        assert '?' not in sql
        assert 7 in params

    def test_update_stats_replaces_jsonb(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.update_stats(42, {'inserted': 10, 'skipped': 2})
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE import_logs' in sql
        assert 'stats' in sql

    def test_mark_completed_sets_finished_at(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.mark_completed(42, {'inserted': 50})
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE import_logs' in sql
        assert 'completed' in sql
        assert 'finished_at' in sql

    def test_mark_failed_records_error(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.mark_failed(42, 'Playwright timeout', stats={'errors': 1})
        sql = mock_db.cursor.execute.call_args[0][0]
        params = mock_db.cursor.execute.call_args[0][1]
        assert 'Playwright timeout' in params
        assert 'error_message' in sql

    def test_find_running_returns_row_or_none(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()

        mock_db.cursor.fetchone.return_value = {'id': 99, 'status': 'running'}
        assert repo.find_running() == {'id': 99, 'status': 'running'}

        mock_db.cursor.fetchone.return_value = None
        assert repo.find_running() is None

    def test_has_running_import(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()

        mock_db.cursor.fetchone.return_value = {'1': 1}
        assert repo.has_running_import() is True

        mock_db.cursor.fetchone.return_value = None
        assert repo.has_running_import() is False

    def test_get_recent_joins_users(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.get_recent(limit=20)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'LEFT JOIN users' in sql
        assert 'ORDER BY' in sql
        assert 'LIMIT %s' in sql

    def test_get_history_has_triggered_by_name(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.get_history(limit=20)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'triggered_by_name' in sql
        assert 'LEFT JOIN users' in sql

    def test_cleanup_orphans_returns_count(self, mock_db):
        mock_db.cursor.rowcount = 3
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        count = repo.cleanup_orphans()
        assert count == 3
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE import_logs' in sql
        assert 'failed' in sql
        assert 'running' in sql

    def test_update_session_status_validates_value(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        with pytest.raises(ValueError):
            repo.update_session_status(42, 'garbage')

    def test_mark_cancelled(self, mock_db):
        from repositories.data_import.import_log_repository import ImportLogRepository
        repo = ImportLogRepository()
        repo.mark_cancelled(42)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'cancelled' in sql
        assert 'finished_at' in sql
