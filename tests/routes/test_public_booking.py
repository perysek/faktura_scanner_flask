"""POST /api/public/book and GET /booking — SMS review P0-4, decision D4.

What must hold for an unauthenticated endpoint that can create clients, block the
calendar and cause SMS to be sent to arbitrary phone numbers:
  * garbage in → 400, nothing written;
  * a failed human check → nothing written (and validation runs BEFORE the single-use
    Turnstile token is spent);
  * a visit is attached to an existing client only on an EXACT phone match + same surname;
  * a stranger typing someone else's number cannot start a reminder stream (hold);
  * the endpoint is rate limited per visitor IP and per phone number.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.turnstile_service import FAILED, PASSED, SKIPPED, UNAVAILABLE, TurnstileResult

ROUTES = 'routes.booking_routes'

PAYLOAD = {
    'service_ids': [1], 'employee_id': 3, 'date': '2030-01-15', 'start_time': '10:00',
    'first_name': 'Anna', 'last_name': 'Kowalska', 'phone': '600 123 456',
    'email': None, 'notes': None, 'turnstile_token': 'tok',
}


def body(**overrides):
    return {**PAYLOAD, **overrides}


def client_row(cid=7, first='Anna', last='Kowalska', phone='+48600123456'):
    return {'id': cid, 'first_name': first, 'last_name': last, 'phone': phone}


class Harness:
    """Replaces every collaborator of the booking route with a recorded fake."""

    def __init__(self, app, *, by_phone=(), by_email=None, verified=False,
                 verdict=PASSED, sms=None):
        self.app = app
        self.clients = MagicMock()
        self.clients.find_by_phone_keys.return_value = list(by_phone)
        self.clients.find_by_email.return_value = by_email
        self.clients.create.return_value = 900
        self.clients.has_verified_history.return_value = verified
        self.appointments = MagicMock()
        self.appointments.create_appointment.return_value = {
            'appointment_id': 55, 'total_price': Decimal('120.00'), 'total_duration': 60, 'end_time': '11:00'}
        self.sms = MagicMock()
        self.sms.send_booking_confirmation.return_value = sms or {'status': 'skipped', 'hold': False}
        self.audit = MagicMock()
        self.verdict = TurnstileResult(verdict)
        self._patches = []

    def __enter__(self):
        self.verify = MagicMock(return_value=self.verdict)
        for target, value in [
            (f'{ROUTES}.ClientRepository', MagicMock(return_value=self.clients)),
            (f'{ROUTES}.AppointmentBusinessService', MagicMock(return_value=self.appointments)),
            (f'{ROUTES}.SmsService', MagicMock(return_value=self.sms)),
            (f'{ROUTES}.AuditRepository', MagicMock(return_value=self.audit)),
            (f'{ROUTES}.turnstile.verify', self.verify),
        ]:
            p = patch(target, value)
            p.start()
            self._patches.append(p)
        self.http = self.app.test_client()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()

    def post(self, payload=None, **kwargs):
        return self.http.post('/api/public/book', json=PAYLOAD if payload is None else payload, **kwargs)

    @property
    def created_nothing(self):
        return not self.clients.create.called and not self.appointments.create_appointment.called


class TestValidation:
    @pytest.mark.parametrize('phone', ['600', '12', '', None, 'abc', '+48 12', '6001234567', 123456789,
                                       "600123456'; DROP TABLE clients;--"])
    def test_invalid_phone_is_a_polish_400_and_nothing_is_written(self, app, phone):
        with Harness(app) as h:
            resp = h.post(body(phone=phone))
        assert resp.status_code == 400
        assert 'numer telefonu' in resp.get_json()['error'].lower()
        assert h.created_nothing
        h.clients.find_by_phone_keys.assert_not_called()      # '600' must never even reach the lookup

    @pytest.mark.parametrize('field, value', [
        ('first_name', 'A' * 101), ('last_name', 'K' * 101), ('first_name', '  '), ('last_name', None),
        ('first_name', 'An\x00na'), ('email', 'not-an-email'), ('email', 'a' * 251 + '@x.pl'),
        ('notes', 'n' * 501), ('first_name', ['Anna']), ('date', ''), ('start_time', None),
    ])
    def test_bad_fields_are_rejected(self, app, field, value):
        with Harness(app) as h:
            resp = h.post(body(**{field: value}))
        assert resp.status_code == 400, resp.get_json()
        assert h.created_nothing

    @pytest.mark.parametrize('payload', [None, [], 'text', 42])
    def test_non_object_body_is_400(self, app, payload):
        with Harness(app) as h:
            resp = h.http.post('/api/public/book', json=payload)
        assert resp.status_code == 400 and h.created_nothing

    def test_malformed_ids_are_400_not_500(self, app):
        with Harness(app) as h:
            assert h.post(body(employee_id='x')).status_code == 400
            assert h.post(body(service_ids=['a'])).status_code == 400
            assert h.post(body(service_ids=[1, 2, 3, 4])).status_code == 400
            assert h.post(body(service_ids=[])).status_code == 400
        assert h.created_nothing

    def test_validation_runs_before_the_single_use_turnstile_token_is_spent(self, app):
        with Harness(app) as h:
            h.post(body(phone='600'))
        h.verify.assert_not_called()

    def test_valid_booking_is_201_and_stores_e164(self, app):
        with Harness(app) as h:
            resp = h.post(body(phone='600-123-456'))
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True and data['appointment_id'] == 55 and data['total_price'] == 120.0
        created = h.clients.create.call_args.args[0]
        assert created.phone == '+48600123456' and len(created.phone) <= 20     # fits VARCHAR(20)
        assert h.appointments.create_appointment.call_args.kwargs['created_by'] is None

    def test_legacy_single_service_id_still_works(self, app):
        with Harness(app) as h:
            resp = h.post({**body(), 'service_ids': None, 'service_id': 4})
        assert resp.status_code == 201
        assert h.appointments.create_appointment.call_args.kwargs['service_ids'] == [4]


class TestTurnstileGate:
    def test_failed_human_check_creates_nothing(self, app):
        with Harness(app, verdict=FAILED) as h:
            resp = h.post()
        assert resp.status_code == 400 and 'robotem' in resp.get_json()['error']
        assert h.created_nothing

    def test_no_verdict_is_fail_closed_503(self, app):
        with Harness(app, verdict=UNAVAILABLE) as h:
            resp = h.post()
        assert resp.status_code == 503 and 'chwilowo niedostępna' in resp.get_json()['error']
        assert h.created_nothing

    def test_skipped_when_not_configured_booking_proceeds(self, app):
        with Harness(app, verdict=SKIPPED) as h:
            assert h.post().status_code == 201

    def test_verifies_our_host_our_action_and_the_real_visitor_ip(self, app):
        with Harness(app) as h:
            h.post(body(turnstile_token='THE-TOKEN'),
                   headers={'Host': 'www.salon.test:8443', 'CF-Connecting-IP': '198.51.100.23'})
        args, kwargs = h.verify.call_args
        assert args == ('THE-TOKEN',)
        assert kwargs['expected_hostname'] == 'www.salon.test'          # port stripped
        assert kwargs['expected_action'] == 'public_booking'            # same action the page renders
        assert kwargs['remote_ip'] == '198.51.100.23'                   # not the Cloudflare edge address


class TestClientResolution:
    def test_exact_phone_and_same_surname_reuses_the_client(self, app):
        with Harness(app, by_phone=[client_row(7, last='Kowalska')]) as h:
            resp = h.post(body(last_name='  KOWALSKA '))
        assert resp.status_code == 201
        h.clients.create.assert_not_called()
        assert h.appointments.create_appointment.call_args.kwargs['client_id'] == 7

    def test_lookup_is_by_exact_keys_never_a_substring(self, app):
        with Harness(app) as h:
            h.post(body(phone='+48 600 123 456'))
        keys = h.clients.find_by_phone_keys.call_args.args[0]
        assert {'600123456', '48600123456', '0600123456', '0048600123456'} <= set(keys)
        assert all(len(k) >= 9 for k in keys)

    def test_same_phone_different_surname_is_not_attached_and_is_flagged(self, app):
        # The stranger-types-your-number scenario.
        with Harness(app, by_phone=[client_row(7, last='Nowak')]) as h:
            resp = h.post(body(last_name='Kowalska'))
        assert resp.status_code == 201
        created = h.clients.create.call_args.args[0]
        assert h.appointments.create_appointment.call_args.kwargs['client_id'] == 900
        assert 'do weryfikacji' in created.notes and '#7' in created.notes

    def test_surname_comparison_ignores_case_and_polish_diacritics(self, app):
        with Harness(app, by_phone=[client_row(7, last='Łukaszewicz')]) as h:
            h.post(body(last_name='lukaszewicz'))
        h.clients.create.assert_not_called()

    def test_blank_stored_surname_falls_back_to_first_name(self, app):
        with Harness(app, by_phone=[client_row(7, first='Anna', last='')]) as h:
            h.post(body(first_name='anna'))
        h.clients.create.assert_not_called()

    def test_second_candidate_with_matching_surname_wins(self, app):
        rows = [client_row(7, last='Nowak'), client_row(8, last='Kowalska')]
        with Harness(app, by_phone=rows) as h:
            h.post()
        assert h.appointments.create_appointment.call_args.kwargs['client_id'] == 8

    def test_email_match_with_same_surname_reuses_that_client(self, app):
        with Harness(app, by_email=client_row(12, last='Kowalska')) as h:
            h.post(body(email='anna@example.com'))
        assert h.appointments.create_appointment.call_args.kwargs['client_id'] == 12
        h.clients.create.assert_not_called()

    def test_email_belonging_to_another_surname_does_not_hit_the_unique_constraint(self, app):
        # clients.email is UNIQUE: creating the new client WITH that email would be a 500.
        with Harness(app, by_email=client_row(12, last='Nowak')) as h:
            resp = h.post(body(email='nowak@example.com'))
        assert resp.status_code == 201
        created = h.clients.create.call_args.args[0]
        assert created.email is None and '#12' in created.notes


class TestConfirmationSmsAndHold:
    def test_unverified_new_client_is_held_and_told_to_confirm(self, app):
        with Harness(app, sms={'status': 'sent', 'hold': True}) as h:
            data = h.post().get_json()
        h.sms.send_booking_confirmation.assert_called_once_with(55, hold=True)
        assert data['confirmation_sms'] == 'sent' and data['confirmation_required'] is True

    def test_existing_client_without_history_is_still_unverified(self, app):
        with Harness(app, by_phone=[client_row(7)], verified=False) as h:
            h.post()
        h.sms.send_booking_confirmation.assert_called_once_with(55, hold=True)

    def test_returning_verified_client_is_not_held(self, app):
        # A5 — their reminders flow exactly as before.
        with Harness(app, by_phone=[client_row(7)], verified=True, sms={'status': 'sent', 'hold': False}) as h:
            data = h.post().get_json()
        h.sms.send_booking_confirmation.assert_called_once_with(55, hold=False)
        assert data['confirmation_required'] is False

    def test_sms_switched_off_still_books(self, app):
        with Harness(app, sms={'status': 'skipped', 'hold': False}) as h:
            resp = h.post()
        assert resp.status_code == 201 and resp.get_json()['confirmation_sms'] == 'skipped'

    def test_a_crashing_sms_service_never_fails_the_booking(self, app):
        with Harness(app) as h:
            h.sms.send_booking_confirmation.side_effect = RuntimeError('twilio exploded')
            resp = h.post()
        assert resp.status_code == 201
        assert resp.get_json()['confirmation_sms'] == 'failed'


class TestRateLimits:
    """The limiter is live in tests; every test's fresh `app` has fresh counters."""

    def test_per_ip_limit_counts_every_attempt_and_answers_in_polish_json(self, app):
        with Harness(app) as h:
            codes = [h.post(body(phone='600'), headers={'CF-Connecting-IP': '198.51.100.1'}).status_code
                     for _ in range(10)]
            blocked = h.post(body(phone='600'), headers={'CF-Connecting-IP': '198.51.100.1'})
        assert codes == [400] * 10
        assert blocked.status_code == 429
        assert 'Zbyt wiele prób' in blocked.get_json()['error']

    def test_buckets_follow_the_real_visitor_not_the_cloudflare_edge(self, app):
        # Same socket address (the edge) for everyone; only CF-Connecting-IP differs.
        with Harness(app) as h:
            for _ in range(11):
                h.post(body(phone='600'), headers={'CF-Connecting-IP': '198.51.100.1'})
            other_visitor = h.post(body(phone='600'), headers={'CF-Connecting-IP': '198.51.100.2'})
        assert other_visitor.status_code == 400          # not throttled with the first visitor

    def test_per_phone_budget_counts_only_successful_bookings(self, app):
        with Harness(app) as h:
            failed = [h.post(body(email='broken')).status_code for _ in range(4)]      # valid phone, 400s
            ok = [h.post().status_code for _ in range(3)]
            fourth = h.post()
            other_phone = h.post(body(phone='601 000 111'))
        assert failed == [400] * 4                       # failures did not burn the phone's budget
        assert ok == [201, 201, 201]
        assert fourth.status_code == 429
        assert other_phone.status_code == 201            # a different number is unaffected

    def test_same_number_in_any_spelling_shares_one_budget(self, app):
        with Harness(app) as h:
            for spelling in ('600123456', '+48 600 123 456', '600-123-456'):
                assert h.post(body(phone=spelling)).status_code == 201
            assert h.post(body(phone='0600123456')).status_code == 429


class TestBookingPage:
    def test_widget_and_script_render_only_when_a_site_key_is_configured(self, app):
        app.config['TURNSTILE_SITE_KEY'] = '0xPUBLICSITEKEY'
        html = app.test_client().get('/booking').get_data(as_text=True)
        app.config['TURNSTILE_SITE_KEY'] = ''
        assert 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit' in html
        assert 'id="ts-widget"' in html
        assert 'const TURNSTILE_SITE_KEY = "0xPUBLICSITEKEY"' in html
        assert 'const TURNSTILE_ACTION = "public_booking"' in html

    def test_no_site_key_means_no_widget_no_script_no_token_requirement(self, app):
        app.config['TURNSTILE_SITE_KEY'] = ''
        html = app.test_client().get('/booking').get_data(as_text=True)
        assert 'challenges.cloudflare.com' not in html
        assert 'id="ts-widget"' not in html
        assert 'const TURNSTILE_SITE_KEY = ""' in html

    def test_page_script_wires_token_reset_and_the_sms_note(self, app):
        html = app.test_client().get('/booking').get_data(as_text=True)
        assert 'turnstile_token: tsToken' in html                       # sent with the booking
        assert 'resetTurnstile();' in html                              # single-use token: re-solve after a failure
        assert 'if (n === 4) renderTurnstile();' in html                # drawn lazily when the contact step opens
        assert "'error-callback'" in html and 'role="alert"' in html    # failures are announced
        assert 'id="conf-sms-note"' in html

    def test_secret_key_never_reaches_the_page(self, app):
        app.config['TURNSTILE_SITE_KEY'] = '0xPUBLIC'
        app.config['TURNSTILE_SECRET_KEY'] = 'TOP-SECRET-VALUE'
        html = app.test_client().get('/booking').get_data(as_text=True)
        app.config['TURNSTILE_SITE_KEY'] = app.config['TURNSTILE_SECRET_KEY'] = ''
        assert 'TOP-SECRET-VALUE' not in html
