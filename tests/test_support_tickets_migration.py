"""Shape of the support-tickets revision (tables + 'support_tickets' module).

The live database is shared with the legacy salon app (:8083), so the revision must be
ADDITIVE ONLY. Reads the migration file — no database.
"""
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[1]
_REVISION = 'c5e8a2d4f6b1'


def _script():
    return ScriptDirectory.from_config(Config(str(_ROOT / 'alembic.ini')))


def _upgrade():
    src = Path(_script().get_revision(_REVISION).path).read_text(encoding='utf-8')
    return src.split('def upgrade', 1)[1].split('def downgrade', 1)[0]


def test_sits_on_the_income_module_revision():
    assert _script().get_revision(_REVISION).down_revision == 'a7c4e1f9b3d2'


def test_is_on_the_line_to_the_current_head():
    script = _script()
    heads = script.get_heads()
    assert len(heads) == 1
    assert _REVISION in {r.revision for r in script.walk_revisions('base', heads[0])}


def test_upgrade_is_additive_only():
    up = _upgrade()
    assert not re.search(r'\bDROP\b|\bRENAME\b|ALTER\s+COLUMN|\bTRUNCATE\b|\bDELETE\b|\bUPDATE\b|drop_|alter_column', up, re.I)
    assert 'ON CONFLICT (role_id, module_name) DO NOTHING' in up


def test_creates_the_three_tables():
    up = _upgrade()
    for table in ('support_tickets', 'support_ticket_messages', 'support_ticket_attachments'):
        assert f"'{table}'" in up


def test_only_superuser_starts_with_access():
    assert "(r.name = 'superuser')" in _upgrade()


def test_module_is_registered_everywhere():
    from config.auth_config import MODULE_PERMISSIONS
    from repositories.roles.role_repository import ALL_MODULES, MODULE_DISPLAY_NAMES
    assert 'support_tickets' in MODULE_PERMISSIONS
    assert 'support_tickets' in ALL_MODULES
    assert 'support_tickets' in MODULE_DISPLAY_NAMES
