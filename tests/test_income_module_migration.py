"""Shape of the 'income' module revision (Finanse → Przychody access switch).

The live database is shared with the legacy salon app (:8083), so the revision must be
ADDITIVE ONLY. Reads the migration file — no database.
"""
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[1]
_REVISION = 'a7c4e1f9b3d2'


def _script():
    return ScriptDirectory.from_config(Config(str(_ROOT / 'alembic.ini')))


def _upgrade():
    src = Path(_script().get_revision(_REVISION).path).read_text(encoding='utf-8')
    return src.split('def upgrade', 1)[1].split('def downgrade', 1)[0]


def test_sits_on_the_absence_conflict_pending_revision():
    assert _script().get_revision(_REVISION).down_revision == 'f3c7a1d9e2b4'


def test_is_on_the_line_to_the_current_head():
    script = _script()
    heads = script.get_heads()
    assert len(heads) == 1
    assert _REVISION in {r.revision for r in script.walk_revisions('base', heads[0])}


def test_upgrade_is_additive_only():
    up = _upgrade()
    assert not re.search(r'\bDROP\b|\bRENAME\b|ALTER\s+COLUMN|\bTRUNCATE\b|\bDELETE\b|\bUPDATE\b', up, re.I)
    assert 'ON CONFLICT (role_id, module_name) DO NOTHING' in up


def test_only_superuser_and_admin_start_with_access():
    assert "(r.name IN ('superuser', 'admin'))" in _upgrade()
