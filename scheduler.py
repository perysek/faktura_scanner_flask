"""
Background scheduler for periodic SMS auto-send.

Improvement area #3: the scheduler is guarded by a PostgreSQL *session-level
advisory lock* so that exactly ONE process runs the SMS jobs, regardless of how
many worker processes exist. Without it, N workers would each start a scheduler
and every client would receive N identical reminders. The lock is held by a
dedicated long-lived connection for the life of the process; if the process
crashes, PostgreSQL releases the lock automatically and another process can take
over. This makes the single-runner guarantee structural rather than a
consequence of the (separately enforced) workers=1 invariant.
"""
import logging

import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.database import get_database_url

_scheduler = None

# Dedicated connection holding the advisory lock (kept alive => lock held).
_lock_conn = None

# Arbitrary, app-unique 32-bit key identifying the SMS-scheduler advisory lock.
_SCHEDULER_LOCK_KEY = 728193


def _acquire_scheduler_lock() -> bool:
    """Try to grab the process-wide advisory lock for the SMS scheduler.

    Returns True if this process now owns the scheduler. On success the lock is
    held by a dedicated connection stored in ``_lock_conn`` for the process
    lifetime. On any error we fail OPEN (return True): at workers=1 (the enforced
    norm) there is no second process to collide with, and missing SMS reminders
    is worse than the theoretical double-send that can't happen single-process.
    """
    global _lock_conn
    try:
        conn = psycopg2.connect(get_database_url(), connect_timeout=5)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT pg_try_advisory_lock(%s)", (_SCHEDULER_LOCK_KEY,))
        got = bool(cur.fetchone()[0])
        cur.close()
        if got:
            _lock_conn = conn  # keep alive -> keeps the lock held
            return True
        conn.close()  # another process owns it
        return False
    except Exception:
        logging.warning(
            "Could not acquire SMS scheduler advisory lock; starting scheduler "
            "unguarded (safe at workers=1).", exc_info=True)
        return True


def _run_auto_reminders(app):
    with app.app_context():
        from repositories.sms.sms_repository import SmsSettingsRepository
        settings = SmsSettingsRepository().get_settings() or {}
        if not settings.get('is_active'):
            return

        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        from services.sms_service import SmsService
        svc = SmsService()

        # Existing: time-based pre-appointment reminders
        result = svc.send_due_reminders(base_url)
        if result['sent'] > 0 or result['failed'] > 0:
            logging.info("Auto SMS reminders: sent=%s failed=%s skipped=%s",
                         result['sent'], result['failed'], result['skipped'])

        # New: event-triggered SMS (post_visit_message, etc.)
        event_result = svc.send_due_event_sms(base_url)
        if event_result['sent'] > 0 or event_result['failed'] > 0:
            logging.info("SMS events: sent=%s failed=%s skipped=%s",
                         event_result['sent'], event_result['failed'],
                         event_result['skipped'])


def start_scheduler(app):
    global _scheduler

    # Only the process that wins the advisory lock runs the scheduler.
    if not _acquire_scheduler_lock():
        logging.info("SMS scheduler not started: another process holds the "
                     "advisory lock (this is expected with >1 worker).")
        return

    _scheduler = BackgroundScheduler(timezone='Europe/Warsaw')
    _scheduler.add_job(
        func=_run_auto_reminders,
        args=[app],
        trigger=IntervalTrigger(minutes=15),
        id='sms_auto_send',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logging.info("SMS auto-send scheduler started (interval=15min, advisory-locked)")


def stop_scheduler():
    global _scheduler, _lock_conn
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    # Release the advisory lock by closing its dedicated connection.
    if _lock_conn is not None:
        try:
            _lock_conn.close()
        except Exception:
            pass
        _lock_conn = None
