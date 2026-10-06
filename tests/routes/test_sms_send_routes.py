"""Manual "Wyślij SMS" routes (SMS review P1-9 / P0-2).

  * Links in a manually sent text come from the configured BASE_URL — never from whichever
    host the staff member's browser was on (staging, a raw IP…).
  * A type that is switched off is refused with a clean 400, not a 500 and not a text.
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from services.sms_service import SmsError

XHR = {'X-Requested-With': 'XMLHttpRequest'}
FULL = {'has_access': True, 'read_only': False, 'own_data': False}


@pytest.fixture
def sms(app):
    """Logged-in stylist with appointments access + the SMS permission; SmsService replaced."""
    from database.models import User
    app.config['WTF_CSRF_ENABLED'] = False
    user = User(email='t@test.pl', password_hash='x', full_name='Test User', role='stylist', is_active=True, id=5)
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(FULL)
    emp_repo = MagicMock()
    emp_repo.get_by_user_id.return_value = None
    service = MagicMock()
    service.send.return_value = {'success': True, 'reminder_id': 77}

    with ExitStack() as stack:
        stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
        stack.enter_context(patch('repositories.employees.employee_repository.EmployeeRepository', return_value=emp_repo))
        stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
        stack.enter_context(patch('config.admin_view.get_hidden_employee_ids', return_value=()))
        stack.enter_context(patch('routes.sms_routes.can_send_appointment_sms', return_value=True))
        stack.enter_context(patch('routes.sms_routes.SmsService', return_value=service))
        yield type('Ctx', (), {'service': service, 'client': app.test_client()})()


class TestLinksComeFromConfiguredBaseUrl:
    def test_single_send_does_not_pass_the_browsers_host(self, sms):
        resp = sms.client.post('/api/sms/send', json={'appointment_id': 1, 'message_type_key': 'reminder_1'},
                               headers={**XHR, 'Host': 'staging.my-way-solutions.com'})
        assert resp.status_code == 200 and resp.get_json()['reminder_id'] == 77
        kwargs = sms.service.send.call_args.kwargs
        assert 'base_url' not in kwargs, 'send() must fall back to the configured BASE_URL'
        assert kwargs['sender_user_id'] == 5

    def test_bulk_send_does_not_pass_the_browsers_host_either(self, sms):
        resp = sms.client.post('/api/sms/bulk-send',
                               json={'appointment_ids': [1, 2], 'message_type_key': 'reminder_1'},
                               headers={**XHR, 'Host': 'http://70.34.252.120'})
        assert resp.status_code == 200 and resp.get_json()['sent'] == 2
        assert all('base_url' not in c.kwargs for c in sms.service.send.call_args_list)


class TestDisabledTypeIsAClean400:
    def test_single_send(self, sms):
        sms.service.send.side_effect = SmsError('Typ SMS „Ocena” jest wyłączony w ustawieniach')
        resp = sms.client.post('/api/sms/send', json={'appointment_id': 1, 'message_type_key': 'post_visit_message'},
                               headers=XHR)
        assert resp.status_code == 400
        assert 'wyłączony' in resp.get_json()['message']

    def test_bulk_send_reports_each_refusal_without_aborting_the_batch(self, sms):
        sms.service.send.side_effect = [SmsError('wyłączony'), {'success': True, 'reminder_id': 1}]
        resp = sms.client.post('/api/sms/bulk-send',
                               json={'appointment_ids': [1, 2], 'message_type_key': 'post_visit_message'},
                               headers=XHR)
        body = resp.get_json()
        assert body['sent'] == 1 and body['total'] == 2
        assert body['details'][0]['success'] is False and 'wyłączony' in body['details'][0]['error']
