"""
Tests for the advisory-locked SMS scheduler (improvement area #3).

Contract: exactly one process runs the scheduler. The winner of the Postgres
advisory lock starts APScheduler; losers skip it. On lock-acquisition error we
fail OPEN (safe at the enforced workers=1).
"""
from unittest.mock import MagicMock, patch

import pytest

import scheduler


@pytest.fixture(autouse=True)
def _reset_scheduler_globals():
    """Isolate module-level state between tests."""
    scheduler._scheduler = None
    scheduler._lock_conn = None
    yield
    scheduler._scheduler = None
    scheduler._lock_conn = None


def _mock_connect(lock_granted):
    """Return a fake psycopg2.connect whose advisory-lock query yields a bool."""
    cur = MagicMock()
    cur.fetchone.return_value = [lock_granted]
    conn = MagicMock()
    conn.cursor.return_value = cur
    return MagicMock(return_value=conn), conn


class TestAcquireSchedulerLock:
    def test_returns_true_and_holds_conn_when_granted(self):
        connect, conn = _mock_connect(True)
        with patch('scheduler.get_database_url', return_value='postgresql://x/y'), \
             patch('scheduler.psycopg2.connect', connect):
            assert scheduler._acquire_scheduler_lock() is True
        assert scheduler._lock_conn is conn          # connection kept alive
        conn.close.assert_not_called()               # lock must stay held

    def test_returns_false_and_closes_conn_when_denied(self):
        connect, conn = _mock_connect(False)
        with patch('scheduler.get_database_url', return_value='postgresql://x/y'), \
             patch('scheduler.psycopg2.connect', connect):
            assert scheduler._acquire_scheduler_lock() is False
        assert scheduler._lock_conn is None
        conn.close.assert_called_once()              # released — not our lock

    def test_fails_open_on_connection_error(self):
        with patch('scheduler.psycopg2.connect', side_effect=Exception("db down")):
            assert scheduler._acquire_scheduler_lock() is True


class TestStartScheduler:
    def test_skips_when_lock_not_acquired(self):
        with patch('scheduler._acquire_scheduler_lock', return_value=False), \
             patch('scheduler.BackgroundScheduler') as bg:
            scheduler.start_scheduler(app=MagicMock())
            bg.assert_not_called()
        assert scheduler._scheduler is None

    def test_starts_when_lock_acquired(self):
        with patch('scheduler._acquire_scheduler_lock', return_value=True), \
             patch('scheduler.BackgroundScheduler') as bg:
            scheduler.start_scheduler(app=MagicMock())
            bg.assert_called_once()
            bg.return_value.add_job.assert_called_once()
            bg.return_value.start.assert_called_once()


class TestStopScheduler:
    def test_closes_lock_connection(self):
        conn = MagicMock()
        scheduler._lock_conn = conn
        scheduler._scheduler = None
        scheduler.stop_scheduler()
        conn.close.assert_called_once()
        assert scheduler._lock_conn is None
