"""GET /api/sms/pending and GET /api/sms/appointment/<id>/overview.

Permission gates follow the rest of sms_routes (pending = `settings`, like the sent log it sits
beside; overview = `appointments`, like the other per-visit SMS endpoints). The queue service is
patched at the route's import site — its own logic is covered in tests/services.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock, patch

XHR = {'X-Requested-With': 'XMLHttpRequest'}


def _user(role='admin'):
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User', role=role, is_active=True, id=5)


def _logged_in(modules, *, role='admin'):
    flags = {m: {'has_access': True, 'read_only': False, 'own_data': False} for m in modules}
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda r, module: dict(
        flags.get(module, {'has_access': False, 'read_only': False, 'own_data': False}))
    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=_user(role)))
    stack.enter_context(patch('config.admin_view.get_hidden_employee_ids', return_value=()))
    return stack


PENDING = {'rows': [{'key': 'w1:confirmation_request', 'will_be_sent_at': '2026-10-07T07:50:53'}],
           'total': 1, 'sms_active': True, 'next_tick_at': '2026-10-07T04:20:53', 'estimated': False}


class TestPending:
    def _get(self, client, query='', modules=('settings',)):
        queue = MagicMock()
        queue.return_value.pending.return_value = PENDING
        with _logged_in(modules), \
             patch('routes.sms_routes.SmsQueueService', queue), \
             patch('routes.sms_routes.scheduler.next_tick_local', return_value=datetime(2026, 10, 7, 4, 20, 53)):
            resp = client.get('/api/sms/pending' + query, headers=XHR)
        return resp, queue

    def test_returns_the_queue_with_paging_echoed_and_the_scheduler_anchor_passed_through(self, client):
        resp, queue = self._get(client)
        body = resp.get_json()
        assert resp.status_code == 200 and body['success'] is True
        assert body['rows'][0]['will_be_sent_at'] == '2026-10-07T07:50:53'
        assert (body['offset'], body['limit'], body['total']) == (0, 100, 1)
        kwargs = queue.return_value.pending.call_args.kwargs
        assert kwargs['next_run'] == datetime(2026, 10, 7, 4, 20, 53)

    def test_paging_is_clamped(self, client):
        resp, queue = self._get(client, '?offset=-5&limit=100000')
        kwargs = queue.return_value.pending.call_args.kwargs
        assert (kwargs['offset'], kwargs['limit']) == (0, 500)
        resp, queue = self._get(client, '?limit=0')
        assert queue.return_value.pending.call_args.kwargs['limit'] == 1

    def test_needs_settings_access(self, client):
        resp, _ = self._get(client, modules=('appointments',))
        assert resp.status_code == 403

    def test_a_failing_queue_is_a_clean_500_not_a_traceback(self, client):
        queue = MagicMock()
        queue.return_value.pending.side_effect = RuntimeError('db down')
        with _logged_in(('settings',)), patch('routes.sms_routes.SmsQueueService', queue), \
             patch('routes.sms_routes.scheduler.next_tick_local', return_value=None):
            resp = client.get('/api/sms/pending', headers=XHR)
        assert resp.status_code == 500 and resp.get_json()['success'] is False


class TestOverview:
    def _get(self, client, *, modules=('appointments',), role='admin', can_send=True):
        queue = MagicMock()
        queue.return_value.pending.return_value = dict(PENDING, rows=[{'key': 'w9:reminder_1'}])
        queue.return_value.manual_send_options.return_value = {
            'sms_active': True, 'types': [{'type_key': 'confirmation_request', 'name': 'Prośba', 'available': True,
                                           'reason': None, 'already_sent': False}]}
        reminders = MagicMock()
        reminders.return_value.get_for_appointment.return_value = [{
            'id': 3, 'sent_at': datetime(2026, 10, 7, 5, 0, tzinfo=timezone.utc), 'message_type_key': 'confirmation_request',
            'type_name': 'Prośba', 'status': 'sent', 'created_by_user_id': None, 'created_by_name': 'System (auto)',
            'sender_name': None, 'error_message': None}]
        with _logged_in(modules, role=role), \
             patch('routes.sms_routes.SmsQueueService', queue), \
             patch('routes.sms_routes.SmsReminderRepository', reminders), \
             patch('routes.sms_routes.can_send_appointment_sms', return_value=can_send), \
             patch('routes.sms_routes.scheduler.next_tick_local', return_value=None):
            resp = client.get('/api/sms/appointment/42/overview', headers=XHR)
        return resp, queue

    def test_one_call_carries_sent_pending_the_dropdown_and_the_send_flag(self, client):
        resp, queue = self._get(client)
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['sent'][0]['sent_at'] == '2026-10-07T07:00:00'        # 05:00 UTC -> 07:00 Warsaw (CEST)
        assert body['sent'][0]['automatic'] is True and body['sent'][0]['sent_by'] == 'System (auto)'
        assert body['pending'] == [{'key': 'w9:reminder_1'}] and body['pending_estimated'] is False
        assert body['send_types'][0]['type_key'] == 'confirmation_request'
        assert body['can_send'] is True and body['sms_active'] is True
        assert queue.return_value.pending.call_args.kwargs['appointment_id'] == 42
        queue.return_value.manual_send_options.assert_called_once_with(42)

    def test_a_role_without_the_sms_flag_is_told_it_cannot_send(self, client):
        resp, _ = self._get(client, can_send=False)
        assert resp.get_json()['can_send'] is False

    def test_needs_appointments_access(self, client):
        resp, _ = self._get(client, modules=('settings',))
        assert resp.status_code == 403


class TestMonthPicker:
    """`?month=YYYY-MM` on both Historia SMS endpoints: everything up to the END of that month, newest first."""

    def _log(self, client, query='', rows=None):
        reminders = MagicMock()
        reminders.return_value.get_log.return_value = rows if rows is not None else []
        reminders.return_value.count_log.return_value = 42
        with _logged_in(('settings',)), patch('routes.sms_routes.SmsReminderRepository', reminders):
            resp = client.get('/api/sms/log' + query, headers=XHR)
        return resp, reminders

    def test_the_log_is_cut_at_the_start_of_the_following_month_warsaw_time(self, client):
        resp, reminders = self._log(client, '?month=2026-10')
        assert resp.status_code == 200
        before = reminders.return_value.get_log.call_args.kwargs['before']
        assert before.replace(tzinfo=None) == datetime(2026, 11, 1) and before.utcoffset() == timedelta(hours=1)   # CET on 1 Nov
        assert reminders.return_value.count_log.call_args.kwargs['before'] == before     # the pill counts what the list reaches

    def test_the_log_reports_its_total_and_defaults_to_no_bound(self, client):
        resp, reminders = self._log(client)
        assert resp.get_json()['total'] == 42
        assert reminders.return_value.get_log.call_args.kwargs['before'] is None

    def test_log_rows_keep_the_text_and_the_response_for_the_table(self, client):
        row = {'id': 1, 'sent_at': datetime(2026, 10, 7, 5, 0, tzinfo=timezone.utc), 'message_body': 'Hej! https://x.pl/rate/abc',
               'response': 'rated', 'created_by_user_id': None, 'created_by_name': 'System (auto)', 'status': 'sent',
               'appointment_date': datetime(2026, 10, 8).date(), 'start_time': datetime(2026, 10, 8, 10).time()}
        resp, _ = self._log(client, rows=[row])
        out = resp.get_json()['rows'][0]
        assert out['message_body'] == 'Hej! https://x.pl/rate/abc' and out['response'] == 'rated'
        assert out['sent_at'] == '2026-10-07T07:00:00'

    def test_the_log_page_size_is_clamped(self, client):
        _, reminders = self._log(client, '?limit=100000&offset=-3')
        kwargs = reminders.return_value.get_log.call_args.kwargs
        assert (kwargs['limit'], kwargs['offset']) == (500, 0)

    @pytest.mark.parametrize('path', ['/api/sms/log', '/api/sms/pending'])
    @pytest.mark.parametrize('bad', ['2026-13', 'oct', '2026-1', '1999-01'])
    def test_a_malformed_month_is_a_400_not_a_500(self, client, path, bad):
        with _logged_in(('settings',)), patch('routes.sms_routes.SmsReminderRepository'), \
             patch('routes.sms_routes.SmsQueueService'), patch('routes.sms_routes.scheduler.next_tick_local', return_value=None):
            resp = client.get(f'{path}?month={bad}', headers=XHR)
        assert resp.status_code == 400 and resp.get_json()['success'] is False

    def test_pending_gets_the_same_cutoff_naive_warsaw_and_the_requested_order(self, client):
        resp, queue = TestPending()._get(client, '?month=2026-12&order=desc')
        assert resp.status_code == 200
        kwargs = queue.return_value.pending.call_args.kwargs
        assert kwargs['before'] == datetime(2027, 1, 1) and kwargs['newest_first'] is True

    def test_pending_keeps_its_old_behaviour_without_the_new_parameters(self, client):
        _, queue = TestPending()._get(client)
        kwargs = queue.return_value.pending.call_args.kwargs
        assert kwargs['before'] is None and kwargs['newest_first'] is False
