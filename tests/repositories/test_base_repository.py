"""
Tests for BaseRepository DatabaseConnectionError wrapping.

Verifies that psycopg2.OperationalError and psycopg2.InterfaceError are
wrapped into DatabaseConnectionError for all 4 query methods, while
other psycopg2 exceptions pass through unmodified.
"""
import psycopg2
import pytest
from unittest.mock import Mock, patch

from repositories.base_repository import BaseRepository
from exceptions import DatabaseConnectionError


class TestDatabaseConnectionErrorWrapping:
    def setup_method(self):
        self.repo = BaseRepository('test_table')

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_execute_raises_on_operational_error(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.OperationalError("connection refused")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError) as exc_info:
            self.repo._execute("SELECT 1")
        assert "OperationalError" in str(exc_info.value)

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_execute_raises_on_interface_error(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.InterfaceError("connection closed")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError) as exc_info:
            self.repo._execute("SELECT 1")
        assert "InterfaceError" in str(exc_info.value)

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_fetch_one_raises_on_operational_error(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.OperationalError("connection refused")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError):
            self.repo._fetch_one("SELECT 1")

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_fetch_all_raises_on_interface_error(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.InterfaceError("connection closed")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError):
            self.repo._fetch_all("SELECT 1")

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_execute_insert_raises_on_operational_error(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.OperationalError("connection refused")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError):
            self.repo._execute_insert("INSERT INTO test_table (name) VALUES (%s)", ("x",))

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_execute_does_not_wrap_programming_error(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError("syntax error")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(psycopg2.ProgrammingError):
            self.repo._execute("INVALID SQL")

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_execute_exception_is_chained(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        original_error = psycopg2.OperationalError("connection refused")
        mock_cursor.execute.side_effect = original_error
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError) as exc_info:
            self.repo._execute("SELECT 1")
        assert exc_info.value.__cause__ is original_error

    @patch('repositories.base_repository.DatabaseConnection.get_connection')
    def test_execute_error_message_contains_type_name_not_raw_details(self, mock_get_conn):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.OperationalError("raw internal details")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(DatabaseConnectionError) as exc_info:
            self.repo._execute("SELECT 1")
        message = str(exc_info.value)
        # Message should contain the error type name
        assert "OperationalError" in message
        # Message should NOT expose raw internal error details
        assert "raw internal details" not in message
