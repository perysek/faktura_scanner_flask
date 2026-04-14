"""
Public booking routes — accessible without authentication.
Clients can browse services, check available slots, and book appointments.
"""
import json
import logging
from datetime import datetime, date, time

from flask import Blueprint, jsonify, request, render_template

from exceptions import AppError, ValidationError
from repositories.services.service_repository import ServiceRepository
from repositories.employees.employee_service_repository import EmployeeServiceRepository
from repositories.clients.client_repository import ClientRepository
from services.appointment_service import AppointmentBusinessService, AppointmentError
from database.models import Client

logger = logging.getLogger(__name__)

booking_bp = Blueprint('booking', __name__)

# ─── Constants ───────────────────────────────────────────────────────────────
_WEEKDAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
_DEFAULT_WORK_START = time(9, 0)
_DEFAULT_WORK_END   = time(18, 0)

_DAY_PL = {
    'mon': 'pon', 'tue': 'wt', 'wed': 'śr',
    'thu': 'czw', 'fri': 'pt', 'sat': 'sob', 'sun': 'nd',
}


# ─── Schedule Helpers ─────────────────────────────────────────────────────────

def _parse_schedule_time_part(t_str: str) -> time:
    """Parse "H", "HH", or "HH:MM" to a time object."""
    t_str = t_str.strip()
    if ':' in t_str:
        return datetime.strptime(t_str, '%H:%M').time()
    return time(int(t_str), 0)


def _parse_day_hours(schedule_dict: dict, day_key: str):
    """Return (start_time, end_time) for a day, or None if off.

    Accepts schedule values like "9-17", "9:30-18:30", "0", "".
    """
    val = schedule_dict.get(day_key, '').strip()
    if not val or val == '0':
        return None
    parts = val.split('-')
    if len(parts) != 2:
        return None
    try:
        return _parse_schedule_time_part(parts[0]), _parse_schedule_time_part(parts[1])
    except (ValueError, AttributeError):
        return None


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


def _work_hours_for_day(work_schedule_json, day_key: str):
    """Return (start_time, end_time) for a specific day, or default if no schedule."""
    sched: dict = {}
    if work_schedule_json:
        try:
            sched = json.loads(work_schedule_json) if isinstance(work_schedule_json, str) else work_schedule_json
        except (json.JSONDecodeError, TypeError):
            pass

    if not sched:
        return _DEFAULT_WORK_START, _DEFAULT_WORK_END

    hours = _parse_day_hours(sched, day_key)
    if hours is None:
        return None  # Employee is off on this day
    return hours


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
            day_booked = appts_by_date.get(day_date.isoformat(), [])
            slots = svc.get_available_slots(
                employee_id, day_date, duration,
                work_start=work_start, work_end=work_end,
                booked=day_booked,  # in-memory conflict check — no extra DB queries
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
        svc = AppointmentBusinessService()
        all_slots = svc.get_available_slots(
            employee_id, slot_date, duration,
            work_start=work_start,
            work_end=work_end,
        )
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
        service_id, employee_id, date (YYYY-MM-DD), start_time (HH:MM),
        first_name, last_name, phone, email (optional), notes (optional)

    Logic:
        1. Find existing client by phone; create new one if not found.
        2. Delegate to AppointmentBusinessService.create_appointment.
    """
    try:
        data = request.get_json()
        if not data:
            raise ValidationError('Brak danych')

        required = ['service_id', 'employee_id', 'date', 'start_time',
                    'first_name', 'last_name', 'phone']
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
            service_ids=[int(data['service_id'])],
            appt_date=_parse_date(data['date']),
            start_time=_parse_time(data['start_time']),
            notes=notes,
            created_by=None,  # Public booking — no logged-in user
        )

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
    return client_repo.create(client)
