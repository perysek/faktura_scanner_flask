"""Absence-conflict "cancel + notify the client" must never fail silently (SMS review P0-2 / P2-7).

`SmsService.send()` now refuses a switched-off type — and `absence_cancellation` ships switched
off — while the modal's "Wyślij SMS" box used to be ticked by default. Without these changes
staff would believe a client had been told while nothing was sent. So:
  * the candidates endpoint says whether the SMS can actually go out (the box is only offered then);
  * the cancel endpoint reports what happened to the SMS it was asked to send.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from services.sms_service import SmsError

XHR = {'X-Requested-With': 'XMLHttpRequest'}
CONFIGURED = {'is_active': True, 'account_sid': 'AC1', 'auth_token': 'tok', 'from_number': '+48500000000'}


def _service(settings=None, msg_type=None):
    from services.sms_service import SmsService
    svc = SmsService()
    svc.get_settings = MagicMock(return_value=CONFIGURED if settings is None else settings)
    svc._type_repo = MagicMock()
    svc._type_repo.get_by_key.return_value = msg_type
    return svc


class TestTypeStatus:
    def test_available_when_configured_and_type_enabled(self):
        svc = _service(msg_type={'name': 'Anulowanie', 'is_enabled': True})
        assert svc.type_status('absence_cancellation') == {'available': True, 'reason': ''}

    def test_type_switched_off_says_so_by_name(self):
        status = _service(msg_type={'name': 'Anulowanie wizyty (nieobecność pracownika)', 'is_enabled': False}) \
            .type_status('absence_cancellation')
        assert status['available'] is False
        assert 'Anulowanie wizyty (nieobecność pracownika)' in status['reason'] and 'wyłączony' in status['reason']

    @pytest.mark.parametrize('settings', [
        {**CONFIGURED, 'is_active': False},
        {**CONFIGURED, 'account_sid': ''},
        {**CONFIGURED, 'auth_token': None},
        {**CONFIGURED, 'from_number': '', 'messaging_service_sid': None},
        {},
    ], ids=['sms-off', 'no-sid', 'no-token', 'no-sender', 'empty'])
    def test_sms_off_or_unconfigured(self, settings):
        status = _service(settings=settings, msg_type={'name': 'x', 'is_enabled': True}).type_status('absence_cancellation')
        assert status['available'] is False and 'SMS' in status['reason']

    def test_messaging_service_counts_as_a_sender(self):
        settings = {**CONFIGURED, 'from_number': '', 'messaging_service_sid': 'MG1'}
        assert _service(settings=settings, msg_type={'name': 'x', 'is_enabled': True}) \
            .type_status('absence_cancellation')['available'] is True

    def test_unknown_type(self):
        status = _service(msg_type=None).type_status('nope')
        assert status['available'] is False and 'nope' in status['reason']


class TestAbsenceSmsOutcomeIsReported:
    def _run(self, app, *, send=None, raises=None):
        from routes.absence_routes import _send_absence_cancellation_sms
        svc = MagicMock()
        if raises:
            svc.send.side_effect = raises
        else:
            svc.send.return_value = send
        with app.app_context(), patch('services.sms_service.SmsService', return_value=svc):
            return _send_absence_cancellation_sms(41)

    def test_sent(self, app):
        assert self._run(app, send={'success': True, 'reminder_id': 3}) == {'status': 'sent'}

    def test_switched_off_type_is_reported_with_the_reason(self, app):
        out = self._run(app, raises=SmsError('Typ SMS „Anulowanie” jest wyłączony w ustawieniach'))
        assert out['status'] == 'failed' and 'wyłączony' in out['error']

    def test_twilio_failure_is_reported(self, app):
        out = self._run(app, send={'success': False, 'error': 'Twilio 21211 invalid number'})
        assert out == {'status': 'failed', 'error': 'Twilio 21211 invalid number'}

    def test_crash_never_propagates(self, app):
        out = self._run(app, raises=RuntimeError('db gone'))
        assert out['status'] == 'failed' and 'db gone' in out['error']


@pytest.fixture
def supervisor(app):
    from database.models import User
    app.config['WTF_CSRF_ENABLED'] = False
    user = User(email='s@test.pl', password_hash='x', full_name='Szefowa', role='admin', is_active=True, id=2)
    role_repo = MagicMock()
    role_repo.role_has_module_access.return_value = True
    with ExitStack() as stack:
        stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
        stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
        yield app.test_client()


class TestCandidatesEndpointTellsWhetherTheSmsCanGoOut:
    def _get(self, client, status):
        service, sms = MagicMock(), MagicMock()
        service.get_reassignment_candidates.return_value = []
        sms.type_status.return_value = status
        with patch('routes.appointment_routes.AppointmentBusinessService', return_value=service), \
             patch('services.sms_service.SmsService', return_value=sms):
            resp = client.get('/api/appointments/9/reassignment-candidates', headers=XHR)
        return resp, sms

    def test_includes_the_availability_of_the_absence_cancellation_sms(self, supervisor):
        status = {'available': False, 'reason': 'Typ SMS „X” jest wyłączony w Ustawieniach SMS.'}
        resp, sms = self._get(supervisor, status)
        assert resp.status_code == 200
        assert resp.get_json()['sms'] == status
        sms.type_status.assert_called_once_with('absence_cancellation')

    def test_a_broken_status_check_degrades_to_unavailable_instead_of_failing_the_modal(self, supervisor):
        service, sms = MagicMock(), MagicMock()
        service.get_reassignment_candidates.return_value = [{'employee_id': 1}]
        sms.type_status.side_effect = RuntimeError('db')
        with patch('routes.appointment_routes.AppointmentBusinessService', return_value=service), \
             patch('services.sms_service.SmsService', return_value=sms):
            resp = supervisor.get('/api/appointments/9/reassignment-candidates', headers=XHR)
        body = resp.get_json()
        assert resp.status_code == 200 and body['candidates'] == [{'employee_id': 1}]
        assert body['sms']['available'] is False and body['sms']['reason']


class TestCancelEndpointReportsTheSms:
    def _post(self, client, outcomes, *, send_sms=True, bulk=False):
        calls = []

        def fake_do_cancel(appointment_id, absence_id, reason, want_sms, sms_results=None):
            calls.append((appointment_id, want_sms))
            if want_sms and sms_results is not None:
                sms_results.append(outcomes.pop(0))
            return appointment_id

        absence = MagicMock()
        absence.get_live_conflicts.return_value = [{'appointment_id': 12}, {'appointment_id': 13}]
        with patch('routes.appointment_routes._do_cancel', side_effect=fake_do_cancel), \
             patch('services.absence_service.AbsenceService', return_value=absence):
            resp = client.post('/api/appointments/11/cancel-for-absence', headers=XHR,
                               json={'absence_id': 5, 'send_sms': send_sms, 'bulk': bulk})
        return resp, calls

    def test_sent(self, supervisor):
        resp, _ = self._post(supervisor, [{'status': 'sent'}])
        assert resp.get_json()['sms'] == {'requested': True, 'sent': 1, 'failed': 0, 'error': ''}

    def test_a_failed_text_is_reported_with_its_reason(self, supervisor):
        resp, _ = self._post(supervisor, [{'status': 'failed', 'error': 'Typ SMS „X” jest wyłączony'}])
        body = resp.get_json()
        assert body['success'] is True and body['applied'] == [11]            # the cancellation itself stands
        assert body['sms'] == {'requested': True, 'sent': 0, 'failed': 1, 'error': 'Typ SMS „X” jest wyłączony'}

    def test_bulk_counts_every_text(self, supervisor):
        outcomes = [{'status': 'sent'}, {'status': 'failed', 'error': 'Twilio 21211'}, {'status': 'sent'}]
        resp, calls = self._post(supervisor, outcomes, bulk=True)
        assert [c[0] for c in calls] == [11, 12, 13]
        assert resp.get_json()['sms'] == {'requested': True, 'sent': 2, 'failed': 1, 'error': 'Twilio 21211'}

    def test_no_sms_requested_means_nothing_to_report(self, supervisor):
        resp, calls = self._post(supervisor, [], send_sms=False)
        assert resp.get_json()['sms'] == {'requested': False, 'sent': 0, 'failed': 0, 'error': ''}
        assert calls == [(11, False)]
