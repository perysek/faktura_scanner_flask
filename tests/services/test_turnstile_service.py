"""Cloudflare Turnstile server-side verification (SMS review P0-4, decision D4).

Cloudflare is never contacted: `post` is injected. The rules under test:
  * a verdict must be obtained — no verdict (outage, wrong OUR-secret) is fail-CLOSED;
  * `success: true` alone is not enough — hostname and action must be ours;
  * no secret configured = feature not switched on = skipped (explicitly NOT fail-closed).
"""
import logging

import pytest
import requests

from services import turnstile_service as ts

SECRET = 'real-looking-secret-not-a-dummy'
DUMMY_PASS = '1x0000000000000000000000000000000AA'    # Cloudflare's published always-pass secret


class FakeResponse:
    def __init__(self, body=None, status=200, json_error=None):
        self._body, self.status_code, self._json_error = body, status, json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._body


class FakePost:
    def __init__(self, response=None, raises=None):
        self.response, self.raises, self.calls = response, raises, []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.raises:
            raise self.raises
        return self.response


def verify(token='tok', post=None, **kw):
    kw.setdefault('secret', SECRET)
    return ts.verify(token, post=post or FakePost(FakeResponse({'success': True})), **kw)


class TestPassedAndPayload:
    def test_valid_token_passes_and_posts_the_documented_payload(self):
        post = FakePost(FakeResponse({'success': True, 'hostname': 'www.salon.pl', 'action': 'public_booking'}))
        result = ts.verify('TOKEN', remote_ip='203.0.113.9', expected_hostname='www.salon.pl',
                           expected_action='public_booking', secret=SECRET, post=post)
        assert result.outcome == ts.PASSED and result.ok
        url, kwargs = post.calls[0]
        assert url == 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
        assert kwargs['data'] == {'secret': SECRET, 'response': 'TOKEN', 'remoteip': '203.0.113.9'}
        assert kwargs['timeout'] == 5, 'a hung Cloudflare call must not hang the booking request'

    def test_remote_ip_is_optional(self):
        post = FakePost(FakeResponse({'success': True}))
        verify(post=post)
        assert 'remoteip' not in post.calls[0][1]['data']

    def test_hostname_comparison_ignores_case(self):
        post = FakePost(FakeResponse({'success': True, 'hostname': 'WWW.Salon.PL'}))
        assert verify(post=post, expected_hostname='www.salon.pl').outcome == ts.PASSED


class TestFailed:
    @pytest.mark.parametrize('token', [None, '', '   ', 123, ['x']])
    def test_missing_token_fails_without_calling_cloudflare(self, token):
        post = FakePost(FakeResponse({'success': True}))
        result = verify(token, post=post)
        assert result.outcome == ts.FAILED and 'missing-input-response' in result.error_codes
        assert post.calls == []

    def test_oversized_token_fails_without_calling_cloudflare(self):
        post = FakePost(FakeResponse({'success': True}))
        result = verify('x' * (ts.MAX_TOKEN_LENGTH + 1), post=post)
        assert result.outcome == ts.FAILED and post.calls == []

    @pytest.mark.parametrize('code', ['timeout-or-duplicate', 'invalid-input-response'])
    def test_rejected_token_is_a_visitor_problem_not_an_outage(self, code):
        post = FakePost(FakeResponse({'success': False, 'error-codes': [code]}))
        result = verify(post=post)
        assert result.outcome == ts.FAILED and result.error_codes == (code,) and not result.ok

    def test_success_true_for_another_hostname_is_rejected(self):
        # A token solved on someone else's site (or a scraped test page) says success:true too.
        post = FakePost(FakeResponse({'success': True, 'hostname': 'evil.example', 'action': 'public_booking'}))
        result = verify(post=post, expected_hostname='www.salon.pl', expected_action='public_booking')
        assert result.outcome == ts.FAILED and result.error_codes == ('hostname-mismatch',)

    def test_success_true_for_another_action_is_rejected(self):
        post = FakePost(FakeResponse({'success': True, 'hostname': 'www.salon.pl', 'action': 'login'}))
        result = verify(post=post, expected_hostname='www.salon.pl', expected_action='public_booking')
        assert result.outcome == ts.FAILED and result.error_codes == ('action-mismatch',)

    def test_dummy_test_secret_skips_hostname_and_action_checks(self):
        # Cloudflare's test keys answer with a fixed example hostname; enforcing it would
        # make local/dev use impossible.
        post = FakePost(FakeResponse({'success': True, 'hostname': 'example.com'}))
        result = ts.verify('tok', secret=DUMMY_PASS, post=post,
                           expected_hostname='localhost', expected_action='public_booking')
        assert result.outcome == ts.PASSED


class TestUnavailableIsFailClosed:
    @pytest.mark.parametrize('exc', [requests.ConnectionError('dns'), requests.Timeout('slow'),
                                     requests.exceptions.SSLError('tls')])
    def test_network_errors_give_no_verdict(self, exc):
        result = verify(post=FakePost(raises=exc))
        assert result.outcome == ts.UNAVAILABLE and not result.ok

    @pytest.mark.parametrize('status', [500, 502, 503])
    def test_cloudflare_5xx_gives_no_verdict(self, status):
        result = verify(post=FakePost(FakeResponse({}, status=status)))
        assert result.outcome == ts.UNAVAILABLE and not result.ok

    def test_unparsable_reply_gives_no_verdict(self):
        result = verify(post=FakePost(FakeResponse(json_error=ValueError('not json'))))
        assert result.outcome == ts.UNAVAILABLE

    def test_non_object_json_gives_no_verdict(self):
        assert verify(post=FakePost(FakeResponse(['nope']))).outcome == ts.UNAVAILABLE

    @pytest.mark.parametrize('code', ['invalid-input-secret', 'missing-input-secret'])
    def test_our_own_bad_secret_is_unavailable_not_the_visitors_fault(self, code, caplog):
        post = FakePost(FakeResponse({'success': False, 'error-codes': [code]}))
        with caplog.at_level(logging.ERROR):
            result = verify(post=post)
        assert result.outcome == ts.UNAVAILABLE
        assert any('rejected OUR secret' in r.message for r in caplog.records)


class TestSkippedWhenNotConfigured:
    @pytest.fixture(autouse=True)
    def _reset_warning_latch(self, monkeypatch):
        monkeypatch.setattr(ts, '_warned_unconfigured', False)

    def test_no_secret_skips_and_never_calls_cloudflare(self, app):
        app.config['TURNSTILE_SECRET_KEY'] = ''
        post = FakePost(FakeResponse({'success': True}))
        with app.app_context():
            result = ts.verify('whatever', post=post)
        assert result.outcome == ts.SKIPPED and result.ok
        assert post.calls == []

    def test_warns_once_not_on_every_request(self, app, caplog):
        app.config['TURNSTILE_SECRET_KEY'] = ''
        with app.app_context(), caplog.at_level(logging.WARNING):
            ts.verify(None, post=FakePost())
            ts.verify(None, post=FakePost())
        assert len([r for r in caplog.records if 'NOT bot-protected' in r.message]) == 1

    def test_secret_is_read_from_app_config_by_default(self, app):
        app.config['TURNSTILE_SECRET_KEY'] = SECRET
        post = FakePost(FakeResponse({'success': True}))
        with app.app_context():
            result = ts.verify('tok', post=post)
        app.config['TURNSTILE_SECRET_KEY'] = ''
        assert result.outcome == ts.PASSED and post.calls[0][1]['data']['secret'] == SECRET


def test_dummy_secret_detection():
    assert ts.is_dummy_secret(DUMMY_PASS)
    assert ts.is_dummy_secret('2x0000000000000000000000000000000AA')
    assert not ts.is_dummy_secret(SECRET)
    assert not ts.is_dummy_secret('')
