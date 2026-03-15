"""Tests for EmailService — connection, disconnect, error handling."""
import imaplib
import pytest
from unittest.mock import Mock, patch, MagicMock

from services.email_service import EmailService


class TestEmailServiceConnect:
    """Test IMAP connection handling."""

    def setup_method(self):
        self.service = EmailService()

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_connect_success(self, mock_imap_class):
        """Poprawne dane logowania powinny ustawić connected=True."""
        mock_imap = Mock()
        mock_imap_class.return_value = mock_imap

        result = self.service.connect('test@example.com', 'pass', 'imap.example.com', 993)

        assert result is True
        assert self.service.connected is True
        mock_imap.login.assert_called_once_with('test@example.com', 'pass')

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_connect_failure_sets_connected_false(self, mock_imap_class):
        """Błąd połączenia powinien ustawić connected=False."""
        mock_imap_class.side_effect = Exception("Connection refused")

        result = self.service.connect('test@example.com', 'pass', 'bad-server', 993)

        assert result is False
        assert self.service.connected is False

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_connect_login_failure(self, mock_imap_class):
        """Błędne hasło powinno zwrócić False."""
        mock_imap = Mock()
        mock_imap.login.side_effect = imaplib.IMAP4.error("LOGIN failed")
        mock_imap_class.return_value = mock_imap

        result = self.service.connect('test@example.com', 'wrong', 'imap.example.com', 993)

        assert result is False
        assert self.service.connected is False


class TestEmailServiceDisconnect:
    """Test disconnect with specific exception handling (P3 fix)."""

    def setup_method(self):
        self.service = EmailService()

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_disconnect_success(self, mock_imap_class):
        """Poprawne rozłączenie powinno ustawić connected=False."""
        mock_imap = Mock()
        mock_imap_class.return_value = mock_imap
        self.service.imap = mock_imap
        self.service.connected = True

        self.service.disconnect()

        assert self.service.connected is False
        mock_imap.logout.assert_called_once()

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_disconnect_on_imap_error_still_sets_disconnected(self, mock_imap_class):
        """IMAP error during disconnect should still set connected=False."""
        mock_imap = Mock()
        mock_imap.logout.side_effect = imaplib.IMAP4.error("Connection broken")
        self.service.imap = mock_imap
        self.service.connected = True

        self.service.disconnect()

        assert self.service.connected is False

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_disconnect_on_os_error_still_sets_disconnected(self, mock_imap_class):
        """OSError during disconnect should still set connected=False."""
        mock_imap = Mock()
        mock_imap.logout.side_effect = OSError("Network is unreachable")
        self.service.imap = mock_imap
        self.service.connected = True

        self.service.disconnect()

        assert self.service.connected is False

    def test_disconnect_when_not_connected_is_noop(self):
        """Disconnect gdy nie połączony nie powinno rzucić wyjątku."""
        self.service.connected = False
        self.service.imap = None

        self.service.disconnect()  # should not raise

        assert self.service.connected is False


class TestEmailServiceTestConnection:
    """Test static test_connection method."""

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_connection_success(self, mock_imap_class):
        """Poprawne ustawienia powinny zwrócić True."""
        mock_imap = Mock()
        mock_imap_class.return_value = mock_imap

        settings = {
            'imap_server': 'imap.example.com',
            'imap_port': 993,
            'email_address': 'test@example.com',
            'password': 'pass',
        }

        assert EmailService.test_connection(settings) is True
        mock_imap.login.assert_called_once()
        mock_imap.logout.assert_called_once()

    @patch('services.email_service.imaplib.IMAP4_SSL')
    def test_connection_failure(self, mock_imap_class):
        """Błąd połączenia powinien zwrócić False."""
        mock_imap_class.side_effect = Exception("Connection refused")

        settings = {
            'imap_server': 'bad-server',
            'imap_port': 993,
            'email_address': 'test@example.com',
            'password': 'pass',
        }

        assert EmailService.test_connection(settings) is False


class TestEmailSettings:
    """Test email settings env var priority (P5 fix)."""

    @patch.dict('os.environ', {'IMAP_EMAIL': 'env@test.com', 'IMAP_PASSWORD': 'env-pass'})
    def test_env_vars_override_json(self, tmp_path):
        """Env vars powinny mieć priorytet nad JSON config."""
        from config.email_settings import EmailSettings

        settings_instance = EmailSettings()
        # Force re-load to pick up env vars
        settings = settings_instance.load_settings()

        assert settings['email'] == 'env@test.com'
        assert settings['password'] == 'env-pass'

    def test_save_settings_excludes_password(self, tmp_path):
        """Hasło nie powinno być zapisywane do pliku JSON."""
        import json
        from config.email_settings import EmailSettings

        instance = EmailSettings()
        instance.config_file = tmp_path / 'email_config.json'

        instance.save_settings({
            'email': 'test@test.com',
            'password': 'secret123',
            'imap_server': 'imap.test.com',
            'imap_port': 993,
        })

        # Read the saved file
        with open(instance.config_file, 'r') as f:
            saved = json.load(f)

        assert 'password' not in saved
        assert saved['email'] == 'test@test.com'
        assert saved['imap_server'] == 'imap.test.com'
