"""Tests for EmailService — connection, disconnect, error handling."""
import imaplib
import logging
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


class TestEmailServiceCredentialMasking:
    """IMPR-06: Email credentials must not appear in log output."""

    def test_connect_failure_does_not_log_password(self, caplog):
        """When IMAP login fails, password must not appear in log."""
        service = EmailService()
        test_password = 'SuperSecret123!'
        with patch('services.email_service.imaplib.IMAP4_SSL') as mock_imap:
            mock_instance = Mock()
            mock_instance.login.side_effect = imaplib.IMAP4.error('LOGIN failed')
            mock_imap.return_value = mock_instance
            with caplog.at_level(logging.DEBUG):
                result = service.connect('test@example.com', test_password, 'imap.example.com', 993)
        assert result is False
        assert test_password not in caplog.text

    def test_connect_imap_error_returns_false(self, caplog):
        """connect() catches imaplib.IMAP4.error specifically and returns False."""
        service = EmailService()
        with patch('services.email_service.imaplib.IMAP4_SSL') as mock_imap:
            mock_instance = Mock()
            mock_instance.login.side_effect = imaplib.IMAP4.error('LOGIN failed')
            mock_imap.return_value = mock_instance
            with caplog.at_level(logging.DEBUG):
                result = service.connect('test@example.com', 'pass', 'imap.example.com', 993)
        assert result is False
        assert service.connected is False

    def test_connect_os_error_returns_false(self, caplog):
        """connect() catches OSError specifically and returns False."""
        service = EmailService()
        with patch('services.email_service.imaplib.IMAP4_SSL') as mock_imap:
            mock_imap.side_effect = OSError('Connection refused')
            with caplog.at_level(logging.DEBUG):
                result = service.connect('test@example.com', 'pass', 'imap.example.com', 993)
        assert result is False
        assert service.connected is False


class TestEmailServiceSpecificExceptions:
    """FIX-03: All catch blocks use specific exception types."""

    def test_extract_email_body_text_catches_unicode_decode_error(self):
        """_extract_email_body_text() catches UnicodeDecodeError (not bare except)."""
        from email.message import Message
        # Simulate a multipart message where decoding fails
        msg = Message()
        msg.set_payload([])
        msg['Content-Type'] = 'multipart/mixed'

        # Should return empty string without raising
        result = EmailService._extract_email_body_text(msg)
        assert isinstance(result, str)

    def test_extract_email_body_text_returns_empty_on_attribute_error(self):
        """_extract_email_body_text() returns empty string on AttributeError (malformed message)."""
        result = EmailService._extract_email_body_text(None)
        assert result == ''

    def test_fetch_pdf_attachments_catches_imap_error_per_folder(self):
        """fetch_pdf_attachments() catches imaplib.IMAP4.error per folder and continues."""
        service = EmailService()
        service.connected = True
        mock_imap = Mock()
        service.imap = mock_imap
        # First folder raises IMAP error, second one succeeds
        mock_imap.select.side_effect = [
            imaplib.IMAP4.error('Folder not accessible'),
            None,
        ]
        # Second folder returns no emails
        mock_imap.search.return_value = ('OK', [b''])
        result = service.fetch_pdf_attachments(folders=['INBOX', 'Sent'])
        # Should not raise and should return a list
        assert isinstance(result, list)

    def test_no_bare_except_blocks(self):
        """email_service.py must have zero bare except: blocks."""
        import inspect
        import re
        from services import email_service
        source = inspect.getsource(email_service)
        bare_excepts = re.findall(r'^\s*except\s*:', source, re.MULTILINE)
        assert len(bare_excepts) == 0, f"Found {len(bare_excepts)} bare except: blocks"

    def test_no_print_calls(self):
        """email_service.py must use logging, not print()."""
        import inspect
        import re
        from services import email_service
        source = inspect.getsource(email_service)
        lines = source.split('\n')
        print_lines = [
            line for line in lines
            if re.search(r'^\s+print\(', line) and not line.strip().startswith('#')
        ]
        assert len(print_lines) == 0, f"Found {len(print_lines)} print() calls: {print_lines}"


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
