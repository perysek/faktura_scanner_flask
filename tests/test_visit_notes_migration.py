"""Shape of the visit_notes Alembic revision.

The live database is shared with the production salon app, so this revision must
be additive only: it creates one table (and its indexes) and its downgrade
removes exactly that table. These tests read the migration *file* — no database
needed — and complement tests/test_migration_chain.py (single head / single base).
"""
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[1]
_PREVIOUS_HEAD = 'f4a8b2c9d1e7'


def _script():
    return ScriptDirectory.from_config(Config(str(_ROOT / 'alembic.ini')))


def _head_revision():
    script = _script()
    return script.get_revision(script.get_current_head())


def _source():
    return Path(_head_revision().path).read_text(encoding='utf-8')


class TestVisitNotesMigration:
    def test_sits_directly_on_the_previous_head(self):
        assert _head_revision().down_revision == _PREVIOUS_HEAD

    def test_creates_visit_notes_with_the_expected_columns(self):
        src = _source()
        assert "op.create_table(\n        'visit_notes'" in src or "op.create_table('visit_notes'" in src
        for column in ('appointment_id', 'note_text', 'created_at', 'created_by',
                       'updated_at', 'updated_by', 'is_deleted', 'deleted_at'):
            assert f"'{column}'" in src, f'missing column {column}'

    def test_note_belongs_to_a_visit_and_dies_with_it(self):
        src = _source()
        assert "['appointments.id']" in src
        assert "ondelete='CASCADE'" in src

    def test_has_the_list_index(self):
        assert 'idx_visit_notes_appointment' in _source()

    def test_is_additive_only(self):
        """No ALTER/ADD/DROP COLUMN, and no drop of any table but visit_notes."""
        src = _source()
        assert not re.search(r'op\.(alter_column|add_column|drop_column|rename_table)', src)
        dropped = re.findall(r"op\.drop_table\(\s*'([^']+)'", src)
        assert dropped == ['visit_notes']

    def test_downgrade_removes_the_table(self):
        src = _source()
        downgrade = src.split('def downgrade', 1)[1]
        assert "op.drop_table('visit_notes')" in downgrade
