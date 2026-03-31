"""
Tests for InvoiceRepository and ClientRepository soft-delete filtering.

Verifies that ALL custom query methods exclude soft-deleted records
(i.e., SQL contains 'is_deleted = FALSE').
"""
import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock


# ---------------------------------------------------------------------------
# InvoiceRepository tests
# ---------------------------------------------------------------------------

class TestSoftDelete:
    """Every custom InvoiceRepository query must filter by is_deleted = FALSE."""

    def test_search_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.search("test")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"search() missing is_deleted filter: {sql}"

    def test_get_by_date_range_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.get_by_date_range(date(2026, 1, 1), date(2026, 12, 31))
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_by_date_range() missing is_deleted filter: {sql}"

    def test_get_by_seller_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.get_by_seller(1)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_by_seller() missing is_deleted filter: {sql}"

    def test_find_by_invoice_number_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = None
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.find_by_invoice_number("FV/001")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"find_by_invoice_number() missing is_deleted filter: {sql}"

    def test_find_by_invoice_number_and_seller_with_nip_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = None
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.find_by_invoice_number_and_seller("FV/001", seller_nip="1234567890")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"find_by_invoice_number_and_seller(nip) missing is_deleted filter: {sql}"
        )

    def test_find_by_invoice_number_and_seller_with_name_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = None
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.find_by_invoice_number_and_seller("FV/001", seller_name="Test Sp. z o.o.")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"find_by_invoice_number_and_seller(name) missing is_deleted filter: {sql}"
        )

    def test_get_recent_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.get_recent(5)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_recent() missing is_deleted filter: {sql}"

    def test_get_upcoming_payments_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.get_upcoming_payments(5)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_upcoming_payments() missing is_deleted filter: {sql}"
        )

    def test_get_overdue_payments_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.get_overdue_payments(5)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_overdue_payments() missing is_deleted filter: {sql}"
        )

    def test_get_statistics_all_queries_exclude_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = {
            'total_count': 0,
            'paid_count': 0,
            'unpaid_count': 0
        }
        mock_db.cursor.fetchall.return_value = []
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.get_statistics()
        for call in mock_db.cursor.execute.call_args_list:
            sql = call[0][0]
            assert 'is_deleted = FALSE' in sql, (
                f"get_statistics() query missing is_deleted filter: {sql}"
            )


class TestAuditAfterDelete:
    """Soft-delete must use UPDATE not DELETE FROM."""

    def test_soft_delete_preserves_row_for_audit(self, mock_db):
        mock_db.cursor.rowcount = 1
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        result = repo.delete(1)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE' in sql, f"delete() should use UPDATE, got: {sql}"
        assert 'is_deleted = TRUE' in sql, f"delete() should set is_deleted = TRUE, got: {sql}"
        assert 'DELETE FROM' not in sql, f"delete() must not use DELETE FROM, got: {sql}"
        assert result is True


# ---------------------------------------------------------------------------
# ClientRepository tests
# ---------------------------------------------------------------------------

class TestClientSoftDelete:
    """Every custom ClientRepository query must filter by is_deleted = FALSE."""

    def test_client_search_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.search("anna")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"search() missing is_deleted filter: {sql}"

    def test_client_search_by_name_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.search_by_name("kowalski")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"search_by_name() missing is_deleted filter: {sql}"

    def test_client_search_by_phone_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.search_by_phone("604")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"search_by_phone() missing is_deleted filter: {sql}"

    def test_client_find_by_email_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = None
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.find_by_email("test@example.com")
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"find_by_email() missing is_deleted filter: {sql}"

    def test_client_get_active_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.get_active_clients()
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_active_clients() missing is_deleted filter: {sql}"

    def test_client_get_recent_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.get_recent_clients(10)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_recent_clients() missing is_deleted filter: {sql}"

    def test_client_get_upcoming_birthdays_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.get_upcoming_birthdays(30)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_upcoming_birthdays() missing is_deleted filter: {sql}"
        )

    def test_client_get_clients_without_recent_visits_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchall.return_value = []
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.get_clients_without_recent_visits(90)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_clients_without_recent_visits() missing is_deleted filter: {sql}"
        )

    def test_client_get_statistics_excludes_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = {
            'total_clients': 0,
            'active_clients': 0,
            'inactive_clients': 0,
            'recent_visitors': 0,
            'clients_with_birthdate': 0,
        }
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository()
        repo.get_statistics()
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_statistics() missing is_deleted filter: {sql}"


# ---------------------------------------------------------------------------
# TestPartialUniqueConstraint (Plan 02)
# ---------------------------------------------------------------------------

class TestPartialUniqueConstraint:
    """Verify soft-deleted invoices don't block duplicate detection."""

    def test_find_by_invoice_number_returns_none_for_deleted(self, mock_db):
        """After soft-delete, find_by_invoice_number returns None (query filters is_deleted=FALSE)."""
        mock_db.cursor.fetchone.return_value = None
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        result = repo.find_by_invoice_number("FV/2026/001")
        assert result is None
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql

    def test_find_by_invoice_number_and_seller_nip_returns_none_for_deleted(self, mock_db):
        mock_db.cursor.fetchone.return_value = None
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        result = repo.find_by_invoice_number_and_seller("FV/2026/001", seller_nip="1234567890")
        assert result is None
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql


# ---------------------------------------------------------------------------
# TestAuditDeleteVerification — FIX-01 (Plan 02)
# ---------------------------------------------------------------------------

class TestAuditDeleteVerification:
    """FIX-01: Verify DELETE audit logging call pattern."""

    def test_audit_log_event_uses_correct_action(self):
        from repositories.audit_repository import AuditRepository
        audit = AuditRepository()
        with patch.object(audit, '_execute') as mock_exec:
            audit.log_event(
                entity_type='invoice', action='DELETE', entity_id=42,
                entity_label='FV/2026/001', field_name='status',
                old_value='active', new_value='deleted',
            )
            mock_exec.assert_called_once()
            sql = mock_exec.call_args[0][0]
            params = mock_exec.call_args[0][1]
            assert 'INSERT' in sql.upper() and 'audit' in sql.lower()
            assert 'DELETE' in params, f"action='DELETE' not in params: {params}"

    def test_audit_log_event_includes_entity_label(self):
        from repositories.audit_repository import AuditRepository
        audit = AuditRepository()
        with patch.object(audit, '_execute') as mock_exec:
            audit.log_event(
                entity_type='invoice', action='DELETE', entity_id=42,
                entity_label='FV/2026/001',
            )
            mock_exec.assert_called_once()
            params = mock_exec.call_args[0][1]
            assert 'FV/2026/001' in params


# ---------------------------------------------------------------------------
# TestFKConstraintResolution — FIX-02 (Plan 02)
# ---------------------------------------------------------------------------

class TestFKConstraintResolution:
    """FIX-02: Verify soft delete does not trigger CASCADE or FK violations."""

    def test_soft_delete_uses_update_not_delete(self, mock_db):
        mock_db.cursor.rowcount = 1
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.delete(42)
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'UPDATE' in sql.upper()
        assert 'DELETE FROM' not in sql.upper()
        assert 'is_deleted = TRUE' in sql
        assert 'deleted_at = CURRENT_TIMESTAMP' in sql

    def test_soft_delete_does_not_cascade(self, mock_db):
        mock_db.cursor.rowcount = 1
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository()
        repo.delete(99)
        assert mock_db.cursor.execute.call_count == 1
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'duplicate_detection' not in sql.lower()
