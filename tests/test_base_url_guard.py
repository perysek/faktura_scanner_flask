"""Decision D5 — one canonical HTTPS domain for SMS links; refuse to start the scheduler
without it (SMS review P1-9).

Unset BASE_URL used to ship `http://localhost:5000/confirm/…` in real client texts; a raw-IP
`http://` link is what carriers flag as spam and it carries single-use tokens in clear.
"""
import logging
from unittest.mock import patch

import pytest

from utils.base_url import enforce_sms_base_url, sms_link_base_url_problems

GOOD = 'https://www.my-way-solutions.com'


class TestProblems:
    @pytest.mark.parametrize('url', [GOOD, 'https://staging.my-way-solutions.com/', 'https://salon.pl:8443'])
    def test_canonical_https_domains_are_fine(self, url):
        assert sms_link_base_url_problems(url) == []

    @pytest.mark.parametrize('url, needle', [
        (None, 'not set'), ('', 'not set'), ('   ', 'not set'),
        ('http://localhost:5000', 'localhost'),                     # the old silent default
        ('https://localhost', 'localhost'),
        ('http://127.0.0.1:8083', '127.0.0.1'),
        ('https://[::1]/', '::1'),
        ('http://0.0.0.0', '0.0.0.0'),
        ('http://70.34.252.120/', 'raw IP'),                         # prod today: raw IP over http
        ('https://70.34.252.120', 'raw IP'),
        ('http://www.my-way-solutions.com', 'not https'),
        ('www.my-way-solutions.com', 'no host'),                     # scheme-less → no hostname
    ])
    def test_unusable_base_urls_are_explained(self, url, needle):
        problems = sms_link_base_url_problems(url)
        assert problems and any(needle in p for p in problems), problems

    def test_http_raw_ip_reports_both_problems(self):
        assert len(sms_link_base_url_problems('http://70.34.252.120/')) == 2


class TestEnforcement:
    def test_production_with_scheduler_and_bad_url_refuses_to_start(self):
        with pytest.raises(RuntimeError) as exc:
            enforce_sms_base_url('http://localhost:5000', scheduler_enabled=True, production=True)
        message = str(exc.value)
        assert 'Refusing to start' in message and 'BASE_URL' in message
        assert 'ENABLE_SMS_SCHEDULER=0' in message          # tells the operator the other way out

    def test_production_with_scheduler_and_good_url_starts(self):
        enforce_sms_base_url(GOOD, scheduler_enabled=True, production=True)

    def test_instance_that_does_not_send_texts_is_only_warned(self, caplog):
        with caplog.at_level(logging.WARNING):
            enforce_sms_base_url('http://localhost:5000', scheduler_enabled=False, production=True)
        assert any('SMS link base URL problem' in r.message for r in caplog.records)

    @pytest.mark.parametrize('scheduler', [True, False])
    def test_dev_and_tests_may_use_localhost_silently(self, caplog, scheduler):
        with caplog.at_level(logging.WARNING):
            enforce_sms_base_url('http://localhost:5000', scheduler_enabled=scheduler, production=False)
        assert not caplog.records


class TestAppFactoryBoot:
    """The guard is really wired into create_app — and sits OUTSIDE the scheduler's try/except,
    which would otherwise swallow the very error that is meant to stop the boot."""

    def _build(self, monkeypatch, **env):
        monkeypatch.setenv('SECRET_KEY', 'b1946ac92492d2347c6235b4d2611184b1946ac92492d2347c6235b4d2611184')
        monkeypatch.setenv('DATABASE_URL', 'postgresql://test:test@localhost/test')
        for key in ('BASE_URL', 'ENABLE_SMS_SCHEDULER', 'FLASK_ENV'):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        with patch('config.database.initialize_pool', return_value=None), \
             patch('config.database.initialize_database', return_value=None), \
             patch('scheduler.start_scheduler', return_value=None):
            from app import create_app
            return create_app()

    def test_production_scheduler_on_without_base_url_does_not_boot(self, monkeypatch):
        with pytest.raises(RuntimeError, match='Refusing to start'):
            self._build(monkeypatch, FLASK_ENV='production', ENABLE_SMS_SCHEDULER='1')

    def test_production_scheduler_on_with_raw_ip_http_does_not_boot(self, monkeypatch):
        with pytest.raises(RuntimeError, match='raw IP'):
            self._build(monkeypatch, FLASK_ENV='production', BASE_URL='http://70.34.252.120/')

    def test_production_scheduler_off_boots_without_base_url(self, monkeypatch):
        assert self._build(monkeypatch, FLASK_ENV='production', ENABLE_SMS_SCHEDULER='0') is not None

    def test_production_with_canonical_domain_boots(self, monkeypatch):
        app = self._build(monkeypatch, FLASK_ENV='production', BASE_URL=GOOD)
        assert app.config['BASE_URL'] == GOOD

    def test_development_boots_on_the_localhost_default(self, monkeypatch):
        assert self._build(monkeypatch, FLASK_ENV='development') is not None
