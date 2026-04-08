"""
Shared pytest fixtures for FakturaScanner Flask tests.

Provides:
    - Flask app factory with test config
    - Authenticated test client
    - Mock database connection
"""
import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def app():
    """Create Flask application with test configuration.

    Patches initialize_database() so tests don't need a real DB connection.
    """
    import os
    os.environ['FLASK_ENV'] = 'development'
    os.environ['SECRET_KEY'] = 'test-secret-key'
    os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')

    # Patch pool + DB initialization before importing app to prevent real connection
    with patch('config.database.initialize_pool', return_value=None), \
         patch('config.database.initialize_database', return_value=None):
        from app import create_app
        app = create_app()
        app.config['TESTING'] = True
        yield app


@pytest.fixture
def client(app):
    """Flask test client (unauthenticated)."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database connection and cursor.

    Usage:
        def test_something(mock_db):
            mock_db.cursor.fetchall.return_value = [{'id': 1}]
            # ... your test code
    """
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor

    with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
        yield type('MockDB', (), {
            'connection': mock_conn,
            'cursor': mock_cursor,
        })()


@pytest.fixture
def mock_db_connection():
    """Mock get_db_connection context manager (used by AppointmentRepository etc).

    Usage:
        def test_something(mock_db_connection):
            mock_db_connection.cursor.fetchall.return_value = [...]
    """
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)

    with patch('config.database.get_db_connection', return_value=mock_conn):
        yield type('MockDB', (), {
            'connection': mock_conn,
            'cursor': mock_cursor,
        })()
