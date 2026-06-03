"""
Public booking routes — accessible without authentication.
Clients can browse services, check available slots, and book appointments.
"""
import json
import logging
from datetime import datetime, date, time, timedelta

from flask import Blueprint, jsonify, request, render_template

from exceptions import AppError, ValidationError
from repositories.services.service_repository import ServiceRepository
from repositories.employees.employee_service_repository import EmployeeServiceRepository
from repositories.clients.client_repository import ClientRepository
from repositories.audit_repository import AuditRepository
from services.appointment_service import AppointmentBusinessService, AppointmentError
from database.models import Client
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
    """Public booking page — no authentication required."""
    return render_template('booking/index.html')


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


@booking_bp.route('/api/public/book', methods=['POST'])
def create_public_booking():
    """Create a booking from the public booking page.

    Body (JSON):
        service_ids (array, required), employee_id, date (YYYY-MM-DD),
        start_time (HH:MM), first_name, last_name, phone,
        email (optional), notes (optional)

    Also accepts legacy single service_id for backwards compatibility.

    Logic:
        1. Find existing client by phone; create new one if not found.
        2. Delegate to AppointmentBusinessService.create_appointment.
    """
    try:
        data = request.get_json()
        if not data:
            raise ValidationError('Brak danych')

        # Resolve service IDs — accept array (new) or single (legacy)
        raw_ids = data.get('service_ids') or ([data.get('service_id')] if data.get('service_id') else [])
        service_ids = [int(x) for x in raw_ids if x]
        if not service_ids:
            raise ValidationError('Wymagane: service_ids')
        if len(service_ids) > 3:
            raise ValidationError('Maksymalnie 3 usługi na wizytę')

        required = ['employee_id', 'date', 'start_time', 'first_name', 'last_name', 'phone']
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise ValidationError(f'Brakujące pola: {", ".join(missing)}')

        # ── Resolve client ─────────────────────────────────────────────
        client_repo = ClientRepository()
        phone = data['phone'].strip()

        existing = client_repo.search_by_phone(phone)
        if existing:
            client_id = existing[0]['id']
        else:
            # Also try by email if provided
            email = (data.get('email') or '').strip()
            if email:
                existing_by_email = client_repo.find_by_email(email)
                if existing_by_email:
                    client_id = existing_by_email['id']
                else:
                    client_id = _create_guest_client(client_repo, data)
            else:
                client_id = _create_guest_client(client_repo, data)

        # ── Build notes ────────────────────────────────────────────────
        user_notes = (data.get('notes') or '').strip()
        booking_note = 'Rezerwacja online'
        notes = f"{booking_note} — {user_notes}" if user_notes else booking_note

        # ── Create appointment ─────────────────────────────────────────
        appt_service = AppointmentBusinessService()
        result = appt_service.create_appointment(
            client_id=client_id,
            employee_id=int(data['employee_id']),
            service_ids=service_ids,
            appt_date=_parse_date(data['date']),
            start_time=_parse_time(data['start_time']),
            notes=notes,
            created_by=None,  # Public booking — no logged-in user
        )

        # ── Audit: appointment created via online booking ──────────────
        try:
            AuditRepository().log_event(
                entity_type='appointment',
                action='CREATE',
                entity_id=result['appointment_id'],
                entity_label=f"{data['date']} {data['start_time']}",
                user_id=None,
                user_name='Rezerwacja online',
            )
        except Exception:
            logger.exception('Failed to log appointment creation from online booking')

        return jsonify({
            'success': True,
            'appointment_id': result['appointment_id'],
            'total_price': float(result['total_price']),
            'total_duration': result['total_duration'],
            'end_time': result['end_time'],
        }), 201

    except AppError:
        raise
    except Exception:
        logger.exception('Error creating public booking')
        return jsonify({'success': False, 'error': 'Nie udało się dokonać rezerwacji'}), 500


def _create_guest_client(client_repo: ClientRepository, data: dict) -> int:
    """Create a new client record from booking form data."""
    client = Client(
        first_name=data['first_name'].strip(),
        last_name=data['last_name'].strip(),
        phone=data['phone'].strip(),
        email=(data.get('email') or '').strip() or None,
        is_active=True,
    )
    client_id = client_repo.create(client)

    # Audit: new client created via online booking
    try:
        name = f"{data['first_name'].strip()} {data['last_name'].strip()}"
        AuditRepository().log_event(
            entity_type='client',
            action='CREATE',
            entity_id=client_id,
            entity_label=name,
            user_id=None,
            user_name='Rezerwacja online',
        )
    except Exception:
        logger.exception('Failed to log client creation from online booking')

    return client_id
