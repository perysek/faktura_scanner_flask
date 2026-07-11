"""Regression tests for the EmailSettings staleness bug.

Bug: get_settings()/load_email_settings() returned a copy cached at instance
creation time (or at the last save_settings() call), so upload.html's
"Wybierz foldery" (which reads settings via load_email_settings()) could use
stale or wrong credentials while settings/email.html's "Testuj polaczenie"
(which always sends the live form values) kept succeeding — same screen,
two different data sources.
"""
from config.email_settings import EmailSettings


def _make_settings(tmp_path):
    settings = EmailSettings.__new__(EmailSettings)
    settings.config_file = tmp_path / "email_config.json"
    settings.settings = settings.load_settings()
    return settings


class TestGetSettingsFreshness:
    def test_get_settings_reflects_file_change_after_construction(self, tmp_path, monkeypatch):
        monkeypatch.delenv('IMAP_PASSWORD', raising=False)
        monkeypatch.delenv('IMAP_EMAIL', raising=False)

        settings = _make_settings(tmp_path)
        settings.save_settings({
            'email': 'old@example.com',
            'password': 'old-pass',
            'imap_server': 'imap.old.com',
            'imap_port': 993,
        })

        # A second reader (e.g. a request handler on another thread) writes
        # new settings via the same on-disk config after this instance exists.
        other = _make_settings(tmp_path)
        other.save_settings({
            'email': 'new@example.com',
            'password': 'new-pass',
            'imap_server': 'imap.new.com',
            'imap_port': 993,
        })

        # The first instance must not keep serving what it cached at
        # construction/last-save time.
        assert settings.get_settings()['email'] == 'new@example.com'
        assert settings.get_settings()['imap_server'] == 'imap.new.com'

    def test_save_settings_does_not_override_env_password_with_stale_submission(self, tmp_path, monkeypatch):
        monkeypatch.setenv('IMAP_PASSWORD', 'env-truth-password')
        monkeypatch.delenv('IMAP_EMAIL', raising=False)

        settings = _make_settings(tmp_path)

        # Simulate the settings page submitting a form that (for whatever
        # reason — stale tab, autofill) carries an outdated password value.
        settings.save_settings({
            'email': 'user@example.com',
            'password': 'stale-typed-password',
            'imap_server': 'imap.example.com',
            'imap_port': 993,
        })

        # load_email_settings()/get_settings() must still resolve to the
        # env var, matching what a fresh /email/test call would use.
        assert settings.get_settings()['password'] == 'env-truth-password'
