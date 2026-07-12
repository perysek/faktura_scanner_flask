"""Tests for SmsService._build_message()'s {booking_url} handling (Phase 0).

Mirrors the existing confirm_url/cancel_url dual mechanism: substitute in place
if the template already has the placeholder, else append it — but only when the
message type's include_booking_link flag is on.
"""
from datetime import date, time
from unittest.mock import patch

APPT_SVC_GET_ALL = (
    'repositories.appointments.appointment_service_repository'
    '.AppointmentServiceRepository.get_all_for_appointment'
)


def _appt():
    return {
        'id': 42, 'appointment_date': date(2026, 7, 20), 'start_time': time(10, 0),
        'rating_token': '',
    }


def _client():
    return {'first_name': 'Anna'}


def _msg_type(template_text, include_booking_link=True):
    return {
        'template_text': template_text,
        'include_confirm_link': False,
        'include_cancel_link': False,
        'include_rate_link': False,
        'include_booking_link': include_booking_link,
        'send_hours_before': 0,
    }


class TestBuildMessageBookingLink:
    def test_appends_booking_url_when_no_placeholder(self, app):
        from services.sms_service import SmsService
        with app.app_context(), patch(APPT_SVC_GET_ALL, return_value=[]):
            body = SmsService()._build_message(
                _appt(), _client(), _msg_type('Twoja wizyta {date} {time}.'),
                confirm_url='', booking_url='http://x.test/booking',
            )
        assert body.endswith('http://x.test/booking')

    def test_substitutes_placeholder_in_place_no_duplicate(self, app):
        from services.sms_service import SmsService
        with app.app_context(), patch(APPT_SVC_GET_ALL, return_value=[]):
            body = SmsService()._build_message(
                _appt(), _client(),
                _msg_type('Umów nowy termin: {booking_url}. Dzięki!'),
                confirm_url='', booking_url='http://x.test/booking',
            )
        assert body.count('http://x.test/booking') == 1
        assert 'Dzięki!' in body

    def test_omitted_when_include_booking_link_false(self, app):
        from services.sms_service import SmsService
        with app.app_context(), patch(APPT_SVC_GET_ALL, return_value=[]):
            body = SmsService()._build_message(
                _appt(), _client(),
                _msg_type('Twoja wizyta {date} {time}.', include_booking_link=False),
                confirm_url='', booking_url='http://x.test/booking',
            )
        assert 'http://x.test/booking' not in body

    def test_placeholder_removed_when_flag_off(self, app):
        """A template that mentions {booking_url} but has the checkbox off should
        render an empty substitution, not leak the raw placeholder text."""
        from services.sms_service import SmsService
        with app.app_context(), patch(APPT_SVC_GET_ALL, return_value=[]):
            body = SmsService()._build_message(
                _appt(), _client(),
                _msg_type('Link: {booking_url}', include_booking_link=False),
                confirm_url='', booking_url='http://x.test/booking',
            )
        assert '{booking_url}' not in body
        assert 'http://x.test/booking' not in body
