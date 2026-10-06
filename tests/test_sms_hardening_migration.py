"""Shape of the SMS-hardening Alembic revision (SMS review WP1).

The live database is shared with the legacy salon app (:8083, branch invoices-app), so this
revision must be ADDITIVE ONLY: every new column has a server default, nothing is dropped or
retyped on the way up. These tests read the migration *file* (no database) and complement
tests/test_migration_chain.py (single head / single base); the behavioural proof — upgrade →
downgrade → upgrade on a real UTC Postgres — is the ISA's verify_wp1.py.
"""
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[1]
_REVISION = 'e2a6c9d4f1b7'
_PREVIOUS = 'b7d3e9a1c4f2'


def _rev():
    return ScriptDirectory.from_config(Config(str(_ROOT / 'alembic.ini'))).get_revision(_REVISION)


def _source():
    return Path(_rev().path).read_text(encoding='utf-8')


def _upgrade():
    src = _source()
    return src.split('def upgrade', 1)[1].split('def downgrade', 1)[0]


def _downgrade():
    return _source().split('def downgrade', 1)[1]


class TestSmsHardeningMigration:
    def test_sits_directly_on_the_visit_notes_revision(self):
        assert _rev().down_revision == _PREVIOUS

    def test_is_the_current_head(self):
        script = ScriptDirectory.from_config(Config(str(_ROOT / 'alembic.ini')))
        assert script.get_heads() == [_REVISION]

    def test_upgrade_is_additive_only(self):
        up = _upgrade()
        assert not re.search(r'\bDROP\b|\bRENAME\b|ALTER\s+COLUMN|\bTYPE\b|\bTRUNCATE\b', up, re.I), \
            'upgrade must not drop, rename, retype or truncate anything the legacy app uses'
        assert not re.search(r'op\.(alter_column|drop_|rename_table)', up)

    def test_new_columns_are_not_null_with_defaults_so_the_legacy_app_keeps_working(self):
        up = _upgrade()
        assert re.search(r"ADD COLUMN IF NOT EXISTS trigger_mode VARCHAR\(20\) NOT NULL DEFAULT 'before_visit'", up)
        assert re.search(r'ADD COLUMN IF NOT EXISTS sms_hold BOOLEAN NOT NULL DEFAULT FALSE', up)

    def test_trigger_mode_is_constrained_to_the_three_known_modes(self):
        assert "CHECK (trigger_mode IN ('before_visit', 'on_status', 'manual'))" in _upgrade()

    def test_booking_confirmed_ships_disabled(self):
        up = _upgrade()
        seed = up.split("'booking_confirmed'", 1)[1].split('ON CONFLICT', 1)[0]
        assert 'FALSE, 0, 0' in seed, 'is_enabled must be FALSE — enabling it is the go-live switch'

    def test_phone_digits_index_matches_the_expression_the_repository_queries(self):
        # The query uses exactly this expression; a different spelling would not use the index.
        expr = "regexp_replace(phone, '[^0-9]', '', 'g')"
        assert expr in _upgrade()
        from repositories.clients.client_repository import ClientRepository
        import inspect
        assert expr in inspect.getsource(ClientRepository.find_by_phone_keys)

    def test_reminder_repair_cancels_moot_events_before_retiming_the_rest(self):
        up = _upgrade()
        cancel_at, retime_at = up.index("SET status = 'cancelled'"), up.index('SET scheduled_at')
        assert cancel_at < retime_at, 'cancel first, or a stale "Za 20 min wizyta" fires at the next tick'
        assert up.count("e.status = 'scheduled'") == 2, 'only still-pending events may be touched'

    def test_downgrade_removes_what_upgrade_added(self):
        down = _downgrade()
        for needle in ('ix_clients_phone_digits', "type_key = 'booking_confirmed'",
                       'DROP COLUMN IF EXISTS sms_hold', 'DROP COLUMN IF EXISTS trigger_mode',
                       'ck_sms_message_types_trigger_mode'):
            assert needle in down, f'downgrade should handle {needle}'
