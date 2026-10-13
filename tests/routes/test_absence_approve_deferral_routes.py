"""Approve routes of the absence conflict modal.

  * "Zatwierdź wniosek i rozwiąż konflikty" (approve) queues the "Wyślij wiadomość" marks —
    only when the absence actually got approved;
  * "Zatwierdź mimo to" (force) reads the unresolved conflicts BEFORE flipping the status,
    parks them for auto-cancel, and still reports success if parking fails (the absence IS
    approved) — with the error spelled out instead of swallowed.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}


@pytest.fixture
def supervisor_client(app):
    from database.models import User
    app.config['WTF_CSRF_ENABLED'] = False
    user = User(email='s@test.pl', password_hash='x', full_name='Szef', role='superuser', is_active=True, id=9)
    role_repo = MagicMock()
    role_repo.role_has_module_access.return_value = True
    with ExitStack() as stack:
        stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
        stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
        stack.enter_context(patch('routes.absence_routes.get_linked_employee', return_value={'id': 1}))
        yield app.test_client()


def _deferral():
    svc = MagicMock()
    svc.queue_resolution_sms.return_value = [{'appointment_id': 5, 'event_type': 'absence_visit_update', 'event_id': 1}]
    svc.defer_unresolved.return_value = [{'appointment_id': 11, 'valid_for': '2026-11-18T10:00:00+01:00'}]
    return svc


def test_approve_queues_marked_sms_once_approved(supervisor_client):
    absence_svc = MagicMock()
    absence_svc.approve.return_value = {'status': 'approved'}
    deferral = _deferral()
    with patch('routes.absence_routes._svc', return_value=absence_svc), \
         patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService', return_value=deferral):
        r = supervisor_client.post('/absences/3/approve', json={'sms_appointment_ids': [5, 'x']}, headers=XHR)
    body = r.get_json()
    assert r.status_code == 200 and body['status'] == 'approved'
    deferral.queue_resolution_sms.assert_called_once_with(3, [5])
    assert body['sms_queued'][0]['appointment_id'] == 5


def test_approve_with_conflicts_left_queues_nothing(supervisor_client):
    absence_svc = MagicMock()
    absence_svc.approve.return_value = {'status': 'conflict', 'conflicts': [], 'employee_id': 42}
    deferral = _deferral()
    with patch('routes.absence_routes._svc', return_value=absence_svc), \
         patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService', return_value=deferral):
        supervisor_client.post('/absences/3/approve', json={'sms_appointment_ids': [5]}, headers=XHR)
    deferral.queue_resolution_sms.assert_not_called()


def test_force_approve_parks_conflicts_read_before_approval(supervisor_client):
    order = []
    absence_svc = MagicMock()
    conflicts = [{'appointment_id': 11, 'date': '2026-11-20', 'start_time': '10:00:00', 'end_time': '11:00:00'}]
    absence_svc.get_live_conflicts.side_effect = lambda _id: order.append('read') or conflicts
    absence_svc.force_approve.side_effect = lambda *_a: order.append('approve')
    absence_svc.absence_repo.get_by_id.return_value = {'employee_id': 42}
    deferral = _deferral()
    with patch('routes.absence_routes._svc', return_value=absence_svc), \
         patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService', return_value=deferral):
        r = supervisor_client.post('/absences/3/approve/force', json={'sms_appointment_ids': [5]}, headers=XHR)
    body = r.get_json()
    assert order == ['read', 'approve']
    deferral.defer_unresolved.assert_called_once_with(3, 42, conflicts, 9)
    assert body['success'] is True and body['defer_error'] == '' and len(body['deferred']) == 1
    deferral.queue_resolution_sms.assert_called_once_with(3, [5])


def test_force_approve_reports_a_parking_failure_without_unapproving(supervisor_client):
    absence_svc = MagicMock()
    absence_svc.get_live_conflicts.return_value = []
    absence_svc.absence_repo.get_by_id.return_value = {'employee_id': 42}
    deferral = _deferral()
    deferral.defer_unresolved.side_effect = RuntimeError('db hiccup')
    with patch('routes.absence_routes._svc', return_value=absence_svc), \
         patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService', return_value=deferral):
        r = supervisor_client.post('/absences/3/approve/force', json={}, headers=XHR)
    body = r.get_json()
    assert r.status_code == 200 and body['status'] == 'approved'
    assert 'db hiccup' in body['defer_error']
