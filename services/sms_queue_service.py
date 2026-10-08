"""What the SMS scheduler is going to send, and the exact tick that will carry each message.

A READ-ONLY mirror of the scheduler's own rules (scheduler.py, SmsService.send_due_reminders /
send_due_event_sms). There is deliberately no second source of truth: a "N hours before the visit"
text is never queued anywhere — every 15 minutes the scheduler asks which visits start within
±15 minutes of now + N hours — so this module lists the same visits through the same gates, only
looking ahead instead of at the current tick. Nothing here sends, reserves or writes anything.

It also mirrors what the SENDER does once a row is due, because the scheduler's query only finds
candidates: SmsService.send() refuses a phone it cannot parse, a disabled type, an "only confirmed"
type on an unconfirmed visit — and then nothing goes out (a "N hours before" text is skipped silently,
a queued event is marked failed). Deleted visits never get this far: neither the scheduler's queries nor
this module's see them (delete cancels the visit's queued events, and PENDING_EVENT_FILTER is the net). Such rows are still listed, so staff can fix the
cause, but flagged `deliverable: False` with a reason; they never carry a promise. (Checked against the
real sender, tick by tick, on a scratch database — see the ISA's parity runs.)

"Will be sent at" is the TICK, not the nominal due moment. A before-visit message goes out on the
first tick that falls inside its 30-minute window, and ticks run on a fixed 15-minute grid anchored
at the scheduler's start, so the time shown is `next_run + k × 15 min`. When the serving process is
not the one running the scheduler there is no anchor: the times are then rounded up to the next
quarter hour and flagged `estimated`.
"""
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.sms.sms_event_repository import SmsEventRepository
from repositories.sms.sms_repository import (
    SmsMessageTypeRepository, SmsReminderRepository, SmsSettingsRepository,
)
from scheduler import TICK_MINUTES
from utils.phone import normalize_phone
from utils.timezone import now_local, to_local_any

TICK = timedelta(minutes=TICK_MINUTES)
# ±15 min around "start - N h" — AppointmentRepository.get_appointments_due_for_type.
WINDOW = timedelta(minutes=15)

EMPLOYEE_REMINDER = 'employee_visit_reminder'
EMPLOYEE_REMINDER_NAME = 'Przypomnienie dla pracownika'

# What the page tells staff about a row the scheduler will not (or only oddly) deliver.
NOTE_NO_PHONE = 'Brak numeru telefonu — SMS nie zostanie wysłany'
NOTE_BAD_PHONE = 'Nieprawidłowy numer telefonu — SMS nie zostanie wysłany'
NOTE_TYPE_OFF = 'Ten typ SMS jest wyłączony w ustawieniach — SMS nie zostanie wysłany'
NOTE_ALREADY_SENT = 'Ten SMS został już wysłany do tej wizyty — zostanie pominięty'
NOTE_NEEDS_CONFIRMED = 'Wymaga statusu „Potwierdzona” — SMS nie zostanie wysłany'
REASON_CLIENT_NO_PHONE = 'Klient nie ma numeru telefonu'
REASON_CLIENT_BAD_PHONE = 'Nieprawidłowy numer telefonu klienta'


# What the Oczekujące table prints under a number the sender refuses (see phone_for_display).
PHONE_PROBLEM_KIND = {NOTE_NO_PHONE: 'missing', NOTE_BAD_PHONE: 'invalid'}


def phone_for_display(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """(number to show, problem note or None).

    The sender normalises with utils.phone.normalize_phone and REFUSES what it cannot parse
    (SmsService._normalize_phone -> SmsError). For a "N hours before" text send_due_reminders then
    counts the visit as skipped and writes nothing, so a visit with such a number stays "due" on every
    tick and is never texted; for a queued event the event is marked failed. Either way nothing goes
    out, so the page must not promise a time: show what Twilio would receive, or the stored text and
    say it will not be sent.
    """
    text = str(raw).strip() if raw is not None else ''
    if not text:
        return None, NOTE_NO_PHONE
    normalized = normalize_phone(text)
    if normalized:
        return normalized, None
    return text, NOTE_BAD_PHONE


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
                now: Optional[datetime] = None, next_run: Optional[datetime] = None,
                before: Optional[datetime] = None, newest_first: bool = False) -> Dict[str, Any]:
        """Every message the scheduler will still send, soonest first (or newest first).

        `now` / `next_run` are naive Warsaw wall-clock (default: the clock / None = no anchor).
        `before` (naive Warsaw, exclusive) keeps only rows whose tick falls earlier: the month picker of
        Historia SMS asks for "everything up to the end of that month". `total`, `undeliverable` and the
        paging all describe the filtered list, so the tab's count pill matches what the table lists.
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
        if before is not None:
            cutoff = before.isoformat(timespec='seconds')       # same fixed-width ISO format: strings compare as times
            rows = [r for r in rows if r['will_be_sent_at'] < cutoff]
        rows.sort(key=lambda r: (r['will_be_sent_at'], r['appointment_id'] or 0, r['type_key']), reverse=newest_first)

        return {
            'rows': rows[offset:offset + limit],
            'total': len(rows),
            # Rows listed above that the scheduler will not actually deliver (see phone_for_display).
            'undeliverable': sum(1 for r in rows if not r['deliverable']),
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
            shown, problem = phone_for_display(r['phone'])
            out.append({
                'key': f"w{r['appointment_id']}:{msg_type['type_key']}",
                'kind': 'before_visit',
                'type_key': msg_type['type_key'],
                'type_name': msg_type['name'],
                'will_be_sent_at': tick.isoformat(timespec='seconds'),
                'estimated': next_run is None,
                'deliverable': problem is None,
                'recipient_kind': 'client',
                'recipient_name': r['client_name'],
                'phone_number': shown,
                'phone_problem': PHONE_PROBLEM_KIND.get(problem),
                'appointment_id': r['appointment_id'],
                'appointment_date': str(r['appointment_date']),
                'start_time': str(r['start_time']),
                'note': problem,
            })
        return out

    def _event_rows(self, appointment_id: Optional[int], now: datetime,
                    next_run: Optional[datetime]) -> List[Dict[str, Any]]:
        out = []
        for e in self._event_repo.get_scheduled_for_queue(appointment_id):
            employee = e['event_type'] == EMPLOYEE_REMINDER
            shown, problem = phone_for_display(e['employee_phone'] if employee else e['client_phone'])
            if employee:
                # _send_employee_reminder_direct looks at the employee's phone and nothing else: not at the
                # visit's status and not at the message-type switch. (A DELETED visit's events never get here:
                # PENDING_EVENT_FILTER leaves them out of both the scheduler's query and this one.)
                deliverable, note = problem is None, problem
            else:
                # Every other event goes through SmsService.send(); this is its refusal order. A refusal makes
                # the scheduler mark the event failed (or skipped, for "already texted") and text nobody.
                refusal = self._client_event_refusal(e, problem)
                deliverable, note = refusal is None, refusal
            tick = self._tick_for(max(to_local_any(e['scheduled_at']), now), next_run)
            out.append({
                'key': f"e{e['id']}",
                'kind': 'queued_event',
                'type_key': e['event_type'],
                'type_name': e.get('type_name') or (EMPLOYEE_REMINDER_NAME if employee else e['event_type']),
                'will_be_sent_at': tick.isoformat(timespec='seconds'),
                'estimated': next_run is None,
                'deliverable': deliverable,
                'recipient_kind': 'employee' if employee else 'client',
                'recipient_name': (e['employee_name'] if employee else e['client_name']) or '',
                'phone_number': shown,
                'phone_problem': PHONE_PROBLEM_KIND.get(problem),
                'appointment_id': e['appointment_id'],
                'appointment_date': str(e['appointment_date']),
                'start_time': str(e['start_time']),
                'note': note,
            })
        return out

    @staticmethod
    def _client_event_refusal(e: Dict[str, Any], phone_problem: Optional[str]) -> Optional[str]:
        """Why SmsService.send() would refuse this queued client-facing event (None = it goes out).
        Same order as send(): type unknown/disabled, already texted, phone, only-confirmed. (send() also refuses a
        deleted visit; those events are excluded upstream, see PENDING_EVENT_FILTER.)"""
        if not e.get('type_enabled'):                       # no sms_message_types row at all, or switched off
            return NOTE_TYPE_OFF
        if e.get('already_sent'):
            return NOTE_ALREADY_SENT
        if phone_problem:
            return phone_problem
        if e.get('type_only_confirmed') and e.get('visit_status') != 'confirmed':
            return NOTE_NEEDS_CONFIRMED
        return None

    # ------------------------------------------------------------ manual sending

    def manual_send_options(self, appointment_id: int) -> Dict[str, Any]:
        """What the visit page's "Wyślij SMS" dropdown may offer for this visit, and why not.

        Mirrors SmsService.send()'s refusals so the UI explains a greyed-out entry instead of
        letting the click fail: SMS off, no phone, a phone the sender cannot parse, or an "only
        confirmed" type on an unconfirmed visit. Disabled types are not offered at all (send()
        refuses them too).
        """
        from repositories.clients.client_repository import ClientRepository
        settings = self._settings_repo.get_settings() or {}
        sms_active = bool(settings.get('is_active'))
        appt = self._appt_repo.get_by_id(appointment_id)
        if not appt:
            return {'sms_active': sms_active, 'types': []}
        client = ClientRepository().get_by_id(appt['client_id'])
        _, phone_problem = phone_for_display(client['phone'] if client else None)

        types = []
        for t in self._type_repo.get_enabled():
            reason = None
            if not sms_active:
                reason = 'Wysyłanie SMS jest wyłączone w ustawieniach'
            elif phone_problem:
                reason = REASON_CLIENT_NO_PHONE if phone_problem == NOTE_NO_PHONE else REASON_CLIENT_BAD_PHONE
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
