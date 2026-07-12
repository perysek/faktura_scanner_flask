"""Tests for AppointmentBusinessService.get_reassignment_candidates() (Phase 0).

The eligibility rule (AD-4): can perform EVERY main service of the appointment
(intersection, not union) ∩ not the currently-assigned employee ∩ no approved
absence at that slot ∩ no other conflicting appointment at that exact slot.
Survivors are flagged is_preferred against the union of the client's preferred
employees across all of the appointment's services.
"""
from datetime import date, time
from unittest.mock import Mock

import pytest


def _svc_with_mocks():
    from services.appointment_service import AppointmentBusinessService
    svc = AppointmentBusinessService()
    svc.appt_repo = Mock()
    svc.appt_svc_repo = Mock()
    svc.emp_svc_repo = Mock()
    svc.absence_repo = Mock()
    svc.pref_repo = Mock()
    return svc


def _appt_row(employee_id=1, client_id=99):
    return {
        'id': 42, 'employee_id': employee_id, 'client_id': client_id,
        'appointment_date': date(2026, 7, 20),
        'start_time': time(10, 0), 'end_time': time(11, 0),
    }


def _emp_row(employee_id, first='Jan', last='Kowalski', position='Fryzjer'):
    return {'employee_id': employee_id, 'first_name': first, 'last_name': last,
            'position': position}


class TestGetReassignmentCandidates:
    def test_raises_when_appointment_missing(self, app):
        from services.appointment_service import AppointmentError
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = None
            with pytest.raises(AppointmentError):
                svc.get_reassignment_candidates(42)

    def test_empty_when_no_main_services(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row()
            svc.appt_svc_repo.get_main_services.return_value = []
            assert svc.get_reassignment_candidates(42) == []
            svc.emp_svc_repo.get_employees_for_service.assert_not_called()

    def test_excludes_currently_assigned_employee(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row(employee_id=1)
            svc.appt_svc_repo.get_main_services.return_value = [{'service_id': 10}]
            svc.emp_svc_repo.get_employees_for_service.return_value = [_emp_row(1), _emp_row(2)]
            svc.absence_repo.has_approved_absence.return_value = False
            svc.appt_repo.find_conflicting_appointments.return_value = []
            svc.pref_repo.get_preferred_employee_ids.return_value = set()

            result = svc.get_reassignment_candidates(42)

            assert [c['employee_id'] for c in result] == [2]

    def test_excludes_candidate_with_approved_absence(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row(employee_id=1)
            svc.appt_svc_repo.get_main_services.return_value = [{'service_id': 10}]
            svc.emp_svc_repo.get_employees_for_service.return_value = [_emp_row(2), _emp_row(3)]
            svc.absence_repo.has_approved_absence.side_effect = lambda emp_id, *a, **kw: emp_id == 2
            svc.appt_repo.find_conflicting_appointments.return_value = []
            svc.pref_repo.get_preferred_employee_ids.return_value = set()

            result = svc.get_reassignment_candidates(42)

            assert [c['employee_id'] for c in result] == [3]

    def test_excludes_candidate_with_conflicting_appointment(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row(employee_id=1)
            svc.appt_svc_repo.get_main_services.return_value = [{'service_id': 10}]
            svc.emp_svc_repo.get_employees_for_service.return_value = [_emp_row(2), _emp_row(3)]
            svc.absence_repo.has_approved_absence.return_value = False
            svc.appt_repo.find_conflicting_appointments.side_effect = (
                lambda emp_id, *a, **kw: [{'id': 999}] if emp_id == 2 else []
            )
            svc.pref_repo.get_preferred_employee_ids.return_value = set()

            result = svc.get_reassignment_candidates(42)

            assert [c['employee_id'] for c in result] == [3]

    def test_multi_service_appointment_intersects_eligible_sets(self, app):
        """Employee 2 can do service 10 but not 20 -> excluded. Employee 3 can do
        both -> survives. This is the intersection AD-4 requires, not a union."""
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row(employee_id=1)
            svc.appt_svc_repo.get_main_services.return_value = [
                {'service_id': 10}, {'service_id': 20},
            ]
            svc.emp_svc_repo.get_employees_for_service.side_effect = lambda service_id, **kw: {
                10: [_emp_row(2), _emp_row(3)],
                20: [_emp_row(3)],
            }[service_id]
            svc.absence_repo.has_approved_absence.return_value = False
            svc.appt_repo.find_conflicting_appointments.return_value = []
            svc.pref_repo.get_preferred_employee_ids.return_value = set()

            result = svc.get_reassignment_candidates(42)

            assert [c['employee_id'] for c in result] == [3]

    def test_flags_is_preferred_from_union_across_services(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row(employee_id=1, client_id=99)
            svc.appt_svc_repo.get_main_services.return_value = [{'service_id': 10}]
            svc.emp_svc_repo.get_employees_for_service.return_value = [_emp_row(2), _emp_row(3)]
            svc.absence_repo.has_approved_absence.return_value = False
            svc.appt_repo.find_conflicting_appointments.return_value = []
            svc.pref_repo.get_preferred_employee_ids.return_value = {2}

            result = svc.get_reassignment_candidates(42)
            by_id = {c['employee_id']: c for c in result}

            assert by_id[2]['is_preferred'] is True
            assert by_id[3]['is_preferred'] is False
            svc.pref_repo.get_preferred_employee_ids.assert_called_once_with(99, service_id=10)

    def test_result_sorted_by_name(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_by_id.return_value = _appt_row(employee_id=1)
            svc.appt_svc_repo.get_main_services.return_value = [{'service_id': 10}]
            svc.emp_svc_repo.get_employees_for_service.return_value = [
                _emp_row(2, first='Zenon', last='Zajac'),
                _emp_row(3, first='Anna', last='Abacka'),
            ]
            svc.absence_repo.has_approved_absence.return_value = False
            svc.appt_repo.find_conflicting_appointments.return_value = []
            svc.pref_repo.get_preferred_employee_ids.return_value = set()

            result = svc.get_reassignment_candidates(42)

            assert [c['name'] for c in result] == ['Anna Abacka', 'Zenon Zajac']
