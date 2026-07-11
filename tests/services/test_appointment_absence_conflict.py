"""Tests for AppointmentBusinessService._check_absence_conflicts().

Business rule (business-logic-test-tweaks scenario #2/#3):
  * approved absence  -> hard block, "Konflikt z nieobecnością pracownika" message
  * pending absence   -> also blocks (nothing confirmed yet, but scheduling into a
                          slot someone is waiting to hear back on is asking for
                          trouble) via a distinct "oczekuje na akceptację" marker
                          phrase so the frontend can show a lighter toast-only
                          warning instead of the full field-reset treatment.
  * rejected/cancelled -> excluded by the repository query; no conflict at all.
"""
from datetime import date, time
from unittest.mock import Mock

import pytest


def _svc_with_mock_absence_repo():
    from services.appointment_service import AppointmentBusinessService
    svc = AppointmentBusinessService()
    svc.absence_repo = Mock()
    return svc


class TestCheckAbsenceConflicts:
    def test_no_conflicts_passes_silently(self, app):
        with app.app_context():
            svc = _svc_with_mock_absence_repo()
            svc.absence_repo.check_absence_conflicts.return_value = []
            # Rejected/cancelled absences never reach here (repo query excludes
            # them), so an empty result is the expected shape for that case too.
            svc._check_absence_conflicts(5, date(2026, 7, 12), time(10, 0), time(11, 0))

    def test_approved_absence_hard_blocks_with_stable_message(self, app):
        from services.appointment_service import AppointmentError
        with app.app_context():
            svc = _svc_with_mock_absence_repo()
            svc.absence_repo.check_absence_conflicts.return_value = [{
                'status': 'approved', 'category_name': 'Urlop wypoczynkowy',
                'date_from': '2026-07-12',
            }]
            with pytest.raises(AppointmentError) as ei:
                svc._check_absence_conflicts(5, date(2026, 7, 12), time(10, 0), time(11, 0))
            msg = str(ei.value)
            assert 'Konflikt z nieobecnością pracownika' in msg
            assert 'Urlop wypoczynkowy' in msg
            assert 'oczekuje na akceptację' not in msg

    def test_pending_absence_blocks_with_distinct_marker_phrase(self, app):
        from services.appointment_service import AppointmentError
        with app.app_context():
            svc = _svc_with_mock_absence_repo()
            svc.absence_repo.check_absence_conflicts.return_value = [{
                'status': 'pending', 'category_name': 'L4',
                'date_from': '2026-07-12',
            }]
            with pytest.raises(AppointmentError) as ei:
                svc._check_absence_conflicts(5, date(2026, 7, 12), time(10, 0), time(11, 0))
            msg = str(ei.value)
            assert 'oczekuje na akceptację' in msg
            assert 'L4' in msg

    def test_approved_takes_priority_over_pending(self, app):
        """If an employee somehow has both an approved and a pending absence
        overlapping the slot, the approved (confirmed) one should win the
        error message — it's the harder fact."""
        from services.appointment_service import AppointmentError
        with app.app_context():
            svc = _svc_with_mock_absence_repo()
            svc.absence_repo.check_absence_conflicts.return_value = [
                {'status': 'pending', 'category_name': 'L4', 'date_from': '2026-07-12'},
                {'status': 'approved', 'category_name': 'Urlop', 'date_from': '2026-07-12'},
            ]
            with pytest.raises(AppointmentError) as ei:
                svc._check_absence_conflicts(5, date(2026, 7, 12), time(10, 0), time(11, 0))
            assert 'Konflikt z nieobecnością pracownika' in str(ei.value)


class TestCreateAppointmentWiresAbsenceCheck:
    def _svc_ready_to_create(self):
        from services.appointment_service import AppointmentBusinessService
        svc = AppointmentBusinessService()
        svc.pricing = Mock()
        svc.pricing.calculate_appointment_total.return_value = {
            'total_duration': 60, 'total_price': 100, 'breakdown': [],
        }
        svc.appt_repo = Mock()
        svc.appt_repo.check_conflicts.return_value = []
        svc.appt_repo.check_client_conflicts.return_value = []
        svc.absence_repo = Mock()
        return svc

    def test_pending_absence_blocks_create_no_db_write(self, app):
        from services.appointment_service import AppointmentError
        from unittest.mock import patch
        with app.app_context():
            svc = self._svc_ready_to_create()
            svc.absence_repo.check_absence_conflicts.return_value = [{
                'status': 'pending', 'category_name': 'Urlop', 'date_from': '2026-07-12',
            }]
            # No employee schedule on file -> default 09:00-18:00 window, so a
            # 10:00 slot passes the (unrelated) working-hours check and we
            # actually reach the absence check under test.
            with patch('repositories.employees.employee_repository.EmployeeRepository.get_by_id',
                       return_value=None):
                with pytest.raises(AppointmentError) as ei:
                    svc.create_appointment(
                        client_id=1, employee_id=5, service_ids=[1],
                        appt_date=date(2026, 7, 12), start_time=time(10, 0),
                    )
            assert 'oczekuje na akceptację' in str(ei.value)
            svc.appt_repo.create.assert_not_called()

    def test_rejected_absence_does_not_block_create(self, app):
        from unittest.mock import patch
        with app.app_context():
            svc = self._svc_ready_to_create()
            # Repo query already excludes rejected/cancelled — simulate that.
            svc.absence_repo.check_absence_conflicts.return_value = []
            svc.appt_repo.create.return_value = 42
            svc.appt_svc_repo = Mock()
            conn = Mock()
            with patch('repositories.employees.employee_repository.EmployeeRepository.get_by_id',
                       return_value=None), \
                 patch('config.database.DatabaseConnection.get_connection', return_value=conn):
                result = svc.create_appointment(
                    client_id=1, employee_id=5, service_ids=[1],
                    appt_date=date(2026, 7, 12), start_time=time(10, 0),
                )
            assert result['appointment_id'] == 42
            svc.appt_repo.create.assert_called_once()
