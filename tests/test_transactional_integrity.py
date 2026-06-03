"""
Tests for transactional integrity of multi-step appointment operations.

Verifies that managed_transaction wraps multiple repo calls so that
a failure at any step rolls back ALL previous steps — no partial state.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from flask import g

from config.database import managed_transaction, safe_commit, is_in_transaction


class TestSafeCommit:
    """Verify safe_commit respects the _in_transaction flag."""

    def test_safe_commit_commits_when_not_in_transaction(self, app):
        """Outside managed_transaction, safe_commit calls conn.commit()."""
        with app.app_context():
            mock_conn = Mock()
            safe_commit(mock_conn)
            mock_conn.commit.assert_called_once()

    def test_safe_commit_skips_when_in_transaction(self, app):
        """Inside managed_transaction, safe_commit is a no-op."""
        with app.app_context():
            g._in_transaction = True
            mock_conn = Mock()
            safe_commit(mock_conn)
            mock_conn.commit.assert_not_called()
            g._in_transaction = False


class TestManagedTransaction:
    """Verify managed_transaction sets/clears flag and handles commit/rollback."""

    def test_sets_and_clears_flag(self, app):
        """g._in_transaction is True inside, False after."""
        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                assert not is_in_transaction()
                with managed_transaction():
                    assert is_in_transaction()
                assert not is_in_transaction()

    def test_commits_on_success(self, app):
        """Clean exit triggers commit, not rollback."""
        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                with managed_transaction():
                    pass
                mock_conn.commit.assert_called_once()
                mock_conn.rollback.assert_not_called()

    def test_rolls_back_on_exception(self, app):
        """Exception triggers rollback, not commit."""
        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                with pytest.raises(ValueError):
                    with managed_transaction():
                        raise ValueError("mid-operation failure")
                mock_conn.rollback.assert_called_once()
                mock_conn.commit.assert_not_called()

    def test_clears_flag_on_exception(self, app):
        """Even after exception, flag is cleared."""
        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                with pytest.raises(ValueError):
                    with managed_transaction():
                        raise ValueError("failure")
                assert not is_in_transaction()


class TestCreateAppointmentTransaction:
    """Verify create_appointment rolls back on service insertion failure."""

    @patch('services.appointment_service.PricingService')
    @patch('services.appointment_service.AppointmentServiceRepository')
    @patch('services.appointment_service.AppointmentRepository')
    @patch('services.appointment_service.IncomeRepository')
    @patch('services.appointment_service.ClientRepository')
    @patch('services.appointment_service.ServiceAddonRepository')
    @patch('services.appointment_service.EmployeeServiceRepository')
    def test_rolls_back_on_service_failure(self, mock_emp_svc, mock_addon,
                                            mock_client, mock_income,
                                            mock_appt, mock_appt_svc,
                                            mock_pricing, app):
        """If add_service fails, the created appointment is rolled back."""
        from services.appointment_service import AppointmentBusinessService
        from datetime import date, time

        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                svc = AppointmentBusinessService()

                # Pre-transaction validators added by later features (working-hours
                # guard, absence-conflict check) are out of scope for this rollback
                # test and depend on un-mocked repos — stub them so the flow reaches
                # the managed_transaction block we actually want to exercise.
                svc._validate_working_hours = Mock(return_value=None)
                svc.absence_repo = Mock()
                svc.absence_repo.check_absence_conflicts.return_value = []

                # Setup pricing
                svc.pricing.calculate_appointment_total.return_value = {
                    'total_price': Decimal('100'),
                    'total_duration': 60,
                    'breakdown': [
                        {'service_id': 1, 'effective_price': Decimal('50'),
                         'effective_duration': 30, 'effective_commission': Decimal('0.1'),
                         'commission_amount': Decimal('5')},
                        {'service_id': 2, 'effective_price': Decimal('50'),
                         'effective_duration': 30, 'effective_commission': Decimal('0.1'),
                         'commission_amount': Decimal('5')},
                    ]
                }
                svc.appt_repo.check_conflicts.return_value = []
                svc.appt_repo.check_client_conflicts.return_value = []
                svc.appt_repo.create.return_value = 42

                # Second service insertion fails
                svc.appt_svc_repo.add_service.side_effect = [None, Exception("DB error")]

                with pytest.raises(Exception, match="DB error"):
                    svc.create_appointment(
                        client_id=1, employee_id=1,
                        service_ids=[1, 2],
                        appt_date=date(2026, 1, 15),
                        start_time=time(10, 0)
                    )

                # Transaction should have rolled back
                mock_conn.rollback.assert_called_once()
                mock_conn.commit.assert_not_called()


class TestCompleteAppointmentTransaction:
    """Verify complete_appointment rolls back on status update failure."""

    @patch('services.appointment_service.PricingService')
    @patch('services.appointment_service.AppointmentServiceRepository')
    @patch('services.appointment_service.AppointmentRepository')
    @patch('services.appointment_service.IncomeRepository')
    @patch('services.appointment_service.ClientRepository')
    @patch('services.appointment_service.ServiceAddonRepository')
    @patch('services.appointment_service.EmployeeServiceRepository')
    def test_rolls_back_on_status_update_failure(self, mock_emp_svc, mock_addon,
                                                   mock_client, mock_income,
                                                   mock_appt, mock_appt_svc,
                                                   mock_pricing, app):
        """If update_status fails after income creation, income is rolled back."""
        from services.appointment_service import AppointmentBusinessService
        from datetime import date, time, datetime

        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                svc = AppointmentBusinessService()

                # Setup appointment data (in the past)
                svc.appt_repo.get_by_id.return_value = {
                    'status': 'in_progress',
                    'client_id': 1,
                    'employee_id': 1,
                    'appointment_date': date(2026, 1, 10),
                    'start_time': time(10, 0),
                    'discount_amount': 0,
                }
                svc.income_repo.get_by_appointment.return_value = None
                svc.appt_svc_repo.get_appointment_totals.return_value = {
                    'total_price': Decimal('100'),
                    'total_commission': Decimal('10'),
                    'main_total': Decimal('100'),
                    'addon_total': Decimal('0'),
                    'addon_count': 0,
                }
                svc.income_repo.create.return_value = 99

                # Status update fails after income creation succeeds
                svc.appt_repo.update_status.side_effect = Exception("DB error on status")

                with pytest.raises(Exception, match="DB error on status"):
                    svc.complete_appointment(appointment_id=42, payment_method='cash')

                mock_conn.rollback.assert_called_once()
                mock_conn.commit.assert_not_called()


class TestUpdateAppointmentTransaction:
    """Verify update_appointment rolls back on service reinsertion failure."""

    @patch('services.appointment_service.PricingService')
    @patch('services.appointment_service.AppointmentServiceRepository')
    @patch('services.appointment_service.AppointmentRepository')
    @patch('services.appointment_service.IncomeRepository')
    @patch('services.appointment_service.ClientRepository')
    @patch('services.appointment_service.ServiceAddonRepository')
    @patch('services.appointment_service.EmployeeServiceRepository')
    def test_rolls_back_on_service_reinsertion_failure(self, mock_emp_svc, mock_addon,
                                                         mock_client, mock_income,
                                                         mock_appt, mock_appt_svc,
                                                         mock_pricing, app):
        """If add_service fails after delete_all, old services are not lost."""
        from services.appointment_service import AppointmentBusinessService
        from datetime import date, time

        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                svc = AppointmentBusinessService()

                # appointment_date/start_time are read pre-transaction by the
                # reschedule "timing changed?" guard added in a later feature.
                svc.appt_repo.get_by_id.return_value = {
                    'status': 'scheduled',
                    'client_id': 1,
                    'employee_id': 1,
                    'appointment_date': date(2026, 2, 1),
                    'start_time': time(10, 0),
                }
                # Stub later-feature validators (working-hours, absence conflicts).
                svc._validate_working_hours = Mock(return_value=None)
                svc.absence_repo = Mock()
                svc.absence_repo.check_absence_conflicts.return_value = []
                svc.appt_repo.check_conflicts.return_value = []
                svc.appt_repo.check_client_conflicts.return_value = []

                # Service reinsertion fails
                svc.appt_svc_repo.add_service.side_effect = Exception("DB error on insert")

                services = [
                    {'service_id': 1, 'price_charged': '50', 'duration_minutes': 30, 'is_addon': False}
                ]

                with pytest.raises(Exception, match="DB error on insert"):
                    svc.update_appointment(
                        appointment_id=42,
                        client_id=1, employee_id=1,
                        appointment_date=date(2026, 2, 1),
                        start_time=time(10, 0),
                        end_time=time(10, 30),
                        status='scheduled',
                        notes=None,
                        services=services
                    )

                mock_conn.rollback.assert_called_once()
                mock_conn.commit.assert_not_called()
