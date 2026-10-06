"""
Public booking routes — accessible without authentication.
Clients can browse services, check available slots, and book appointments.
"""
import json
import logging
import re
from datetime import datetime, date, time, timedelta
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, render_template

from exceptions import AppError, ValidationError
from repositories.services.service_repository import ServiceRepository
from repositories.employees.employee_service_repository import EmployeeServiceRepository
from repositories.clients.client_repository import ClientRepository
from repositories.audit_repository import AuditRepository
from services import turnstile_service as turnstile
from services.appointment_service import AppointmentBusinessService, AppointmentError
from services.sms_service import SmsService
from database.models import Client
from utils.client_ip import client_ip
from utils.phone import PHONE_FORMAT_HINT, fold_name, normalize_phone, phone_match_keys
from utils.rate_limit import limiter
from utils.work_schedule import (
    WEEKDAY_KEYS as _WEEKDAY_KEYS,
    DEFAULT_WORK_START as _DEFAULT_WORK_START,
    DEFAULT_WORK_END as _DEFAULT_WORK_END,
    parse_day_hours as _parse_day_hours,
    work_hours_for_day as _work_hours_for_day,
)

logger = logging.getLogger(__name__)

booking_bp = Blueprint('booking', __name__)

# ─── Constants ───────────────────────────────────────────────────────────────
# Schedule parsing (WEEKDAY_KEYS, defaults, parse_day_hours, work_hours_for_day)
# now lives in utils.work_schedule and is imported at the top of this module so
# the public booking flow and the internal appointment service stay in sync.

_DAY_PL = {
    'mon': 'pon', 'tue': 'wt', 'wed': 'śr',
    'thu': 'czw', 'fri': 'pt', 'sat': 'sob', 'sun': 'nd',
}


# ─── Schedule Helpers ─────────────────────────────────────────────────────────

def _schedule_info(work_schedule_json) -> dict:
    """Parse work_schedule JSON string into booking-friendly data.

    Returns:
        available_days  – list of 3-letter day keys the employee works
        hours_display   – human-readable hours string, e.g. "09:00 – 17:00"
    """
    sched: dict = {}
    if work_schedule_json:
        try:
            sched = json.loads(work_schedule_json) if isinstance(work_schedule_json, str) else work_schedule_json
        except (json.JSONDecodeError, TypeError):
            pass

    if not sched:
        # No schedule defined — assume Mon-Fri default hours
        return {
            'available_days': _WEEKDAY_KEYS[:5],
            'hours_display': f"{_DEFAULT_WORK_START.strftime('%H:%M')} – {_DEFAULT_WORK_END.strftime('%H:%M')}",
        }

    available_days = []
    hours_set = set()
    for key in _WEEKDAY_KEYS:
        hours = _parse_day_hours(sched, key)
        if hours:
            available_days.append(key)
            hours_set.add(f"{hours[0].strftime('%H:%M')} – {hours[1].strftime('%H:%M')}")

    if not available_days:
        # Schedule exists but no valid entries — fall back
        return {
            'available_days': _WEEKDAY_KEYS[:5],
            'hours_display': f"{_DEFAULT_WORK_START.strftime('%H:%M')} – {_DEFAULT_WORK_END.strftime('%H:%M')}",
        }

    if len(hours_set) == 1:
        hours_display = hours_set.pop()
    else:
        hours_display = 'Godziny zmienne'

    return {'available_days': available_days, 'hours_display': hours_display}


# ─── Routing Helpers ──────────────────────────────────────────────────────────

def _parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date using local time (no UTC shift)."""
    if not date_str:
        raise ValidationError('Brakująca data')
    try:
        y, m, d = date_str.split('-')
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        raise ValidationError(f'Nieprawidłowy format daty: {date_str}')


def _parse_time(time_str: str):
    """Parse HH:MM time string."""
    if not time_str:
        raise ValidationError('Brakująca godzina')
    try:
        return datetime.strptime(time_str.strip(), '%H:%M').time()
    except ValueError:
        raise ValidationError(f'Nieprawidłowy format godziny: {time_str}')


# ─── Page Route ─────────────────────────────────────────────────────────────

@booking_bp.route('/booking')
def booking_page():
    """Public booking page — no authentication required.

    `turnstile_site_key` is the PUBLIC half of the Cloudflare Turnstile pair; when empty
    the page renders no widget (and the server skips the check — see turnstile_service)."""
    return render_template('booking/index.html',
                           turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''),
                           turnstile_action=BOOKING_ACTION)


# ─── Public API Endpoints ────────────────────────────────────────────────────

@booking_bp.route('/api/public/services', methods=['GET'])
def get_public_services():
    """Return active main services available for online booking."""
    try:
        repo = ServiceRepository()
        rows = repo.get_main_services(active_only=True)
        services = [
            {
                'id': row['id'],
                'name': row['name'],
                'category': row['category'],
                'description': row['description'],
                'price': float(row['price']),
                'duration_minutes': row['duration_minutes'],
                'currency': row['currency'],
            }
            for row in rows
        ]
        return jsonify({'success': True, 'services': services})
    except Exception:
        logger.exception('Error fetching public services')
        return jsonify({'success': False, 'error': 'Nie można wczytać usług'}), 500


@booking_bp.route('/api/public/employees', methods=['GET'])
def get_public_employees():
    """Return employees who can perform a given service.

    Query param: service_id (required)
    Returns effective price and duration for this employee/service pair.
    """
    try:
        service_id = request.args.get('service_id', type=int)
        if not service_id:
            raise ValidationError('Wymagany parametr: service_id')

        emp_svc_repo = EmployeeServiceRepository()
        rows = emp_svc_repo.get_employees_for_service(service_id, active_only=True)

        employees = []
        for row in rows:
            sched = _schedule_info(row['work_schedule'])
            employees.append({
                'id': row['employee_id'],
                'name': f"{row['first_name']} {row['last_name']}",
                'position': row['position'],
                'effective_price': float(row['effective_price']),
                'effective_duration': int(row['effective_duration']),
                'available_days': sched['available_days'],
                'hours_display': sched['hours_display'],
            })
        return jsonify({'success': True, 'employees': employees})
    except AppError:
        raise
    except Exception:
        logger.exception('Error fetching employees for service')
        return jsonify({'success': False, 'error': 'Nie można wczytać pracowników'}), 500


@booking_bp.route('/api/public/available-days', methods=['GET'])
def get_available_days():
    """Return ISO date strings in a given month that have at least one available slot.

    Query params: employee_id, year (YYYY), month (1-12), duration (minutes)
    Skips past dates and off-days from work_schedule.

    Performance: fetches all employee appointments in the month in ONE query,
    then checks conflicts in Python memory — avoids N×M per-slot DB queries.
    """
    import calendar as _cal
    from collections import defaultdict
    try:
        employee_id = request.args.get('employee_id', type=int)
        year        = request.args.get('year',  type=int)
        month       = request.args.get('month', type=int)
        duration    = request.args.get('duration', 60, type=int)

        if not employee_id or not year or not month:
            raise ValidationError('Wymagane: employee_id, year, month')
        if not (1 <= month <= 12):
            raise ValidationError('Nieprawidłowy miesiąc')

        from repositories.employees.employee_repository import EmployeeRepository
        from repositories.appointments.appointment_repository import AppointmentRepository
        emp_row = EmployeeRepository().get_by_id(employee_id)
        work_schedule_json = emp_row['work_schedule'] if emp_row else None

        today = date.today()
        _, days_in_month = _cal.monthrange(year, month)

        # Bulk fetch: ONE query for all appointments in the month
        month_start = date(year, month, 1)
        month_end   = date(year, month, days_in_month)
        appt_rows = AppointmentRepository().get_appointments_in_range(
            employee_id, month_start, month_end
        )

        # Group by ISO date string for O(1) lookup per day
        appts_by_date = defaultdict(list)
        for row in appt_rows:
            d = row['appointment_date']
            key = d.isoformat() if hasattr(d, 'isoformat') else str(d)
            appts_by_date[key].append(row)

        # Merge approved absences — each absence date blocks slots like a booked appointment
        from repositories.absences.absence_repository import AbsenceRepository
        from datetime import timedelta as _td
        absence_rows = AbsenceRepository().list_all(
            status_in=['approved'],
            employee_id=employee_id,
            date_from=month_start,
            date_to=month_end,
        )
        for ab in absence_rows:
            ab_from = ab['date_from'] if hasattr(ab['date_from'], 'isoformat') else date.fromisoformat(str(ab['date_from']))
            ab_to   = ab['date_to']   if hasattr(ab['date_to'],   'isoformat') else date.fromisoformat(str(ab['date_to']))
            cur = ab_from
            while cur <= ab_to:
                if ab['time_from'] is None:
                    # Full-day: use sentinel that will be resolved to work_start/work_end per-day below
                    appts_by_date[cur.isoformat()].append({'_full_day_absence': True})
                else:
                    appts_by_date[cur.isoformat()].append({
                        'start_time': ab['time_from'],
                        'end_time':   ab['time_to'],
                    })
                cur += _td(days=1)

        svc = AppointmentBusinessService()
        available_dates = []

        for day_num in range(1, days_in_month + 1):
            day_date = date(year, month, day_num)
            if day_date < today:
                continue

            day_key = _WEEKDAY_KEYS[day_date.weekday()]
            hours = _work_hours_for_day(work_schedule_json, day_key)
            if hours is None:
                continue  # off day

            work_start, work_end = hours
            raw_booked = appts_by_date.get(day_date.isoformat(), [])
            # Resolve full-day absence sentinels to the actual work window for this day
            day_booked = []
            for b in raw_booked:
                if b.get('_full_day_absence'):
                    day_booked.append({'start_time': work_start, 'end_time': work_end})
                else:
                    day_booked.append(b)
            slots = svc.get_available_slots(
                employee_id, day_date, duration,
                work_start=work_start, work_end=work_end,
                booked=day_booked,
            )
            if any(s['available'] for s in slots):
                available_dates.append(day_date.isoformat())

        return jsonify({'success': True, 'available_dates': available_dates})
    except AppError:
        raise
    except Exception:
        logger.exception('Error fetching available days')
        return jsonify({'success': False, 'error': 'Nie można wczytać kalendarza'}), 500


@booking_bp.route('/api/public/slots', methods=['GET'])
def get_public_slots():
    """Return available time slots for a given employee on a given date.

    Query params: employee_id, date (YYYY-MM-DD), duration (minutes)
    Returns only slots where available=True.
    """
    try:
        employee_id = request.args.get('employee_id', type=int)
        date_str = request.args.get('date')
        duration = request.args.get('duration', 60, type=int)

        if not employee_id or not date_str:
            raise ValidationError('Wymagane parametry: employee_id, date')

        slot_date = _parse_date(date_str)

        # Reject past dates
        if slot_date < date.today():
            return jsonify({'success': True, 'slots': [], 'off_day': False})

        # Look up employee work schedule
        from repositories.employees.employee_repository import EmployeeRepository
        emp_row = EmployeeRepository().get_by_id(employee_id)
        work_schedule_json = emp_row['work_schedule'] if emp_row else None

        day_key = _WEEKDAY_KEYS[slot_date.weekday()]
        hours = _work_hours_for_day(work_schedule_json, day_key)

        if hours is None:
            # Employee is off on this day
            return jsonify({'success': True, 'slots': [], 'off_day': True})

        work_start, work_end = hours

        # Pre-fetch appointments + approved absences for in-memory conflict check
        from repositories.appointments.appointment_repository import AppointmentRepository as _ApptRepo
        from repositories.absences.absence_repository import AbsenceRepository as _AbsRepo
        appt_rows = _ApptRepo().get_appointments_in_range(employee_id, slot_date, slot_date)
        absence_rows = _AbsRepo().list_all(
            status_in=['approved'],
            employee_id=employee_id,
            date_from=slot_date,
            date_to=slot_date,
        )
        booked = list(appt_rows)
        for ab in absence_rows:
            if ab['time_from'] is None:
                booked.append({'start_time': work_start, 'end_time': work_end})
            else:
                booked.append({'start_time': ab['time_from'], 'end_time': ab['time_to']})

        svc = AppointmentBusinessService()
        all_slots = svc.get_available_slots(
            employee_id, slot_date, duration,
            work_start=work_start,
            work_end=work_end,
            booked=booked,
        )
        # On today's date, hide slots that start within the next 30 minutes
        # (minimum travel time assumption — clients booking same-day need to arrive)
        if slot_date == date.today():
            cutoff = (datetime.now() + timedelta(minutes=30)).time()
            available = [
                s for s in all_slots
                if s['available'] and datetime.strptime(s['start_time'], '%H:%M').time() > cutoff
            ]
        else:
            available = [s for s in all_slots if s['available']]

        return jsonify({
            'success': True,
            'slots': available,
            'date': date_str,
            'off_day': False,
            'work_hours': f"{work_start.strftime('%H:%M')} – {work_end.strftime('%H:%M')}",
        })
    except AppError:
        raise
    except Exception:
        logger.exception('Error fetching available slots')
        return jsonify({'success': False, 'error': 'Nie można wczytać terminów'}), 500


BOOKING_ACTION = 'public_booking'               # must equal data-action on the widget in booking/index.html
BOOKING_IP_LIMIT = '10 per hour; 30 per day'    # every attempt counts: cheap abuse stays cheap to stop
BOOKING_PHONE_LIMIT = '3 per day'               # only bookings that SUCCEEDED count (deduct_when below)

_NAME_MAX, _EMAIL_MAX, _NOTES_MAX = 100, 255, 500
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# Control characters except \t \n \r (the notes box is a textarea).
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def _posted_phone(data) -> Optional[str]:
    """E.164 of the posted phone, or None. Strings only: browsers always send one, and a
    JSON number (scripted client) would silently lose leading zeros / '+'."""
    raw = data.get('phone') if isinstance(data, dict) else None
    return normalize_phone(raw) if isinstance(raw, str) else None


def _booking_phone_key() -> str:
    """Limiter key for the per-phone budget: the normalised number, else the visitor's IP."""
    phone = _posted_phone(request.get_json(silent=True))
    return f'phone:{phone}' if phone else f'ip:{client_ip()}'


def _text(data: dict, field: str, label: str, max_len: int, *, required: bool = True) -> str:
    value = data.get(field)
    if value is None or value == '':
        if required:
            raise ValidationError(f'Brakujące pole: {label}')
        return ''
    if not isinstance(value, str):
        raise ValidationError(f'Nieprawidłowa wartość pola: {label}')
    value = value.strip()
    if _CONTROL_CHARS_RE.search(value):
        raise ValidationError(f'Nieprawidłowe znaki w polu: {label}')
    if len(value) > max_len:
        raise ValidationError(f'Pole „{label}” może mieć maksymalnie {max_len} znaków')
    if required and not value:
        raise ValidationError(f'Brakujące pole: {label}')
    return value


def _parse_booking(data: dict) -> dict:
    """Validate and clean the posted booking. Cheap and local, so it runs BEFORE the
    single-use Turnstile token is spent."""
    raw_ids = data.get('service_ids') or ([data.get('service_id')] if data.get('service_id') else [])
    try:
        service_ids = [int(x) for x in raw_ids if x]
        employee_id = int(data.get('employee_id'))
    except (TypeError, ValueError):
        raise ValidationError('Nieprawidłowe dane rezerwacji')
    if not service_ids:
        raise ValidationError('Wymagane: service_ids')
    if len(service_ids) > 3:
        raise ValidationError('Maksymalnie 3 usługi na wizytę')
    for field in ('date', 'start_time'):
        if not data.get(field):
            raise ValidationError(f'Brakujące pole: {field}')

    first_name = _text(data, 'first_name', 'imię', _NAME_MAX)
    last_name = _text(data, 'last_name', 'nazwisko', _NAME_MAX)
    phone = _posted_phone(data)
    if not phone:
        raise ValidationError(f'Nieprawidłowy numer telefonu. {PHONE_FORMAT_HINT}')
    email = _text(data, 'email', 'e-mail', _EMAIL_MAX, required=False)
    if email and not _EMAIL_RE.match(email):
        raise ValidationError('Nieprawidłowy adres e-mail')

    return {
        'service_ids': service_ids, 'employee_id': employee_id,
        'appt_date': _parse_date(data['date']), 'start_time': _parse_time(data['start_time']),
        'first_name': first_name, 'last_name': last_name, 'phone': phone,
        'email': email or None, 'notes': _text(data, 'notes', 'uwagi', _NOTES_MAX, required=False),
    }


def _require_human(token) -> None:
    """Turnstile gate. 400 = try again; 503 = we couldn't get a verdict (fail-closed)."""
    verdict = turnstile.verify(
        token, remote_ip=client_ip(),
        expected_hostname=request.host.split(':')[0], expected_action=BOOKING_ACTION)
    if verdict.outcome == turnstile.UNAVAILABLE:
        raise AppError('Weryfikacja anty-botowa jest chwilowo niedostępna. '
                       'Spróbuj ponownie za chwilę lub zadzwoń do salonu.', 503)
    if not verdict.ok:
        raise ValidationError('Nie udało się potwierdzić, że nie jesteś robotem. '
                              'Odśwież stronę i spróbuj ponownie.')


def _resolve_client(client_repo: ClientRepository, booking: dict):
    """Which client does this booking belong to? Returns (client_id, is_new).

    Never guess. An existing client is reused only when the phone matches EXACTLY (any
    stored spelling) AND the surname matches — otherwise whoever types a number would
    attach the visit (and its texts) to that client. Old behaviour: `phone ILIKE '%600%'`,
    first alphabetical hit wins, so typing "600" booked onto a random client.
    A mismatch creates a new client carrying a note for the desk to review.
    """
    last, first = fold_name(booking['last_name']), fold_name(booking['first_name'])
    candidates = client_repo.find_by_phone_keys(phone_match_keys(booking['phone']))
    for row in candidates:
        row_last = fold_name(row['last_name'])
        if row_last == last or (not row_last and fold_name(row['first_name']) == first):
            return row['id'], False

    notes, email = [], booking['email']
    if candidates:
        notes.append(f"numer telefonu jest już przypisany do klienta #{candidates[0]['id']} (inne nazwisko)")
    if email:
        by_email = client_repo.find_by_email(email)
        if by_email:
            if fold_name(by_email['last_name']) == last:
                return by_email['id'], False
            notes.append(f"e-mail należy do klienta #{by_email['id']} (inne nazwisko) — nie zapisano go przy nowym kliencie")
            email = None          # clients.email is UNIQUE
    review = ('Rezerwacja online — do weryfikacji: ' + '; '.join(notes) + '.') if notes else None
    return _create_guest_client(client_repo, booking, email, review), True


def _send_booking_confirmation(client_repo: ClientRepository, client_id: int, is_new_client: bool,
                                appointment_id: int) -> dict:
    """The single text an online booking triggers. A phone number with no confirmed/completed
    history is 'unverified': its reminders are held until the client clicks the link."""
    try:
        hold = is_new_client or not client_repo.has_verified_history(client_id)
        return SmsService().send_booking_confirmation(appointment_id, hold=hold)
    except Exception:
        logger.exception('Booking confirmation SMS failed appt=%s', appointment_id)
        return {'status': 'failed', 'hold': False}


@booking_bp.route('/api/public/book', methods=['POST'])
@limiter.limit(BOOKING_IP_LIMIT)
@limiter.limit(BOOKING_PHONE_LIMIT, key_func=_booking_phone_key,
               deduct_when=lambda response: response.status_code < 400)
def create_public_booking():
    """Create a booking from the public booking page.

    Body (JSON): service_ids (array, ≤3), employee_id, date (YYYY-MM-DD), start_time (HH:MM),
    first_name, last_name, phone, email (optional), notes (optional), turnstile_token.
    (Legacy single `service_id` is still accepted.)

    Order matters: validate (cheap, local) → Turnstile (spends the single-use token) →
    resolve the client (exact phone + surname) → create the visit → one confirmation SMS.
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValidationError('Brak danych')

        booking = _parse_booking(data)
        _require_human(data.get('turnstile_token'))

        client_repo = ClientRepository()
        client_id, is_new_client = _resolve_client(client_repo, booking)

        booking_note = 'Rezerwacja online'
        notes = f"{booking_note} — {booking['notes']}" if booking['notes'] else booking_note

        result = AppointmentBusinessService().create_appointment(
            client_id=client_id,
            employee_id=booking['employee_id'],
            service_ids=booking['service_ids'],
            appt_date=booking['appt_date'],
            start_time=booking['start_time'],
            notes=notes,
            created_by=None,  # Public booking — no logged-in user
        )

        try:
            AuditRepository().log_event(
                entity_type='appointment', action='CREATE', entity_id=result['appointment_id'],
                entity_label=f"{data['date']} {data['start_time']}",
                user_id=None, user_name='Rezerwacja online',
            )
        except Exception:
            logger.exception('Failed to log appointment creation from online booking')

        sms = _send_booking_confirmation(client_repo, client_id, is_new_client, result['appointment_id'])

        return jsonify({
            'success': True,
            'appointment_id': result['appointment_id'],
            'total_price': float(result['total_price']),
            'total_duration': result['total_duration'],
            'end_time': result['end_time'],
            'confirmation_sms': sms['status'],        # sent | skipped | failed
            'confirmation_required': bool(sms.get('hold')),
        }), 201

    except AppError:
        raise
    except Exception:
        logger.exception('Error creating public booking')
        return jsonify({'success': False, 'error': 'Nie udało się dokonać rezerwacji'}), 500


def _create_guest_client(client_repo: ClientRepository, booking: dict, email, review_note) -> int:
    """Create a new client record from a (validated) booking."""
    client = Client(
        first_name=booking['first_name'],
        last_name=booking['last_name'],
        phone=booking['phone'],               # E.164, fits VARCHAR(20)
        email=email,
        notes=review_note,
        is_active=True,
    )
    client_id = client_repo.create(client)

    # Audit: new client created via online booking
    try:
        AuditRepository().log_event(
            entity_type='client', action='CREATE', entity_id=client_id,
            entity_label=f"{booking['first_name']} {booking['last_name']}",
            user_id=None, user_name='Rezerwacja online',
        )
    except Exception:
        logger.exception('Failed to log client creation from online booking')

    return client_id
