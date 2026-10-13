"""Shape of the absence_conflict_pending Alembic revision ("Zatwierdź mimo to" deferral).

The live database is shared with the legacy salon app (:8083), so the revision must be
ADDITIVE ONLY. Reads the migration file — no database.
"""
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[1]
_REVISION = 'f3c7a1d9e2b4'


def _script():
    return ScriptDirectory.from_config(Config(str(_ROOT / 'alembic.ini')))


def _upgrade():
    src = Path(_script().get_revision(_REVISION).path).read_text(encoding='utf-8')
    return src.split('def upgrade', 1)[1].split('def downgrade', 1)[0]


def test_sits_on_the_sms_hardening_revision():
    assert _script().get_revision(_REVISION).down_revision == 'e2a6c9d4f1b7'


def test_is_the_current_head():
    assert _script().get_heads() == [_REVISION]


def test_upgrade_is_additive_only():
    up = _upgrade()
    assert not re.search(r'\bDROP\b|\bRENAME\b|ALTER\s+COLUMN|\bTRUNCATE\b', up, re.I)
    assert not re.search(r'op\.(alter_column|drop_|rename_table)', up)


def test_table_carries_the_auto_cancel_moment_and_its_sms_event():
    up = _upgrade()
    assert "'valid_for', sa.DateTime(timezone=True), nullable=False" in up
    assert "['sms_event_id'], ['sms_events.id']" in up
    assert "UniqueConstraint('absence_id', 'appointment_id'" in up


def test_visit_update_sms_type_ships_disabled_and_manual():
    up = _upgrade()
    assert "'absence_visit_update'" in up and 'FALSE, 0, 0' in up and "'manual')" in up
    assert 'ON CONFLICT (type_key) DO NOTHING' in up
