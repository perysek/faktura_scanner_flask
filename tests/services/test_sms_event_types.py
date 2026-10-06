"""P0-2 — event-only SMS types must stay out of the time-based reminder loop, and
automatic sends must be idempotent.

Before: `send_due_reminders` iterated EVERY enabled type and read
`send_hours_before` as "N hours before the visit". For `post_visit_message`
and `absence_cancellation` N = 0, so "due" meant "visit starts now ± 15 min":
enabling the rating text texted clients "thanks, rate us" before the visit
happened (and again when it did), enabling the absence text sent a false
"your visit is cancelled" to everyone starting in the window.

The unit layer proves the wiring and the SQL shape; which rows the database
actually returns is proven on a real Postgres (`verify_wp1.py`, stored beside
the ISA).
"""
from unittest.mock import Mock, patch

import pytest

TYPE_REPO = 'repositories.sms.sms_repository.SmsMessageTypeRepository'
EVENT_REPO = 'repositories.sms.sms_event_repository.SmsEventRepository'

CONFIGURED = {'account_sid': 'AC1', 'auth_token': 'tok', 'from_number': '+48500000000',
              'is_active': True}


def _svc():
    from services.sms_service import SmsService
    svc = SmsService()
    svc.get_settings = Mock(return_value=dict(CONFIGURED))
    svc._type_repo = Mock()
    svc._reminder_repo = Mock()
    svc._appt_repo = Mock()
    return svc


class TestReminderLoopOnlyTakesBeforeVisitTypes:
    def test_loop_uses_the_safe_query_not_get_enabled(self):
        svc = _svc()
        svc._type_repo.get_enabled_before_visit.return_value = []
        svc.send_due_reminders('https://salon.example')
        svc._type_repo.get_enabled_before_visit.assert_called_once_with()
        svc._type_repo.get_enabled.assert_not_called()

    def test_loop_sends_each_due_visit_once_per_type_as_auto(self):
        svc = _svc()
        svc._type_repo.get_enabled_before_visit.return_value = [
            {'type_key': 'reminder_1', 'send_hours_before': 24}]
        svc._appt_repo.get_appointments_due_for_type.return_value = [{'id': 11}, {'id': 12}]
        svc.send = Mock(side_effect=[{'success': True}, {'success': False, 'skipped': True}])

        result = svc.send_due_reminders('https://salon.example')

        assert result == {'sent': 1, 'skipped': 1, 'failed': 0}
        for call in svc.send.call_args_list:
            assert call.kwargs['auto'] is True
            assert call.kwargs['message_type_key'] == 'reminder_1'
        svc._appt_repo.get_appointments_due_for_type.assert_called_once_with(
            hours_before=24, message_type_key='reminder_1')

    def test_query_filters_on_mode_lead_time_and_enabled(self):
        from repositories.sms.sms_repository import SmsMessageTypeRepository
        repo = SmsMessageTypeRepository()
        with patch.object(SmsMessageTypeRepository, '_fetch_all', return_value=[]) as fetch:
            repo.get_enabled_before_visit()
        sql = ' '.join(fetch.call_args.args[0].split())
        assert "is_enabled = TRUE" in sql
        assert "trigger_mode = 'before_visit'" in sql
        assert "send_hours_before > 0" in sql


class TestSendEnforcesEnabledSwitch:
    def test_disabled_type_is_refused_before_anything_is_written(self):
        from services.sms_service import SmsError
        svc = _svc()
        svc._type_repo.get_by_key.return_value = {'id': 1, 'type_key': 'absence_cancellation',
                                                  'name': 'Anulowanie', 'is_enabled': False}
        with pytest.raises(SmsError, match='wyłączony'):
            svc.send(5, 'absence_cancellation')
        svc._appt_repo.get_by_id.assert_not_called()
        svc._reminder_repo.create.assert_not_called()

    def test_unknown_type_is_still_refused(self):
        from services.sms_service import SmsError
        svc = _svc()
        svc._type_repo.get_by_key.return_value = None
        with pytest.raises(SmsError, match='Nieznany'):
            svc.send(5, 'nope')


class TestAutomaticSendsAreIdempotent:
    def _enabled(self, svc):
        svc._type_repo.get_by_key.return_value = {'id': 4, 'type_key': 'post_visit_message',
                                                  'name': 'Ocena', 'is_enabled': True}

    def test_second_automatic_send_is_skipped_without_touching_twilio(self):
        svc = _svc()
        self._enabled(svc)
        svc._reminder_repo.exists_active.return_value = True
        with patch('twilio.rest.Client') as twilio:
            result = svc.send(5, 'post_visit_message', auto=True)
        assert result['success'] is False and result['skipped'] is True
        svc._reminder_repo.exists_active.assert_called_once_with(5, 'post_visit_message')
        svc._appt_repo.get_by_id.assert_not_called()
        svc._reminder_repo.create.assert_not_called()
        twilio.assert_not_called()

    def test_manual_resend_by_staff_is_not_blocked(self):
        from services.sms_service import SmsError
        svc = _svc()
        self._enabled(svc)
        svc._reminder_repo.exists_active.return_value = True
        svc._appt_repo.get_by_id.return_value = None          # stop right after the dedupe stage
        with pytest.raises(SmsError, match='nie istnieje'):
            svc.send(5, 'post_visit_message')                 # auto defaults to False
        svc._reminder_repo.exists_active.assert_not_called()
        svc._appt_repo.get_by_id.assert_called_once_with(5)

    def test_event_queue_closes_a_duplicate_as_skipped_not_failed(self):
        svc = _svc()
        event_repo = Mock()
        event_repo.get_due.return_value = [{'id': 90, 'appointment_id': 5, 'event_type': 'post_visit_message'}]
        svc.send = Mock(return_value={'success': False, 'skipped': True, 'error': 'już wysłany'})
        with patch(EVENT_REPO, return_value=event_repo):
            result = svc.send_due_event_sms('https://salon.example')
        assert result == {'sent': 0, 'failed': 0, 'skipped': 1}
        event_repo.mark_skipped.assert_called_once_with(90, 'już wysłany')
        event_repo.mark_failed.assert_not_called()
        assert svc.send.call_args.kwargs['auto'] is True

    def test_event_queue_marks_rating_sent_on_success(self):
        svc = _svc()
        event_repo = Mock()
        event_repo.get_due.return_value = [{'id': 91, 'appointment_id': 6, 'event_type': 'post_visit_message'}]
        svc.send = Mock(return_value={'success': True, 'reminder_id': 33})
        with patch(EVENT_REPO, return_value=event_repo):
            result = svc.send_due_event_sms('https://salon.example')
        assert result == {'sent': 1, 'failed': 0, 'skipped': 0}
        event_repo.mark_sent.assert_called_once_with(91, 33)
        svc._appt_repo.update_rating_status.assert_called_once_with(6, 'sent')

    def test_exists_active_ignores_failed_rows_so_a_failure_can_be_retried(self):
        from repositories.sms.sms_repository import SmsReminderRepository
        repo = SmsReminderRepository()
        with patch.object(SmsReminderRepository, '_fetch_one', return_value={'present': 1}) as one:
            assert repo.exists_active(5, 'post_visit_message') is True
        sql = ' '.join(one.call_args.args[0].split())
        assert "status IN ('pending', 'sent', 'delivered')" in sql
        assert "'failed'" not in sql
        with patch.object(SmsReminderRepository, '_fetch_one', return_value=None):
            assert repo.exists_active(5, 'post_visit_message') is False


class TestCustomTypeKeys:
    """P3-2: `custom_{count+1}` collided on the UNIQUE type_key after a deletion."""

    def _create(self, highest, hours):
        from repositories.sms.sms_repository import SmsMessageTypeRepository
        repo = SmsMessageTypeRepository()
        with patch.object(SmsMessageTypeRepository, '_fetch_one', return_value={'m': highest}), \
             patch.object(SmsMessageTypeRepository, '_execute_insert', return_value=77) as ins:
            new_id = repo.create_custom('Test', hours, 'tpl', True)
        assert new_id == 77
        return ins.call_args.args[1]

    def test_next_key_follows_the_highest_suffix_not_the_row_count(self):
        # custom_001 deleted; custom_002, custom_003 remain -> count says 2 (-> custom_003 again!)
        params = self._create(highest=3, hours=24)
        assert params[0] == 'custom_004'

    def test_first_custom_key(self):
        assert self._create(highest=0, hours=24)[0] == 'custom_001'

    def test_lead_time_decides_the_trigger_mode(self):
        assert self._create(highest=0, hours=24)[-1] == 'before_visit'
        assert self._create(highest=0, hours=0)[-1] == 'manual'
