"""SmsService.send_booking_confirmation — the ONE text an online booking triggers, and the
reminder hold for phone numbers nobody has verified yet (SMS review P0-4, decision D4a).

The invariant worth defending: a visit is held ONLY while the link that releases it is
actually on its way. Held-without-a-link would silently strip the client of every
reminder; hence the hold is lifted whenever the text did not go out.
"""
from unittest.mock import MagicMock

import pytest


def _svc(*, active=True, enabled=True, type_exists=True):
    from services.sms_service import SmsService
    svc = SmsService()
    svc.get_settings = MagicMock(return_value={'is_active': active})
    svc._type_repo = MagicMock()
    svc._type_repo.get_by_key.return_value = (
        {'id': 9, 'type_key': 'booking_confirmed', 'is_enabled': enabled} if type_exists else None)
    svc._appt_repo = MagicMock()
    svc.order = MagicMock()                      # records hold/send call order
    svc.order.attach_mock(svc._appt_repo.set_sms_hold, 'hold')
    svc.send = MagicMock(return_value={'success': True, 'reminder_id': 1})
    svc.order.attach_mock(svc.send, 'send')
    return svc


class TestHoldLifecycle:
    def test_hold_is_set_before_sending_to_close_the_race_with_the_loop(self):
        svc = _svc()
        result = svc.send_booking_confirmation(55, hold=True)
        assert result == {'status': 'sent', 'hold': True}
        names = [c[0] for c in svc.order.mock_calls]
        assert names == ['hold', 'send']
        svc._appt_repo.set_sms_hold.assert_called_once_with(55, True)

    def test_sent_as_an_automatic_text_from_the_online_booking_sender(self):
        svc = _svc()
        svc.send_booking_confirmation(55, hold=False)
        args, kwargs = svc.send.call_args
        assert args == (55, 'booking_confirmed')
        assert kwargs['auto'] is True and kwargs['sender_name'] == 'Rezerwacja online'

    def test_returning_client_is_never_held(self):
        svc = _svc()
        assert svc.send_booking_confirmation(55, hold=False) == {'status': 'sent', 'hold': False}
        svc._appt_repo.set_sms_hold.assert_not_called()

    def test_failed_send_lifts_the_hold_so_the_visit_is_not_orphaned(self):
        svc = _svc()
        svc.send.return_value = {'success': False, 'error': 'twilio 21211'}
        result = svc.send_booking_confirmation(55, hold=True)
        assert result['status'] == 'failed' and result['hold'] is False and 'twilio' in result['error']
        assert [c.args for c in svc._appt_repo.set_sms_hold.call_args_list] == [(55, True), (55, False)]

    def test_sms_error_is_treated_like_a_failed_send(self):
        from services.sms_service import SmsError
        svc = _svc()
        svc.send.side_effect = SmsError('Brak konfiguracji Twilio')
        result = svc.send_booking_confirmation(55, hold=True)
        assert result['status'] == 'failed'
        assert svc._appt_repo.set_sms_hold.call_args_list[-1].args == (55, False)

    def test_unexpected_crash_never_propagates_and_still_lifts_the_hold(self):
        svc = _svc()
        svc.send.side_effect = RuntimeError('boom')
        result = svc.send_booking_confirmation(55, hold=True)      # must not raise
        assert result['status'] == 'failed'
        assert svc._appt_repo.set_sms_hold.call_args_list[-1].args == (55, False)

    def test_lifting_the_hold_failing_does_not_raise_either(self):
        svc = _svc()
        svc.send.return_value = {'success': False, 'error': 'x'}
        svc._appt_repo.set_sms_hold.side_effect = [True, RuntimeError('db gone')]
        assert svc.send_booking_confirmation(55, hold=True)['status'] == 'failed'


class TestSkipped:
    """No text goes out ⇒ no hold: a visit must never wait for a link nobody will send."""

    @pytest.mark.parametrize('kwargs', [
        {'active': False}, {'enabled': False}, {'type_exists': False},
    ], ids=['sms-off', 'type-disabled', 'type-missing']
    )
    def test_nothing_sent_and_nothing_held(self, kwargs):
        svc = _svc(**kwargs)
        assert svc.send_booking_confirmation(55, hold=True) == {'status': 'skipped', 'hold': False}
        svc._appt_repo.set_sms_hold.assert_not_called()
        svc.send.assert_not_called()
