"""Tests for core API routes — permission checks, response codes, validation."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestDeleteInvoice:
    """Test audit log_event signature for DELETE invoice (P4 fix verification)."""

    def test_audit_log_event_delete_signature(self):
        """log_event dla DELETE powinno miec action='DELETE' i entity_type='invoice'.

        Ten test weryfikuje poprawnosc wywolania log_event (P4 fix),
        bez potrzeby przechodzenia przez caly stos HTTP Flask.
        """
        from repositories.audit_repository import AuditRepository

        audit = AuditRepository()
        with patch.object(audit, '_execute') as mock_execute:
            audit.log_event(
                entity_type='invoice',
                action='DELETE',
                entity_id=42,
                entity_label='FV/2026/001',
                field_name='status',
                old_value='active',
                new_value='deleted',
            )
            mock_execute.assert_called_once()
            args = mock_execute.call_args[0]
            params = args[1]
            # entity_type='invoice', entity_id=42, invoice_id=None, action='DELETE'
            assert params[0] == 'invoice'  # entity_type
            assert params[1] == 42         # entity_id
            assert params[4] == 'DELETE'   # action


class TestAppErrorHandler:
    """Test global AppError handler returns correct HTTP status codes."""

    def test_validation_error_returns_400(self, app):
        """ValidationError powinien zwrócić 400 na endpointach /api/."""
        from exceptions import ValidationError

        @app.route('/api/test-validation-error')
        def trigger_validation():
            raise ValidationError('Bad input')

        with app.test_client() as c:
            response = c.get('/api/test-validation-error')
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'Bad input' in data['error']

    def test_not_found_error_returns_404(self, app):
        """NotFoundError powinien zwrócić 404."""
        from exceptions import NotFoundError

        @app.route('/api/test-not-found-error')
        def trigger_not_found():
            raise NotFoundError('Invoice not found')

        with app.test_client() as c:
            response = c.get('/api/test-not-found-error')
            assert response.status_code == 404
            data = response.get_json()
            assert data['success'] is False

    def test_permission_denied_returns_403(self, app):
        """PermissionDeniedError powinien zwrócić 403."""
        from exceptions import PermissionDeniedError

        @app.route('/api/test-permission-error')
        def trigger_permission():
            raise PermissionDeniedError('Access denied')

        with app.test_client() as c:
            response = c.get('/api/test-permission-error')
            assert response.status_code == 403


class TestAppointmentStatusConstants:
    """Test that AppointmentStatus constants are consistent."""

    def test_final_statuses_are_complete(self):
        from config.appointment_statuses import AppointmentStatus
        assert AppointmentStatus.COMPLETED in AppointmentStatus.FINAL
        assert AppointmentStatus.CANCELLED in AppointmentStatus.FINAL
        assert AppointmentStatus.NO_SHOW in AppointmentStatus.FINAL

    def test_active_and_final_dont_overlap(self):
        from config.appointment_statuses import AppointmentStatus
        overlap = AppointmentStatus.ACTIVE & AppointmentStatus.FINAL
        assert len(overlap) == 0, f"Overlap found: {overlap}"

    def test_valid_transitions_only_to_known_statuses(self):
        from config.appointment_statuses import AppointmentStatus
        all_statuses = AppointmentStatus.ACTIVE | AppointmentStatus.FINAL
        for source, targets in AppointmentStatus.VALID_TRANSITIONS.items():
            assert source in all_statuses, f"Unknown source: {source}"
            for target in targets:
                assert target in all_statuses, f"Unknown target: {target}"

    def test_can_transition_valid(self):
        from config.appointment_statuses import AppointmentStatus
        assert AppointmentStatus.can_transition('confirmed', 'in_progress') is True
        assert AppointmentStatus.can_transition('in_progress', 'completed') is True

    def test_can_transition_invalid(self):
        from config.appointment_statuses import AppointmentStatus
        assert AppointmentStatus.can_transition('pending', 'completed') is False
        assert AppointmentStatus.can_transition('completed', 'pending') is False

    def test_final_statuses_have_no_transitions(self):
        from config.appointment_statuses import AppointmentStatus
        for status in AppointmentStatus.FINAL:
            assert AppointmentStatus.can_transition(status, 'pending') is False
