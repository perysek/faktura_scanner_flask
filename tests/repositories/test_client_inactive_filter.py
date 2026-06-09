"""Tests for ClientRepository.get_clients_with_stats include_inactive flag.

The clients list hid deactivated clients because this query hardcoded
``AND c.is_active = TRUE``. The "Wszyscy / Aktywni" toggle passes
``include_inactive=True`` to drop that filter so deactivated clients become
visible (and their Edit action — hence reactivation — reachable). Soft-deleted
clients stay excluded in both modes.
"""
from unittest.mock import Mock, patch


def _conn():
    cur = Mock()
    cur.fetchall.return_value = []
    conn = Mock()
    conn.cursor.return_value = cur
    return conn, cur


class TestIncludeInactiveFilter:
    def test_active_only_by_default(self, app):
        from repositories.clients.client_repository import ClientRepository
        with app.app_context():
            conn, cur = _conn()
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                ClientRepository().get_clients_with_stats()
            sql = cur.execute.call_args.args[0]
            assert 'c.is_active = TRUE' in sql
            assert 'c.is_deleted = FALSE' in sql

    def test_include_inactive_drops_active_filter(self, app):
        from repositories.clients.client_repository import ClientRepository
        with app.app_context():
            conn, cur = _conn()
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                ClientRepository().get_clients_with_stats(include_inactive=True)
            sql = cur.execute.call_args.args[0]
            assert 'c.is_active = TRUE' not in sql
            # soft-deleted clients are still excluded regardless of the flag
            assert 'c.is_deleted = FALSE' in sql

    def test_search_params_unaffected_by_flag(self, app):
        from repositories.clients.client_repository import ClientRepository
        with app.app_context():
            conn, cur = _conn()
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                ClientRepository().get_clients_with_stats('Kowalski', include_inactive=True)
            # 4 ILIKE params for the search term, no extra params from the flag
            assert len(cur.execute.call_args.args[1]) == 4
