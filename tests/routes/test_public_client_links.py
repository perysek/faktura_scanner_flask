"""Public client pages reached from SMS links: /confirm/<token> and /cancel/<token>.

Covers SMS review P0-3 (decline really cancels, two-step), D3 (12 h cut-off), the
"Umów nowy termin" way back, GET-never-writes (link-preview bots and mail/SMS
scanners fetch these URLs), and P3-1 (pages must define the CSS tokens they use).
"""
import re
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROUTES = 'routes.public_routes'
SVC = 'services.client_cancellation_service'
START = datetime(2026, 7, 2, 14, 0)


def appt(status='scheduled', confirmation_status=None, **extra):
    return {'id': 100, 'status': status, 'confirmation_status': confirmation_status,
            'appointment_date': START.date(), 'start_time': START.time(),
            'employee_name': 'Ola Nowak', 'client_id': 1, **extra}


@contextmanager
def _noop_tx():
    yield


class World:
    """Patches every collaborator of the public routes + the cancellation service."""

    def __init__(self, app, row, hours_before=48):
        self.app = app
        self.repo = MagicMock()
        self.repo.get_by_confirmation_token.return_value = row
        self.effects = MagicMock()
        self.sms_events = MagicMock()
        self.status_events = MagicMock()
        self.audit = MagicMock()
        self.hours_before = hours_before
        self.stack = ExitStack()

    def __enter__(self):
        s = self.stack
        s.enter_context(patch(f'{ROUTES}.AppointmentRepository', return_value=self.repo))
        s.enter_context(patch(f'{ROUTES}.AuditRepository', return_value=self.audit))
        s.enter_context(patch(f'{ROUTES}.managed_transaction', _noop_tx))
        s.enter_context(patch(f'{SVC}.AppointmentRepository', return_value=self.repo))
        s.enter_context(patch(f'{SVC}.AppointmentBusinessService', return_value=self.effects))
        s.enter_context(patch(f'{SVC}.SmsEventRepository', return_value=self.sms_events))
        s.enter_context(patch(f'{SVC}.StatusChangeEventRepository', return_value=self.status_events))
        s.enter_context(patch(f'{SVC}.AuditRepository', return_value=self.audit))
        s.enter_context(patch(f'{SVC}.managed_transaction', _noop_tx))
        s.enter_context(patch(f'{SVC}.now_local', return_value=START - timedelta(hours=self.hours_before)))
        self.client = self.app.test_client()
        return self

    def __exit__(self, *exc):
        self.stack.close()

    def writes(self):
        r = self.repo
        return [n for n in ('update_status', 'update_confirmation_status', 'release_sms_hold')
                if getattr(r, n).called] + (['side_effects'] if self.effects.apply_status_change_side_effects.called else [])


def html(resp):
    return resp.get_data(as_text=True)


class TestGetNeverWrites:
    """A4 — security scanners and chat apps prefetch links; that must be harmless."""

    @pytest.mark.parametrize('url', ['/confirm/tok', '/cancel/tok'])
    @pytest.mark.parametrize('row', [
        appt(), appt('confirmed', 'confirmed'), appt(confirmation_status='declined'),
        appt('cancelled'), appt('completed'),
    ], ids=['open', 'confirmed', 'legacy-declined', 'cancelled', 'completed'])
    def test_get_changes_nothing(self, app, url, row):
        with World(app, row) as w:
            assert w.client.get(url).status_code == 200
        assert w.writes() == []
        w.status_events.create.assert_not_called()

    def test_unknown_token_is_404_with_the_invalid_page(self, app):
        with World(app, None) as w:
            for url in ('/confirm/nope', '/cancel/nope'):
                resp = w.client.get(url)
                assert resp.status_code == 404
                assert 'Nieprawidłowy link' in html(resp)


class TestDeclineIsATwoStepCancel:
    def test_first_click_only_asks_are_you_sure(self, app):
        with World(app, appt()) as w:
            resp = w.client.post('/confirm/tok', data={'action': 'declined'})
        assert resp.status_code == 200
        body = html(resp)
        assert 'Odwołać wizytę?' in body and 'Tak, odwołuję wizytę' in body
        assert 'name="confirm_decline" value="1"' in body
        assert w.writes() == []

    def test_second_click_really_cancels_and_records_the_decline(self, app):
        with World(app, appt('confirmed', 'confirmed')) as w:
            resp = w.client.post('/confirm/tok', data={'action': 'declined', 'confirm_decline': '1'})
        body = html(resp)
        assert 'Wizyta odwołana' in body
        w.repo.update_status.assert_called_once()
        assert w.repo.update_status.call_args.args[:2] == (100, 'cancelled')
        w.repo.update_confirmation_status.assert_called_once_with(100, 'declined')
        w.effects.apply_status_change_side_effects.assert_called_once_with(100, 'confirmed', 'cancelled')
        w.sms_events.cancel_pending_for_appointment.assert_called_once_with(100)
        w.status_events.create.assert_called_once_with(100, 'confirmed', 'cancelled', 'client_sms')

    def test_cancelled_page_offers_the_way_back_to_booking(self, app):
        with World(app, appt()) as w:
            body = html(w.client.post('/confirm/tok', data={'action': 'declined', 'confirm_decline': '1'}))
        assert 'href="/booking"' in body and 'Umów nowy termin' in body

    def test_double_submit_is_idempotent(self, app):
        with World(app, appt('cancelled')) as w:
            body = html(w.client.post('/confirm/tok', data={'action': 'declined', 'confirm_decline': '1'}))
        assert 'Wizyta jest już odwołana' in body
        assert w.writes() == []

    def test_legacy_declined_visit_goes_straight_to_the_are_you_sure_step(self, app):
        # Declined before declines cancelled: slot still held, the old page was a dead end.
        with World(app, appt(confirmation_status='declined')) as w:
            body = html(w.client.get('/confirm/tok'))
        assert 'Odwołać wizytę?' in body
        assert w.writes() == []


class TestCutoffTwelveHours:
    def test_decline_inside_the_cutoff_is_refused_and_writes_nothing(self, app):
        with World(app, appt(), hours_before=11.98) as w:               # 11 h 59 min
            body = html(w.client.post('/confirm/tok', data={'action': 'declined', 'confirm_decline': '1'}))
        assert 'niewiele czasu' in body and '12 godz.' in body
        assert w.writes() == []

    def test_decline_at_twelve_hours_goes_through(self, app):
        with World(app, appt(), hours_before=12.02) as w:
            body = html(w.client.post('/confirm/tok', data={'action': 'declined', 'confirm_decline': '1'}))
        assert 'Wizyta odwołana' in body
        w.repo.update_status.assert_called_once()

    @pytest.mark.parametrize('hours, refused', [(11.98, True), (12.02, False)])
    def test_cancel_link_obeys_the_same_cutoff(self, app, hours, refused):
        with World(app, appt(), hours_before=hours) as w:
            body = html(w.client.post('/cancel/tok'))
        assert ('niewiele czasu' in body) is refused
        assert (w.repo.update_status.called) is (not refused)

    def test_ask_page_hides_decline_inside_the_cutoff_and_says_why(self, app):
        app.config['SALON_PHONE'] = '+48 600 100 200'
        with World(app, appt(), hours_before=5) as w:
            body = html(w.client.get('/confirm/tok'))
        app.config['SALON_PHONE'] = ''
        assert 'Potwierdzam wizytę' in body
        assert 'value="declined"' not in body
        assert 'tel:+48600100200' in body

    def test_ask_page_offers_decline_outside_the_cutoff(self, app):
        with World(app, appt(), hours_before=48) as w:
            body = html(w.client.get('/confirm/tok'))
        assert 'value="declined"' in body

    def test_too_late_page_without_a_configured_phone_still_tells_them_to_call(self, app):
        app.config['SALON_PHONE'] = ''
        with World(app, appt(), hours_before=3) as w:
            body = html(w.client.post('/cancel/tok'))
        assert 'zadzwoń do salonu' in body.lower()


class TestCancelLink:
    def test_ask_page_then_cancel(self, app):
        with World(app, appt()) as w:
            assert 'Anulowanie wizyty' in html(w.client.get('/cancel/tok'))
            body = html(w.client.post('/cancel/tok'))
        assert 'Wizyta odwołana' in body and 'href="/booking"' in body
        w.repo.update_confirmation_status.assert_not_called()            # plain cancel, not a decline

    def test_cancelling_a_completed_visit_is_not_possible(self, app):
        with World(app, appt('completed')) as w:
            body = html(w.client.post('/cancel/tok'))
        assert 'nie wymaga już odpowiedzi' in body
        assert w.writes() == []


class TestConfirm:
    def test_confirm_flips_status_and_releases_the_sms_hold(self, app):
        # C27.2 — clicking the link proves the phone number is theirs: reminders may start.
        with World(app, appt()) as w:
            body = html(w.client.post('/confirm/tok', data={'action': 'confirmed'}))
        assert 'Wizyta potwierdzona' in body
        w.repo.update_confirmation_status.assert_called_once_with(100, 'confirmed')
        w.repo.update_status.assert_called_once_with(100, 'confirmed')
        w.repo.release_sms_hold.assert_called_once_with(100)

    def test_already_confirmed_visit_is_not_rewritten(self, app):
        with World(app, appt('confirmed', 'confirmed')) as w:
            body = html(w.client.post('/confirm/tok', data={'action': 'confirmed'}))
        assert 'Wizyta potwierdzona' in body
        assert w.writes() == []

    def test_invalid_action_is_a_400(self, app):
        with World(app, appt()) as w:
            resp = w.client.post('/confirm/tok', data={'action': 'hack'})
        assert resp.status_code == 400
        assert w.writes() == []

    def test_answering_a_finished_visit_changes_nothing(self, app):
        with World(app, appt('completed')) as w:
            body = html(w.client.post('/confirm/tok', data={'action': 'confirmed'}))
        assert 'nie wymaga już odpowiedzi' in body
        assert w.writes() == []


class TestPublicPagesDefineTheirTokens:
    """P3-1 — these pages don't load input.css; an undefined var(--x) silently computes
    to its initial value (the card background was transparent on the beige page)."""

    PUBLIC = Path(__file__).resolve().parents[2] / 'templates' / 'public'

    @staticmethod
    def _source(path: Path, seen=None) -> str:
        seen = seen or set()
        if path in seen or not path.exists():
            return ''
        seen.add(path)
        text = path.read_text(encoding='utf-8')
        # Comments mention tokens in prose; only real declarations/usages count.
        text = re.sub(r'\{#.*?#\}', '', text, flags=re.S)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        extra = ''
        for ref in re.findall(r"""\{%\s*(?:include|extends|from)\s+['"]([^'"]+)['"]""", text):
            extra += TestPublicPagesDefineTheirTokens._source(path.parents[1] / ref, seen)
        return text + extra

    @pytest.mark.parametrize('name', sorted(p.name for p in (Path(__file__).resolve().parents[2] / 'templates' / 'public').glob('*.html')))
    def test_every_custom_property_used_is_defined(self, name):
        src = self._source(self.PUBLIC / name)
        used = set(re.findall(r'var\(\s*(--[\w-]+)', src))
        defined = set(re.findall(r'(--[\w-]+)\s*:', src))
        assert used <= defined, f'{name}: undefined custom properties {sorted(used - defined)}'
