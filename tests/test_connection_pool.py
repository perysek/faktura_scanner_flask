"""
Tests for connection pooling (config/database.py).

Validates pool initialization, environment variable configuration,
health-checked getconn/putconn lifecycle, and UploadStagingRepository
integration with the shared pool.
"""
import os
from unittest.mock import Mock, patch, MagicMock, PropertyMock

import pytest

from config.database import (
    DatabaseConnection,
    close_pool,
    get_db_connection,
    get_pool,
    initialize_pool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_pool(getconn_return=None):
    """Create a mock ThreadedConnectionPool with sensible defaults."""
    mock_pool = Mock()
    if getconn_return is not None:
        mock_pool.getconn.return_value = getconn_return
    else:
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur
        mock_pool.getconn.return_value = conn
    return mock_pool


# ---------------------------------------------------------------------------
# Test: Pool initialization
# ---------------------------------------------------------------------------

class TestPoolInitialization:
    """Verify initialize_pool() creates a ThreadedConnectionPool."""

    @patch('config.database.ThreadedConnectionPool')
    @patch('config.database.get_database_url', return_value='postgresql://test:test@localhost/test')
    def test_pool_initialization(self, _mock_url, mock_tcp_cls):
        """After initialize_pool(), get_pool() returns the pool instance."""
        import config.database as db_mod

        old_pool = db_mod._pool
        try:
            db_mod._pool = None
            initialize_pool()
            mock_tcp_cls.assert_called_once()
            assert db_mod._pool is mock_tcp_cls.return_value
            # get_pool() should return the same object
            assert get_pool() is mock_tcp_cls.return_value
        finally:
            db_mod._pool = old_pool

    @patch('config.database.ThreadedConnectionPool')
    @patch('config.database.get_database_url', return_value='postgresql://test:test@localhost/test')
    def test_pool_env_defaults(self, _mock_url, mock_tcp_cls):
        """When no env vars set, pool uses defaults: min=2, max=10, connect_timeout=5, statement_timeout=30000."""
        import config.database as db_mod

        # Remove env vars if set
        env_overrides = {
            'DB_POOL_MIN': None,
            'DB_POOL_MAX': None,
            'DB_CONNECT_TIMEOUT': None,
            'DB_STATEMENT_TIMEOUT': None,
        }
        old_pool = db_mod._pool
        try:
            db_mod._pool = None
            with patch.dict(os.environ, {}, clear=False):
                # Ensure our keys are absent
                for key in env_overrides:
                    os.environ.pop(key, None)
                initialize_pool()

            args, kwargs = mock_tcp_cls.call_args
            assert args[0] == 2, f"minconn should be 2, got {args[0]}"
            assert args[1] == 10, f"maxconn should be 10, got {args[1]}"
            assert kwargs['connect_timeout'] == 5
            assert kwargs['options'] == '-c statement_timeout=30000'
        finally:
            db_mod._pool = old_pool

    @patch('config.database.ThreadedConnectionPool')
    @patch('config.database.get_database_url', return_value='postgresql://test:test@localhost/test')
    def test_pool_env_override(self, _mock_url, mock_tcp_cls):
        """When DB_POOL_MIN=5, DB_POOL_MAX=20 set, pool uses those values."""
        import config.database as db_mod

        old_pool = db_mod._pool
        try:
            db_mod._pool = None
            with patch.dict(os.environ, {
                'DB_POOL_MIN': '5',
                'DB_POOL_MAX': '20',
                'DB_CONNECT_TIMEOUT': '10',
                'DB_STATEMENT_TIMEOUT': '60000',
            }):
                initialize_pool()

            args, kwargs = mock_tcp_cls.call_args
            assert args[0] == 5
            assert args[1] == 20
            assert kwargs['connect_timeout'] == 10
            assert kwargs['options'] == '-c statement_timeout=60000'
        finally:
            db_mod._pool = old_pool


# ---------------------------------------------------------------------------
# Test: get_pool() guard
# ---------------------------------------------------------------------------

class TestGetPoolGuard:

    def test_get_pool_raises_when_not_initialized(self):
        """get_pool() raises RuntimeError if pool is None."""
        import config.database as db_mod

        old_pool = db_mod._pool
        try:
            db_mod._pool = None
            with pytest.raises(RuntimeError, match="Connection pool not initialized"):
                get_pool()
        finally:
            db_mod._pool = old_pool


# ---------------------------------------------------------------------------
# Test: close_pool()
# ---------------------------------------------------------------------------

class TestClosePool:

    def test_close_pool_calls_closeall(self):
        """close_pool() calls closeall() and resets _pool to None."""
        import config.database as db_mod

        mock_pool = Mock()
        old_pool = db_mod._pool
        try:
            db_mod._pool = mock_pool
            close_pool()
            mock_pool.closeall.assert_called_once()
            assert db_mod._pool is None
        finally:
            db_mod._pool = old_pool

    def test_close_pool_noop_when_none(self):
        """close_pool() does nothing if pool is already None."""
        import config.database as db_mod

        old_pool = db_mod._pool
        try:
            db_mod._pool = None
            close_pool()  # Should not raise
            assert db_mod._pool is None
        finally:
            db_mod._pool = old_pool


# ---------------------------------------------------------------------------
# Test: get_connection returns from pool
# ---------------------------------------------------------------------------

class TestGetConnectionFromPool:

    def test_get_connection_returns_from_pool(self, app):
        """Within Flask app context, get_db_connection() returns a pooled connection."""
        mock_pool = _make_mock_pool()
        expected_conn = mock_pool.getconn.return_value

        with app.app_context():
            with patch('config.database.get_pool', return_value=mock_pool):
                conn = get_db_connection()
                assert conn is expected_conn
                mock_pool.getconn.assert_called_once()


# ---------------------------------------------------------------------------
# Test: close_connection returns to pool (putconn, not close)
# ---------------------------------------------------------------------------

class TestCloseConnectionReturnsToPool:

    def test_close_connection_calls_putconn(self, app):
        """DatabaseConnection.close_connection() calls putconn, not close."""
        mock_pool = _make_mock_pool()
        mock_conn = mock_pool.getconn.return_value

        with app.app_context():
            with patch('config.database.get_pool', return_value=mock_pool):
                # Simulate a request that obtained a connection
                conn = get_db_connection()
                assert conn is mock_conn

                # Now close (teardown)
                DatabaseConnection.close_connection()
                mock_pool.putconn.assert_called_once_with(mock_conn)
                # Ensure conn.close() was NOT called
                mock_conn.close.assert_not_called()


# ---------------------------------------------------------------------------
# Test: health check replaces dead connection
# ---------------------------------------------------------------------------

class TestHealthCheck:

    def test_health_check_replaces_dead_connection(self, app):
        """If first getconn returns a dead connection, a new one is obtained."""
        dead_conn = Mock()
        dead_cursor = Mock()
        dead_cursor.execute.side_effect = Exception("connection is dead")
        dead_conn.cursor.return_value = dead_cursor

        healthy_conn = Mock()
        healthy_cursor = Mock()
        healthy_conn.cursor.return_value = healthy_cursor

        mock_pool = Mock()
        mock_pool.getconn.side_effect = [dead_conn, healthy_conn]

        with app.app_context():
            with patch('config.database.get_pool', return_value=mock_pool):
                conn = get_db_connection()

                # Dead connection should have been discarded
                mock_pool.putconn.assert_called_once_with(dead_conn, close=True)
                # Returned connection is the healthy one
                assert conn is healthy_conn
                assert mock_pool.getconn.call_count == 2


# ---------------------------------------------------------------------------
# Test: UploadStagingRepository uses shared connection
# ---------------------------------------------------------------------------

class TestUploadStagingUsesSharedConnection:

    def test_upload_staging_uses_shared_connection(self, app):
        """UploadStagingRepository._get_connection returns same connection as get_db_connection."""
        from repositories.upload_staging_repository import UploadStagingRepository

        mock_pool = _make_mock_pool()
        expected_conn = mock_pool.getconn.return_value

        with app.app_context():
            with patch('config.database.get_pool', return_value=mock_pool):
                repo = UploadStagingRepository()
                repo_conn = repo._get_connection()
                shared_conn = get_db_connection()

                # Both should be the same object (from Flask g)
                assert repo_conn is shared_conn
                assert repo_conn is expected_conn
