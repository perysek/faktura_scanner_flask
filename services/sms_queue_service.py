"""What the SMS scheduler is going to send, and the exact tick that will carry each message.

A READ-ONLY mirror of the scheduler's own rules (scheduler.py, SmsService.send_due_reminders /
send_due_event_sms). There is deliberately no second source of truth: a "N hours before the visit"
text is never queued anywhere — every 15 minutes the scheduler asks which visits start within
±15 minutes of now + N hours — so this module lists the same visits through the same gates, only
looking ahead instead of at the current tick. Nothing here sends, reserves or writes anything.

"Will be sent at" is the TICK, not the nominal due moment. A before-visit message goes out on the
first tick that falls inside its 30-minute window, and ticks run on a fixed 15-minute grid anchored
at the scheduler's start, so the time shown is `next_run + k × 15 min`. When the serving process is
not the one running the scheduler there is no anchor: the times are then rounded up to the next
quarter hour and flagged `estimated`.
"""
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.sms.sms_event_repository import SmsEventRepository
from repositories.sms.sms_repository import (
    SmsMessageTypeRepository, SmsReminderRepository, SmsSettingsRepository,
)
from scheduler import TICK_MINUTES
from utils.timezone import now_local, to_local_any

TICK = timedelta(minutes=TICK_MINUTES)
# ±15 min around "start - N h" — AppointmentRepository.get_appointments_due_for_type.
WINDOW = timedelta(minutes=15)

EMPLOYEE_REMINDER = 'employee_visit_reminder'
EMPLOYEE_REMINDER_NAME = 'Przypomnienie dla pracownika'


def first_tick_at_or_after(moment: datetime, next_run: datetime, tick: timedelta = TICK) -> datetime:
    """The first scheduler tick >= `moment`, given the NEXT tick and a fixed cadence."""
    if moment <= next_run:
        return next_run
    steps, remainder = divmod(moment - next_run, tick)
    return next_run + (steps + (1 if remainder else 0)) * tick


def estimate_tick(moment: datetime, tick: timedelta = TICK) -> datetime:
    """No scheduler anchor in this process: round up to the next quarter hour (best guess)."""
    quarter = tick.total_seconds()
    seconds = moment.minute * 60 + moment.second + moment.microsecond / 1e6
    rounded = math.ceil(seconds / quarter) * quarter
    return moment.replace(minute=0, second=0, microsecond=0) + timedelta(seconds=rounded)


def format_sent_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """One `sms_reminders` row as the API/UI shows it (Warsaw wall-clock; no phone, no body)."""
    sent_at = row.get('sent_at')
    return {
        'id': row['id'],
        'sent_at': to_local_any(sent_at).isoformat(timespec='seconds') if sent_at else None,
        'type_key': row.get('message_type_key'),
        'type_name': row.get('type_name') or row.get('message_type_key'),
        'status': row.get('status'),
        'sent_by': row.get('sender_name') or row.get('created_by_name') or None,
        'automatic': row.get('created_by_user_id') is None,
        'error_message': row.get('error_message'),
    }


class SmsQueueService:
    def __init__(self, settings_repo=None, type_repo=None, appt_repo=None, event_repo=None, reminder_repo=None):
        self._settings_repo = settings_repo or SmsSettingsRepository()
        self._type_repo = type_repo or SmsMessageTypeRepository()
        self._appt_repo = appt_repo or AppointmentRepository()
        self._event_repo = event_repo or SmsEventRepository()
        self._reminder_repo = reminder_repo or SmsReminderRepository()

    # ------------------------------------------------------------------ pending

    def pending(self, *, appointment_id: Optional[int] = None, offset: int = 0, limit: int = 100,
                now: Optional[datetime] = None, next_run: Optional[datetime] = None) -> Dict[str, Any]:
        """Every message the scheduler will still send, soonest first.

        `now` / `next_run` are naive Warsaw wall-clock (default: the clock / None = no anchor).
        With SMS switched off globally the scheduler's job returns immediately, so nothing is queued.
        """
        now = now or now_local()
        settings = self._settings_repo.get_settings() or {}
        active = bool(settings.get('is_active'))

        rows: List[Dict[str, Any]] = []
        if active:
            for msg_type in self._type_repo.get_enabled_before_visit():
                rows.extend(self._before_visit_rows(msg_type, appointment_id, now, next_run))
            rows.extend(self._event_rows(appointment_id, now, next_run))
        rows.sort(key=lambda r: (r['will_be_sent_at'], r['appointment_id'] or 0, r['type_key']))

        return {
            'rows': rows[offset:offset + limit],
            'total': len(rows),
            'sms_active': active,
            'next_tick_at': next_run.isoformat(timespec='seconds') if next_run else None,
            'estimated': next_run is None,
        }

    def _tick_for(self, moment: datetime, next_run: Optional[datetime]) -> datetime:
        return first_tick_at_or_after(moment, next_run) if next_run else estimate_tick(moment)

    def _before_visit_rows(self, msg_type: dict, appointment_id: Optional[int],
                           now: datetime, next_run: Optional[datetime]) -> List[Dict[str, Any]]:
        hours = int(msg_type['send_hours_before'])
        lead = timedelta(hours=hours)
        out = []
        candidates = self._appt_repo.get_sms_queue_candidates(
            hours, msg_type['type_key'],
            only_confirmed=bool(msg_type.get('send_only_if_confirmed')),
            appointment_id=appointment_id)
        for r in candidates:
            visit_at = r['visit_at']
            window_open, window_close = visit_at - lead - WINDOW, visit_at - lead + WINDOW
            tick = self._tick_for(max(window_open, now), next_run)
            if tick > window_close:
                continue      # no tick lands inside the window: the scheduler would miss this one
            out.append({
                'key': f"w{r['appointment_id']}:{msg_type['type_key']}",
                'kind': 'before_visit',
                'type_key': msg_type['type_key'],
                'type_name': msg_type['name'],
                'will_be_sent_at': tick.isoformat(timespec='seconds'),
                'estimated': next_run is None,
                'recipient_kind': 'client',
                'recipient_name': r['client_name'],
                'phone_number': r['phone'],
                'appointment_id': r['appointment_id'],
                'appointment_date': str(r['appointment_date']),
                'start_time': str(r['start_time']),
                'note': None,
            })
        return out

    def _event_rows(self, appointment_id: Optional[int], now: datetime,
                    next_run: Optional[datetime]) -> List[Dict[str, Any]]:
        out = []
        for e in self._event_repo.get_scheduled_for_queue(appointment_id):
            employee = e['event_type'] == EMPLOYEE_REMINDER
            phone = e['employee_phone'] if employee else e['client_phone']
            tick = self._tick_for(max(to_local_any(e['scheduled_at']), now), next_run)
            out.append({
                'key': f"e{e['id']}",
                'kind': 'queued_event',
                'type_key': e['event_type'],
                'type_name': e.get('type_name') or (EMPLOYEE_REMINDER_NAME if employee else e['event_type']),
                'will_be_sent_at': tick.isoformat(timespec='seconds'),
                'estimated': next_run is None,
                'recipient_kind': 'employee' if employee else 'client',
                'recipient_name': (e['employee_name'] if employee else e['client_name']) or '',
                'phone_number': phone,
                'appointment_id': e['appointment_id'],
                'appointment_date': str(e['appointment_date']),
                'start_time': str(e['start_time']),
                'note': None if phone else 'Brak numeru telefonu — wysyłka się nie powiedzie',
            })
        return out

    # ------------------------------------------------------------ manual sending

    def manual_send_options(self, appointment_id: int) -> Dict[str, Any]:
        """What the visit page's "Wyślij SMS" dropdown may offer for this visit, and why not.

        Mirrors SmsService.send()'s refusals so the UI explains a greyed-out entry instead of
        letting the click fail: SMS off, no phone, or an "only confirmed" type on an unconfirmed
        visit. Disabled types are not offered at all (send() refuses them too).
        """
        from repositories.clients.client_repository import ClientRepository
        settings = self._settings_repo.get_settings() or {}
        sms_active = bool(settings.get('is_active'))
        appt = self._appt_repo.get_by_id(appointment_id)
        if not appt:
            return {'sms_active': sms_active, 'types': []}
        client = ClientRepository().get_by_id(appt['client_id'])
        has_phone = bool(client and client['phone'])

        types = []
        for t in self._type_repo.get_enabled():
            reason = None
            if not sms_active:
                reason = 'Wysyłanie SMS jest wyłączone w ustawieniach'
            elif not has_phone:
                reason = 'Klient nie ma numeru telefonu'
            elif t.get('send_only_if_confirmed') and appt['status'] != 'confirmed':
                reason = 'Wymaga statusu „Potwierdzona”'
            types.append({
                'type_key': t['type_key'],
                'name': t['name'],
                'available': reason is None,
                'reason': reason,
                'already_sent': self._reminder_repo.exists_active(appointment_id, t['type_key']),
            })
        return {'sms_active': sms_active, 'types': types}
