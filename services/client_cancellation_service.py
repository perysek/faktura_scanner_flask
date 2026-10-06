"""
Client-initiated cancellation through the public SMS links.

Two pages end a visit on the client's say-so — `/cancel/<token>` and the
"Odwołuję wizytę" button on `/confirm/<token>`. Before this module the second one
only wrote `confirmation_status='declined'`: the slot stayed blocked, reminders kept
going out and nobody on the desk heard about it (SMS review P0-3, decision D1).
Both now go through `cancel_by_client`, so they cannot disagree again.

Decision D3: a client may cancel online until CLIENT_CANCEL_CUTOFF_HOURS (12) before
the start; later they are asked to phone the salon.
"""
import logging
from datetime import datetime, time as _time

from flask import current_app

from config.database import managed_transaction
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.status_change_event_repository import StatusChangeEventRepository
from repositories.audit_repository import AuditRepository
from repositories.sms.sms_event_repository import SmsEventRepository
from services.appointment_service import AppointmentBusinessService
from utils.timezone import now_local

CANCELABLE_STATUSES = frozenset({'scheduled', 'confirmed', 'pending'})
DEFAULT_CUTOFF_HOURS = 12

CANCELLED = 'cancelled'
ALREADY_CANCELLED = 'already_cancelled'
NOT_CANCELABLE = 'not_cancelable'
TOO_LATE = 'too_late'

# Who the desk sees as the actor (status_change_events.triggered_by + audit user_name).
EVENT_SOURCE = 'client_sms'
AUDIT_ACTOR = 'Klient (SMS)'


def cutoff_hours() -> int:
    return int(current_app.config.get('CLIENT_CANCEL_CUTOFF_HOURS', DEFAULT_CUTOFF_HOURS))


def _start_datetime(appt) -> datetime:
    start = appt['start_time']
    if not hasattr(start, 'hour'):
        h, m = str(start)[:5].split(':')
        start = _time(int(h), int(m))
    return datetime.combine(appt['appointment_date'], start)


def is_inside_cutoff(appt) -> bool:
    """True when too little time is left (or the visit already started) to cancel online."""
    hours_left = (_start_datetime(appt) - now_local()).total_seconds() / 3600
    return hours_left < cutoff_hours()


def classify(appt) -> str:
    """What may a client do with this visit right now? CANCELLED here means "yes, may cancel"."""
    status = appt.get('status')
    if status == 'cancelled':
        return ALREADY_CANCELLED
    if status not in CANCELABLE_STATUSES:
        return NOT_CANCELABLE
    if is_inside_cutoff(appt):
        return TOO_LATE
    return CANCELLED


def cancel_by_client(appt, *, reason: str, declined: bool = False) -> str:
    """Cancel `appt` on the client's behalf. Returns one of the module outcomes.

    Atomic part (one transaction): status → cancelled (+reason), the client's
    cancelled-counter via the central side-effect hook, queued SMS events cancelled
    (otherwise the employee would still get "Za 20 min wizyta" for a dead visit).
    `declined=True` re-stamps confirmation_status='declined' afterwards, because
    update_status(…'cancelled') blanks it and the SMS stats count declines.
    After commit (best-effort, never undoes the cancellation): a status event so the
    desk's browser toasts it, and an audit row.
    """
    outcome = classify(appt)
    if outcome != CANCELLED:
        return outcome

    appt_id = appt['id']
    old_status = appt['status']
    repo = AppointmentRepository()
    with managed_transaction():
        repo.update_status(appt_id, 'cancelled', cancellation_reason=reason)
        AppointmentBusinessService().apply_status_change_side_effects(appt_id, old_status, 'cancelled')
        SmsEventRepository().cancel_pending_for_appointment(appt_id)
        if declined:
            repo.update_confirmation_status(appt_id, 'declined')

    label = f"{appt.get('appointment_date')} {str(appt.get('start_time', ''))[:5]}"
    try:
        StatusChangeEventRepository().create(appt_id, old_status, 'cancelled', EVENT_SOURCE)
    except Exception:
        logging.exception('status event for client cancel failed appt=%s', appt_id)
    try:
        AuditRepository().log_event(
            entity_type='appointment', action='STATUS_CHANGED', entity_id=appt_id,
            entity_label=label, field_name='status', old_value=old_status, new_value='cancelled',
            user_id=None, user_name=AUDIT_ACTOR,
        )
    except Exception:
        logging.exception('audit for client cancel failed appt=%s', appt_id)
    return CANCELLED
