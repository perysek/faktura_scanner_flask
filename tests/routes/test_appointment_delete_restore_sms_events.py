"""DELETE / restore of a visit and its queued SMS events.

Found on the live site (2026-10-07): delete_appointment left the visit's `sms_events` queued, so the scheduler
would still have texted the employee about a visit that no longer exists. The visit's "dead slot" rule already
holds for reschedule (`_cancel_event_sms`) and cancel; delete was the gap. Restore is the other half: bringing
a visit back must bring its employee reminder back too (a fresh one, because the old one was cancelled, and
only if the visit is live and the reminder moment is still ahead — SmsService.schedule_employee_reminder decides
the latter).

Repositories are patched at the route's import site; auth follows tests/routes/test_visit_notes_routes.py.
"""
from contextlib import ExitStack
from datetime import date, time
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}
FULL = {'appointments': {'has_access': True, 'read_only': False, 'own_data': False}}


@pytest.fixture
def client(app):
    app.config['WTF_CSRF_ENABLED'] = False
    return app.test_client()


def _user():
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User',
                role='superuser', is_active=True, id=5)


def _logged_in():
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(
        FULL.get(module, {'has_access': False, 'read_only': False, 'own_data': False}))
    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=_user()))
    stack.enter_context(patch('config.admin_view.get_hidden_employee_ids', return_value=()))
    return stack


class _World:
    """The collaborators of the two routes, patched where the routes look them up."""

    def __init__(self, *, visit=None, deleted_ok=True, restored_ok=True, cancel_error=None, schedule_error=None):
        self.visit = visit
        self.appts = MagicMock()
        self.appts.get_by_id.return_value = visit
        self.appts.delete.return_value = deleted_ok
        self.appts.restore.return_value = restored_ok
        self.income = MagicMock()
        self.events = MagicMock()
        if cancel_error:
            self.events.return_value.cancel_pending_for_appointment.side_effect = cancel_error
        self.sms = MagicMock()
        if schedule_error:
            self.sms.return_value.schedule_employee_reminder.side_effect = schedule_error

    def __enter__(self):
        self._stack = ExitStack()
        self._stack.enter_context(_logged_in())
        self._stack.enter_context(patch('routes.appointment_routes.AppointmentRepository', return_value=self.appts))
        self._stack.enter_context(patch('routes.appointment_routes.IncomeRepository', return_value=self.income))
        self._stack.enter_context(patch('repositories.sms.sms_event_repository.SmsEventRepository', self.events))
        self._stack.enter_context(patch('services.sms_service.SmsService', self.sms))
        return self

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)

    @property
    def cancelled(self):
        return self.events.return_value.cancel_pending_for_appointment

    @property
    def scheduled(self):
        return self.sms.return_value.schedule_employee_reminder


def _visit(status='confirmed', **extra):
    row = {'id': 100, 'status': status, 'appointment_date': date(2026, 10, 10), 'start_time': time(4, 30)}
    row.update(extra)
    return row


class TestDeleteKillsThePendingSms:
    def test_deleting_a_visit_cancels_every_pending_event_of_it(self, client):
        with _World(visit=_visit()) as w:
            resp = client.delete('/api/appointments/100', headers=XHR)
        assert resp.status_code == 200 and resp.get_json()['success'] is True
        w.cancelled.assert_called_once_with(100)

    def test_a_failed_delete_leaves_the_events_alone(self, client):
        with _World(visit=_visit(), deleted_ok=False) as w:
            resp = client.delete('/api/appointments/100', headers=XHR)
        assert resp.status_code >= 400
        w.cancelled.assert_not_called()

    def test_a_problem_cancelling_the_events_never_fails_the_delete(self, client):
        # same contract as every other SMS side effect of this module: swallowed and logged
        with _World(visit=_visit(), cancel_error=RuntimeError('db hiccup')) as w:
            resp = client.delete('/api/appointments/100', headers=XHR)
        assert resp.status_code == 200 and resp.get_json()['success'] is True
        w.cancelled.assert_called_once_with(100)


class TestRestoreBringsTheEmployeeReminderBack:
    def test_a_restored_live_visit_gets_a_fresh_employee_reminder(self, client):
        from datetime import datetime
        for status in ('scheduled', 'confirmed'):
            with _World(visit=_visit(status)) as w:
                resp = client.post('/api/appointments/100/restore', headers=XHR)
            assert resp.status_code == 200 and resp.get_json()['success'] is True
            w.scheduled.assert_called_once_with(100, datetime(2026, 10, 10, 4, 30))

    @pytest.mark.parametrize('status', ['cancelled', 'completed', 'no_show', 'rescheduled'])
    def test_a_restored_visit_that_is_not_live_gets_none(self, client, status):
        with _World(visit=_visit(status)) as w:
            resp = client.post('/api/appointments/100/restore', headers=XHR)
        assert resp.status_code == 200
        w.scheduled.assert_not_called()

    def test_restoring_something_that_is_not_deleted_schedules_nothing(self, client):
        with _World(visit=_visit(), restored_ok=False) as w:
            resp = client.post('/api/appointments/100/restore', headers=XHR)
        assert resp.status_code == 404
        w.scheduled.assert_not_called()

    def test_a_problem_scheduling_never_fails_the_restore(self, client):
        with _World(visit=_visit(), schedule_error=RuntimeError('sms down')) as w:
            resp = client.post('/api/appointments/100/restore', headers=XHR)
        assert resp.status_code == 200 and resp.get_json()['success'] is True
        w.scheduled.assert_called_once()

    def test_the_visit_is_looked_up_after_it_was_restored(self, client):
        # get_by_id hides deleted rows: asking before restore() would find nothing to schedule against
        order = []
        with _World(visit=_visit()) as w:
            w.appts.restore.side_effect = lambda _id: order.append('restore') or True
            w.appts.get_by_id.side_effect = lambda _id: order.append('lookup') or _visit()
            client.post('/api/appointments/100/restore', headers=XHR)
        assert order == ['restore', 'lookup']
