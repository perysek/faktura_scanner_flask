"""Tests for AbsenceService.preview_conflicts() and get_live_conflicts()
(plan: absences-requests-conflicts-management, Phase 0).

  * preview_conflicts()  — non-authoritative, pre-submit preview (Faza 2). Works
                            off raw employee_id/date/time args, no existing absence
                            row required.
  * get_live_conflicts() — authoritative live refetch used by the supervisor
                            conflict-resolution modal after every resolution
                            action (Faza 3 / AD-8). Requires a 'pending' absence.
"""
from datetime import date, time
from unittest.mock import Mock

import pytest


def _svc_with_mocks():
    from services.absence_service import AbsenceService
    svc = AbsenceService()
    svc.absence_repo = Mock()
    return svc


class TestPreviewConflicts:
    def test_empty_when_no_overlapping_appointments(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_overlapping_appointments.return_value = []
            result = svc.preview_conflicts(5, date(2026, 7, 20), date(2026, 7, 20))
            assert result == []

    def test_formats_overlapping_appointments(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_overlapping_appointments.return_value = [{
                'id': 42, 'appointment_date': date(2026, 7, 20),
                'start_time': time(10, 0), 'end_time': time(11, 0),
                'client_name': 'Anna Nowak', 'service_name': 'Manicure',
            }]
            result = svc.preview_conflicts(5, date(2026, 7, 20), date(2026, 7, 20),
                                           time(9, 0), time(12, 0))
            assert result == [{
                'appointment_id': 42, 'date': '2026-07-20',
                'start_time': '10:00:00', 'end_time': '11:00:00',
                'client_name': 'Anna Nowak', 'service_name': 'Manicure',
            }]
            svc.absence_repo.get_overlapping_appointments.assert_called_once_with(
                5, date(2026, 7, 20), date(2026, 7, 20), time(9, 0), time(12, 0)
            )

    def test_does_not_require_an_existing_absence_row(self, app):
        """Unlike get_live_conflicts, preview_conflicts never touches get_by_id —
        it's a what-if check for a request that doesn't exist yet."""
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_overlapping_appointments.return_value = []
            svc.preview_conflicts(5, date(2026, 7, 20), date(2026, 7, 20))
            svc.absence_repo.get_by_id.assert_not_called()


class TestGetLiveConflicts:
    def test_raises_when_absence_missing(self, app):
        from services.absence_service import AbsenceError
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = None
            with pytest.raises(AbsenceError):
                svc.get_live_conflicts(999)
            svc.absence_repo.get_overlapping_appointments.assert_not_called()

    def test_raises_when_absence_not_pending(self, app):
        from services.absence_service import AbsenceError
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = {
                'status': 'approved', 'employee_id': 5,
                'date_from': date(2026, 7, 20), 'date_to': date(2026, 7, 20),
                'time_from': None, 'time_to': None,
            }
            with pytest.raises(AbsenceError):
                svc.get_live_conflicts(1)

    def test_empty_list_when_all_conflicts_resolved(self, app):
        """The AD-8 contract: once every conflicting appointment has been
        reassigned/rescheduled/cancelled away, this returns empty — the signal
        the conflict-resolution modal uses to unlock 'Zatwierdź'."""
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = {
                'status': 'pending', 'employee_id': 5,
                'date_from': date(2026, 7, 20), 'date_to': date(2026, 7, 20),
                'time_from': None, 'time_to': None,
            }
            svc.absence_repo.get_overlapping_appointments.return_value = []
            assert svc.get_live_conflicts(1) == []

    def test_returns_formatted_remaining_conflicts(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.absence_repo.get_by_id.return_value = {
                'status': 'pending', 'employee_id': 5,
                'date_from': date(2026, 7, 20), 'date_to': date(2026, 7, 20),
                'time_from': None, 'time_to': None,
            }
            svc.absence_repo.get_overlapping_appointments.return_value = [{
                'id': 7, 'appointment_date': date(2026, 7, 20),
                'start_time': time(14, 0), 'end_time': time(15, 0),
                'client_name': 'Piotr Kowalski', 'service_name': 'Strzyżenie',
            }]
            result = svc.get_live_conflicts(1)
            assert len(result) == 1
            assert result[0]['appointment_id'] == 7
            svc.absence_repo.get_overlapping_appointments.assert_called_once_with(
                5, date(2026, 7, 20), date(2026, 7, 20), None, None
            )
