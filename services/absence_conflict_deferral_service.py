"""
Odroczone rozwiązywanie konfliktów nieobecność/wizyta + kolejka SMS z modala.

Dwie ścieżki z modala rozwiązywania konfliktów (ConflictResolutionModal.tsx):

1. "Wyślij wiadomość" w tabeli "Historia rozwiązań" — zaznaczone wizyty dostają SMS
   dopiero przy zatwierdzeniu wniosku; trafiają do kolejki `sms_events` z
   scheduled_at = teraz, więc wychodzą przy najbliższym 15-minutowym ticku
   schedulera. Typ SMS zależy od rozwiązania: anulowana → `absence_cancellation`,
   zmieniona stylistka/termin → `absence_visit_update`.

2. "Zatwierdź mimo to" — każda wizyta bez rozwiązania trafia do
   `absence_conflict_pending` z valid_for = start wizyty − AUTO_CANCEL_OFFSET_HOURS,
   a równolegle do `sms_events` idzie `absence_cancellation` na ten sam moment.
   Tick schedulera (process_due) najpierw anuluje takie wizyty, o ile wciąż kolidują
   z nieobecnością — dopiero potem send_due_event_sms() wysyła SMS-y. Wizyty
   rozwiązane w międzyczasie (zmiana stylistki/terminu w Wizytach) są pomijane, a ich
   SMS o odwołaniu wycofany.
"""
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, List, Optional

from utils.timezone import WARSAW_TZ

logger = logging.getLogger(__name__)

# TODO(settings): make this offset (and the conflict-SMS send offset) a customizable parameter
# in a future app-settings panel / db table — tracked in TODOS.md.
AUTO_CANCEL_OFFSET_HOURS = 48

AUTO_CANCEL_REASON = 'Automatyczne anulowanie — nierozwiązany konflikt z nieobecnością pracownika'

SMS_TYPE_FOR_RESOLUTION = {
    'cancelled': 'absence_cancellation',
    'reassigned': 'absence_visit_update',
    'rescheduled': 'absence_visit_update',
}


def _as_date(v) -> date:
    return v if isinstance(v, date) else datetime.strptime(str(v)[:10], '%Y-%m-%d').date()


def _as_time(v) -> time:
    if isinstance(v, time):
        return v
    if isinstance(v, timedelta):
        return (datetime.min + v).time()
    s = str(v)
    return datetime.strptime(s[:8] if len(s) >= 8 else s[:5], '%H:%M:%S' if len(s) >= 8 else '%H:%M').time()


def compute_valid_for(appointment_date, start_time) -> datetime:
    """Visit start (naive Warsaw wall-clock, as stored) − offset, returned timezone-AWARE so a
    TIMESTAMPTZ column stores the right instant on a UTC DB session (same trap as
    SmsService.schedule_employee_reminder)."""
    start_local = datetime.combine(_as_date(appointment_date), _as_time(start_time))
    return (start_local - timedelta(hours=AUTO_CANCEL_OFFSET_HOURS)).replace(tzinfo=WARSAW_TZ)


class AbsenceConflictDeferralService:

    def __init__(self, pending_repo=None, event_repo=None, absence_repo=None,
                 resolution_repo=None, appointment_service=None):
        if pending_repo is None:
            from repositories.absences.absence_conflict_pending_repository import (
                AbsenceConflictPendingRepository,
            )
            pending_repo = AbsenceConflictPendingRepository()
        if event_repo is None:
            from repositories.sms.sms_event_repository import SmsEventRepository
            event_repo = SmsEventRepository()
        if absence_repo is None:
            from repositories.absences.absence_repository import AbsenceRepository
            absence_repo = AbsenceRepository()
        if resolution_repo is None:
            from repositories.absences.absence_conflict_resolution_repository import (
                AbsenceConflictResolutionRepository,
            )
            resolution_repo = AbsenceConflictResolutionRepository()
        self.pending_repo = pending_repo
        self.event_repo = event_repo
        self.absence_repo = absence_repo
        self.resolution_repo = resolution_repo
        self._appointment_service = appointment_service

    @property
    def appointment_service(self):
        if self._appointment_service is None:
            from services.appointment_service import AppointmentBusinessService
            self._appointment_service = AppointmentBusinessService()
        return self._appointment_service

    # ── "Wyślij wiadomość" ──────────────────────────────────────────────────

    def queue_resolution_sms(self, absence_id: int, appointment_ids: Iterable[int]) -> List[dict]:
        """Queue one client SMS per marked visit, fired at the next scheduler tick.

        Only visits that actually have a resolution on THIS absence are accepted (the ids
        come from the browser); the latest resolution decides the type. Returns
        [{'appointment_id', 'event_type', 'event_id'}] for what was queued."""
        wanted = {int(a) for a in appointment_ids or []}
        if not wanted:
            return []
        latest = {}
        for r in self.resolution_repo.list_for_absence(absence_id):   # newest first
            latest.setdefault(r['appointment_id'], r['resolution_type'])

        now = datetime.now(timezone.utc)
        queued = []
        for appt_id in sorted(wanted):
            event_type = SMS_TYPE_FOR_RESOLUTION.get(latest.get(appt_id))
            if not event_type:
                logger.warning('queue_resolution_sms: appt %s has no resolution on absence %s — skipped',
                               appt_id, absence_id)
                continue
            event_id = self.event_repo.create(appt_id, event_type, now)
            queued.append({'appointment_id': appt_id, 'event_type': event_type, 'event_id': event_id})
        return queued

    # ── "Zatwierdź mimo to" ─────────────────────────────────────────────────

    def defer_unresolved(self, absence_id: int, employee_id: Optional[int],
                         conflicts: Iterable[dict], created_by_user_id: int) -> List[dict]:
        """Store every still-unresolved conflict with its auto-cancel moment and queue the
        matching cancellation SMS for that same moment. `conflicts` are
        format_appt_conflict() dicts. Returns [{'appointment_id', 'valid_for'}]."""
        deferred = []
        seen = set()
        for c in conflicts:
            appt_id = c['appointment_id']
            if appt_id in seen:      # the overlap query can repeat a multi-service visit
                continue
            seen.add(appt_id)
            valid_for = compute_valid_for(c['date'], c['start_time'])
            event_id = self.event_repo.create(appt_id, 'absence_cancellation', valid_for)
            row_id = self.pending_repo.create(
                absence_id=absence_id, appointment_id=appt_id, employee_id=employee_id,
                appointment_date=_as_date(c['date']), start_time=_as_time(c['start_time']),
                end_time=_as_time(c['end_time']) if c.get('end_time') else None,
                valid_for=valid_for, created_by_user_id=created_by_user_id,
                sms_event_id=event_id,
            )
            if row_id is None:
                # Already deferred earlier — drop the duplicate SMS we just queued.
                self.event_repo.mark_skipped(event_id, 'Wizyta już oczekuje na auto-anulowanie')
                continue
            deferred.append({'appointment_id': appt_id, 'valid_for': valid_for.isoformat()})
        return deferred

    # ── scheduler tick ──────────────────────────────────────────────────────

    def _still_conflicting(self, row: dict) -> bool:
        absence = self.absence_repo.get_by_id(row['absence_id'])
        if not absence or absence['status'] != 'approved' or absence.get('is_deleted'):
            return False
        overlapping = self.absence_repo.get_overlapping_appointments(
            absence['employee_id'], absence['date_from'], absence['date_to'],
            absence['time_from'], absence['time_to'],
        )
        return any(o['id'] == row['appointment_id'] for o in overlapping)

    def process_due(self) -> dict:
        """Auto-cancel visits whose `valid_for` has passed and that still collide with the
        approved absence. Must run BEFORE SmsService.send_due_event_sms() in the same tick so
        the queued cancellation SMS goes out after the visit is actually cancelled."""
        cancelled = resolved = failed = 0
        for row in self.pending_repo.get_due():
            try:
                if not self._still_conflicting(row):
                    if row.get('sms_event_id'):
                        self.event_repo.mark_skipped(row['sms_event_id'],
                                                     'Konflikt rozwiązany przed auto-anulowaniem')
                    self.pending_repo.mark(row['id'], 'resolved')
                    resolved += 1
                    continue
                self.appointment_service.cancel_appointment(row['appointment_id'], AUTO_CANCEL_REASON)
                self.resolution_repo.create(
                    absence_id=row['absence_id'], appointment_id=row['appointment_id'],
                    resolution_type='cancelled', cancellation_reason=AUTO_CANCEL_REASON,
                    resolved_by_user_id=row['created_by_user_id'],
                )
                self.pending_repo.mark(row['id'], 'auto_cancelled')
                cancelled += 1
            except Exception as exc:
                logger.exception('absence auto-cancel failed pending_id=%s appt=%s',
                                 row['id'], row['appointment_id'])
                if row.get('sms_event_id'):
                    # Never text "your visit is cancelled" for a visit we failed to cancel.
                    self.event_repo.mark_skipped(row['sms_event_id'], f'Auto-anulowanie nieudane: {exc}')
                self.pending_repo.mark(row['id'], 'failed', str(exc)[:500])
                failed += 1
        return {'cancelled': cancelled, 'resolved': resolved, 'failed': failed}
