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
    scheduler._auto_cancel_lock_conn = None
    yield
    scheduler._scheduler = None
    scheduler._lock_conn = None
    scheduler._auto_cancel_lock_conn = None


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
    def test_skips_when_neither_lock_is_acquired(self):
        with patch('scheduler._acquire_scheduler_lock', return_value=False), \
             patch('scheduler._acquire_auto_cancel_lock', return_value=False), \
             patch('scheduler.BackgroundScheduler') as bg:
            scheduler.start_scheduler(app=MagicMock())
            bg.assert_not_called()
        assert scheduler._scheduler is None

    def test_starts_both_jobs_when_both_locks_acquired(self):
        with patch('scheduler._acquire_scheduler_lock', return_value=True), \
             patch('scheduler._acquire_auto_cancel_lock', return_value=True), \
             patch('scheduler.BackgroundScheduler') as bg:
            scheduler.start_scheduler(app=MagicMock())
            ids = [c.kwargs['id'] for c in bg.return_value.add_job.call_args_list]
            assert ids == ['sms_auto_send', 'absence_auto_cancel']
            bg.return_value.start.assert_called_once()

    def test_auto_cancel_runs_even_when_another_app_owns_the_sms_lock(self):
        # Production: the legacy :8083 app (same DB, no auto-cancel code) holds the SMS lock.
        with patch('scheduler._acquire_scheduler_lock', return_value=False), \
             patch('scheduler._acquire_auto_cancel_lock', return_value=True), \
             patch('scheduler.BackgroundScheduler') as bg:
            scheduler.start_scheduler(app=MagicMock())
            ids = [c.kwargs['id'] for c in bg.return_value.add_job.call_args_list]
            assert ids == ['absence_auto_cancel']


class TestStopScheduler:
    def test_closes_lock_connection(self):
        conn = MagicMock()
        scheduler._lock_conn = conn
        scheduler._scheduler = None
        scheduler.stop_scheduler()
        conn.close.assert_called_once()
        assert scheduler._lock_conn is None


class TestAbsenceAutoCancelTick:
    """Auto-cancel of visits parked by "Zatwierdź mimo to" is its own job with its own lock —
    not part of the SMS tick, which the legacy app may be running instead of this one."""

    def _app(self):
        app = MagicMock()
        app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        app.app_context.return_value.__exit__ = MagicMock(return_value=False)
        return app

    def test_job_processes_due_rows(self):
        deferral = MagicMock()
        deferral.process_due.return_value = {'cancelled': 1, 'resolved': 0, 'failed': 0}
        with patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService', return_value=deferral):
            scheduler._run_absence_auto_cancel_job(self._app())
        deferral.process_due.assert_called_once()

    def test_job_swallows_errors(self):
        with patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService', side_effect=Exception('boom')):
            scheduler._run_absence_auto_cancel_job(self._app())   # must not raise into APScheduler

    def test_sms_tick_does_not_auto_cancel(self):
        settings_repo = MagicMock()
        settings_repo.get_settings.return_value = {'is_active': False}
        with patch('services.absence_conflict_deferral_service.AbsenceConflictDeferralService') as deferral, \
             patch('repositories.sms.sms_repository.SmsSettingsRepository', return_value=settings_repo):
            scheduler._run_auto_reminders(self._app())
        deferral.assert_not_called()


class TestAutoCancelLock:
    def test_uses_its_own_key_not_the_sms_one(self):
        assert scheduler._AUTO_CANCEL_LOCK_KEY != scheduler._SCHEDULER_LOCK_KEY

    def test_fails_closed_on_connection_error(self):
        with patch('scheduler.psycopg2.connect', side_effect=Exception("db down")):
            assert scheduler._acquire_auto_cancel_lock() is False

    def test_holds_conn_when_granted(self):
        connect, conn = _mock_connect(True)
        with patch('scheduler.get_database_url', return_value='postgresql://x/y'), \
             patch('scheduler.psycopg2.connect', connect):
            assert scheduler._acquire_auto_cancel_lock() is True
        assert scheduler._auto_cancel_lock_conn is conn
        scheduler._auto_cancel_lock_conn = None
