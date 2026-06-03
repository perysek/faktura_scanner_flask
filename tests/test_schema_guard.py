"""
Tests for config.database.assert_schema_current — the schema dual-track guard
(improvement area #1).

Contract: a database that is under Alembic control but BEHIND head must fail
boot loudly; a fresh/legacy DB with no alembic_version table must NOT be bricked.
"""
import os
from unittest.mock import Mock, patch

import pytest

from config.database import assert_schema_current


def _pool_returning(version_num):
    """Mock pool whose `SELECT version_num FROM alembic_version` yields a row.

    - str        -> a RealDict-style row {'version_num': str}
    - None       -> empty table (fetchone returns None)
    - Exception  -> the query itself raises (table does not exist)
    """
    cur = Mock()
    if isinstance(version_num, Exception):
        cur.execute.side_effect = version_num
    else:
        cur.fetchone.return_value = (
            {'version_num': version_num} if version_num is not None else None
        )
    conn = Mock()
    conn.cursor.return_value = cur
    pool = Mock()
    pool.getconn.return_value = conn
    return pool


def _patch_head(head):
    script_dir = Mock()
    script_dir.get_current_head.return_value = head
    return patch('alembic.script.ScriptDirectory.from_config', return_value=script_dir)


class TestAssertSchemaCurrent:
    """The boot-time migration-state guard."""

    def test_passes_when_at_head(self):
        """Migrated DB at head -> no exception (the production case)."""
        with _patch_head('rev2'), \
             patch('config.database.get_pool', return_value=_pool_returning('rev2')):
            assert_schema_current()  # must not raise

    def test_raises_when_behind_head(self):
        """Migrated DB behind head -> RuntimeError telling you to upgrade."""
        with _patch_head('rev2'), \
             patch('config.database.get_pool', return_value=_pool_returning('rev1')):
            with pytest.raises(RuntimeError, match="alembic upgrade head"):
                assert_schema_current()

    def test_skips_when_no_alembic_version_table(self):
        """No alembic_version table (schema.sql baseline) -> warn, do not brick."""
        with _patch_head('rev2'), \
             patch('config.database.get_pool',
                   return_value=_pool_returning(Exception("no such table"))):
            assert_schema_current()  # must not raise

    def test_skips_when_table_empty(self):
        """alembic_version present but empty -> treated as un-stamped, no raise."""
        with _patch_head('rev2'), \
             patch('config.database.get_pool', return_value=_pool_returning(None)):
            assert_schema_current()  # must not raise

    def test_skips_when_pool_unavailable(self):
        """Pool not initialized -> guard skips instead of bricking boot."""
        with _patch_head('rev2'), \
             patch('config.database.get_pool', side_effect=RuntimeError('no pool')):
            assert_schema_current()  # must not raise

    def test_env_override_bypasses_entirely(self):
        """SKIP_SCHEMA_CHECK=true short-circuits before touching alembic/pool."""
        with patch.dict(os.environ, {'SKIP_SCHEMA_CHECK': 'true'}):
            with patch('config.database.get_pool') as mock_pool:
                assert_schema_current()
                mock_pool.assert_not_called()
