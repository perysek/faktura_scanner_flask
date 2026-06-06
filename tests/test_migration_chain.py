"""
Tests for the Alembic migration chain integrity (improvement area #1).

Since `database/schema.sql` is no longer executed at boot, the Alembic chain is
the *single* source of truth for the schema. These tests guard the chain's
shape so a future migration can't silently:

  - introduce a second root (which would make `alembic upgrade head` ambiguous),
  - introduce a second head (branching) without a merge,
  - or detach the `000_baseline` invoice-domain root that lets a fresh empty
    database build to head.

They read the migration *files* only (via Alembic's ScriptDirectory) — no
database connection required, so they run in the standard mock-based suite.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _script_directory() -> ScriptDirectory:
    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    return ScriptDirectory.from_config(cfg)


class TestMigrationChain:
    """The chain must stay a single linear path: base -> 000_baseline -> ... -> head."""

    def test_single_head(self):
        """Exactly one head — otherwise `alembic upgrade head` is ambiguous."""
        assert len(_script_directory().get_heads()) == 1

    def test_single_base(self):
        """Exactly one root — two roots cannot both build a fresh DB in order."""
        assert len(_script_directory().get_bases()) == 1

    def test_baseline_is_the_root(self):
        """The invoice-domain baseline is the root of the whole chain."""
        assert list(_script_directory().get_bases()) == ['000_baseline']

    def test_001_chains_off_baseline(self):
        """Migration 001 (users/employees) must follow the baseline, not be a root."""
        rev = _script_directory().get_revision('001')
        assert rev.down_revision == '000_baseline'

    def test_chain_is_walkable_base_to_head(self):
        """Every revision links to a known parent (no dangling down_revision)."""
        script = _script_directory()
        head = script.get_heads()[0]
        # iterate_revisions walks head -> base; it raises if a link is broken.
        revs = list(script.iterate_revisions(head, 'base'))
        # Sanity: the baseline must appear in the walked path.
        assert any(r.revision == '000_baseline' for r in revs)
