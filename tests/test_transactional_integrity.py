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


class TestInvoiceAuditAtomicity:
    """Improvement #7 Step 2: in routes/api_routes.py the invoice create/update data
    write and its audit row(s) now share ONE managed_transaction. A financial change
    can never commit without its forensic audit record, nor an audit row without the
    change it describes — 'amount changed but nobody logged who' is structurally
    impossible.

    These tests use a REAL AuditRepository (not a mock) so the audit write genuinely
    flows through _execute -> safe_commit(conn), which is the mechanism that defers the
    audit INSERT into the shared transaction. The connection is mocked.
    """

    def test_audit_write_is_deferred_then_committed_once(self, app):
        """Inside the transaction the audit INSERT runs but does NOT commit; the single
        commit happens at block exit — exactly the route's create/update behaviour."""
        from repositories.audit_repository import AuditRepository

        with app.app_context():
            mock_conn = Mock()
            mock_conn.cursor.return_value = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                audit = AuditRepository()
                with managed_transaction():
                    audit.log_change(
                        invoice_id=1, field_name='amount',
                        old_value='12000', new_value='1200', action='UPDATE',
                    )
                    # The audit INSERT was issued on the shared connection...
                    mock_conn.cursor.return_value.execute.assert_called_once()
                    # ...but safe_commit was suppressed while in the transaction.
                    mock_conn.commit.assert_not_called()
                # One atomic commit for the whole unit.
                mock_conn.commit.assert_called_once()
                mock_conn.rollback.assert_not_called()

    def test_failure_after_audit_rolls_back_the_audit_write(self, app):
        """If the surrounding operation fails after the audit INSERT was issued, the
        whole transaction rolls back — the audit row is undone with the data write."""
        from repositories.audit_repository import AuditRepository

        with app.app_context():
            mock_conn = Mock()
            mock_conn.cursor.return_value = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                audit = AuditRepository()
                with pytest.raises(RuntimeError, match="invoice write failed"):
                    with managed_transaction():
                        audit.log_change(
                            invoice_id=42, field_name='amount',
                            old_value='12000', new_value='1200', action='UPDATE',
                        )
                        # Simulate the invoice write blowing up after the audit was queued.
                        raise RuntimeError("invoice write failed")
                mock_conn.rollback.assert_called_once()
                mock_conn.commit.assert_not_called()

    def test_audit_failure_rolls_back_invoice_write(self, app):
        """The headline guarantee: if the audit write itself raises, the data write that
        preceded it in the same transaction is rolled back (no commit)."""
        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                invoice_repo = Mock()      # stands in for current_app.invoice_repo
                audit_repo = Mock()        # stands in for current_app.audit_repo
                audit_repo.log_change.side_effect = Exception("audit_log INSERT failed")

                with pytest.raises(Exception, match="audit_log INSERT failed"):
                    with managed_transaction():
                        invoice_repo.update(42, object())       # the financial write
                        audit_repo.log_change(invoice_id=42)    # blows up

                invoice_repo.update.assert_called_once()
                mock_conn.rollback.assert_called_once()
                mock_conn.commit.assert_not_called()


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


class TestResolvePastStatusTransaction:
    """Verify resolve_past_status (Past Visits Scanner) creates income on
    completion, using the visit's own date rather than today's date, and
    rolls back atomically like complete_appointment/update_appointment."""

    @patch('services.appointment_service.PricingService')
    @patch('services.appointment_service.AppointmentServiceRepository')
    @patch('services.appointment_service.AppointmentRepository')
    @patch('services.appointment_service.IncomeRepository')
    @patch('services.appointment_service.ClientRepository')
    @patch('services.appointment_service.ServiceAddonRepository')
    @patch('services.appointment_service.EmployeeServiceRepository')
    def test_completing_a_past_visit_creates_income_dated_to_the_visit(
            self, mock_emp_svc, mock_addon, mock_client, mock_income,
            mock_appt, mock_appt_svc, mock_pricing, app):
        """Regression for the Past Visits Scanner bug: resolving status to
        'completed' must create an income record, and payment_date must be
        the appointment's own date — not date.today() — so the revenue lands
        in the month the visit actually happened, not the month it was
        retroactively closed out in."""
        from services.appointment_service import AppointmentBusinessService
        from datetime import date, time

        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                svc = AppointmentBusinessService()

                visit_date = date(2026, 5, 3)  # a past month, distinct from "today"
                svc.appt_repo.get_by_id.return_value = {
                    'status': 'scheduled',
                    'client_id': 7,
                    'employee_id': 3,
                    'appointment_date': visit_date,
                    'start_time': time(10, 0),
                    'discount_amount': Decimal('10'),
                }
                svc.appt_repo.update_status.return_value = True
                svc.income_repo.get_by_appointment.return_value = None
                svc.appt_svc_repo.get_appointment_totals.return_value = {
                    'total_price': Decimal('100'),
                    'total_commission': Decimal('10'),
                    'main_total': Decimal('100'),
                    'addon_total': Decimal('0'),
                    'addon_count': 0,
                }
                svc.income_repo.create.return_value = 99

                result = svc.resolve_past_status(appointment_id=42, new_status='completed')

                assert result is True
                svc.income_repo.create.assert_called_once()
                income_record = svc.income_repo.create.call_args[0][0]
                assert income_record.appointment_id == 42
                assert income_record.payment_date == visit_date
                assert income_record.total_amount == Decimal('100')
                assert income_record.net_amount == Decimal('90')
                mock_conn.commit.assert_called_once()

    @patch('services.appointment_service.PricingService')
    @patch('services.appointment_service.AppointmentServiceRepository')
    @patch('services.appointment_service.AppointmentRepository')
    @patch('services.appointment_service.IncomeRepository')
    @patch('services.appointment_service.ClientRepository')
    @patch('services.appointment_service.ServiceAddonRepository')
    @patch('services.appointment_service.EmployeeServiceRepository')
    def test_resolving_to_cancelled_does_not_create_income(
            self, mock_emp_svc, mock_addon, mock_client, mock_income,
            mock_appt, mock_appt_svc, mock_pricing, app):
        """Non-completed resolutions (cancelled/no_show) must not touch income."""
        from services.appointment_service import AppointmentBusinessService
        from datetime import date, time

        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                svc = AppointmentBusinessService()

                svc.appt_repo.get_by_id.return_value = {
                    'status': 'scheduled',
                    'client_id': 7,
                    'employee_id': 3,
                    'appointment_date': date(2026, 5, 3),
                    'start_time': time(10, 0),
                    'discount_amount': Decimal('0'),
                }
                svc.appt_repo.update_status.return_value = True

                result = svc.resolve_past_status(appointment_id=42, new_status='no_show')

                assert result is True
                svc.income_repo.create.assert_not_called()

    @patch('services.appointment_service.PricingService')
    @patch('services.appointment_service.AppointmentServiceRepository')
    @patch('services.appointment_service.AppointmentRepository')
    @patch('services.appointment_service.IncomeRepository')
    @patch('services.appointment_service.ClientRepository')
    @patch('services.appointment_service.ServiceAddonRepository')
    @patch('services.appointment_service.EmployeeServiceRepository')
    def test_rolls_back_if_income_creation_fails(
            self, mock_emp_svc, mock_addon, mock_client, mock_income,
            mock_appt, mock_appt_svc, mock_pricing, app):
        """Status update must not survive if income creation fails right after it."""
        from services.appointment_service import AppointmentBusinessService
        from datetime import date, time

        with app.app_context():
            mock_conn = Mock()
            with patch('config.database.DatabaseConnection.get_connection', return_value=mock_conn):
                svc = AppointmentBusinessService()

                svc.appt_repo.get_by_id.return_value = {
                    'status': 'scheduled',
                    'client_id': 7,
                    'employee_id': 3,
                    'appointment_date': date(2026, 5, 3),
                    'start_time': time(10, 0),
                    'discount_amount': Decimal('0'),
                }
                svc.appt_repo.update_status.return_value = True
                svc.income_repo.get_by_appointment.return_value = None
                svc.appt_svc_repo.get_appointment_totals.return_value = {
                    'total_price': Decimal('100'),
                    'total_commission': Decimal('10'),
                    'main_total': Decimal('100'),
                    'addon_total': Decimal('0'),
                    'addon_count': 0,
                }
                svc.income_repo.create.side_effect = Exception("DB error on income insert")

                with pytest.raises(Exception, match="DB error on income insert"):
                    svc.resolve_past_status(appointment_id=42, new_status='completed')

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
