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
