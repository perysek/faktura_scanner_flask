"""
Background scheduler for periodic SMS auto-send.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler = None


def _run_auto_reminders(app):
    with app.app_context():
        from repositories.sms.sms_repository import SmsSettingsRepository
        settings = SmsSettingsRepository().get_settings() or {}
        if not settings.get('is_active'):
            return

        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        from services.sms_service import SmsService
        result = SmsService().send_due_reminders(base_url)
        if result['sent'] > 0 or result['failed'] > 0:
            logging.info("Auto SMS: sent=%s failed=%s skipped=%s",
                         result['sent'], result['failed'], result['skipped'])


def start_scheduler(app):
    global _scheduler
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
    logging.info("SMS auto-send scheduler started (interval=15min)")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
