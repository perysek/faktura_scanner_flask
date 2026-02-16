"""
API routes for appointment management
"""
from datetime import datetime, date, time
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from config.auth_config import module_permission_required
from services.appointment_service import AppointmentBusinessService, AppointmentError
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.appointment_service_repository import AppointmentServiceRepository

appointment_bp = Blueprint('appointments', __name__)


def _parse_date(date_str):
    """Parse date string (YYYY-MM-DD) to date object"""
    if not date_str:
        return None
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def _parse_time(time_str):
    """Parse time string (HH:MM) to time object"""
    if not time_str:
        return None
    return datetime.strptime(time_str, '%H:%M').time()


@appointment_bp.route('/appointments', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_appointments():
    """Pobierz wizyty z opcjonalnym filtrowaniem po dacie/pracowniku/statusie"""
    try:
        start_date = _parse_date(request.args.get('start_date'))
        end_date = _parse_date(request.args.get('end_date'))
        employee_id = request.args.get('employee_id', type=int)
        status = request.args.get('status')

        if not start_date or not end_date:
            # Domyślnie bieżący tydzień
            today = date.today()
            start_date = today
            end_date = today

        repo = AppointmentRepository()
        rows = repo.get_by_date_range(start_date, end_date, employee_id, status)

        appointments = [dict(row) for row in rows]
        return jsonify({'success': True, 'appointments': appointments, 'count': len(appointments)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments', methods=['POST'])
@login_required
@module_permission_required('appointments')
def create_appointment():
    """Utwórz nową wizytę"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        required = ['client_id', 'employee_id', 'service_ids', 'appointment_date', 'start_time']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'success': False, 'error': f'Brakujące pola: {", ".join(missing)}'}), 400

        service = AppointmentBusinessService()
        result = service.create_appointment(
            client_id=int(data['client_id']),
            employee_id=int(data['employee_id']),
            service_ids=[int(sid) for sid in data['service_ids']],
            appt_date=_parse_date(data['appointment_date']),
            start_time=_parse_time(data['start_time']),
            notes=data.get('notes'),
            created_by=current_user.id if current_user.is_authenticated else None
        )

        return jsonify({'success': True, **result}), 201
    except AppointmentError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_appointment(appointment_id):
    """Pobierz szczegóły wizyty"""
    try:
        service = AppointmentBusinessService()
        details = service.get_appointment_details(appointment_id)

        if not details:
            return jsonify({'success': False, 'error': 'Wizyta nie istnieje'}), 404

        # Convert Decimal to float for JSON serialization
        totals = details['totals']
        for key in totals:
            if isinstance(totals[key], Decimal):
                totals[key] = float(totals[key])

        return jsonify({'success': True, **details})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/check-conflict', methods=['GET'])
@login_required
@module_permission_required('appointments')
def check_appointment_conflict():
    """Sprawdź czy wizyta koliduje z innymi wizytami pracownika"""
    try:
        employee_id = request.args.get('employee_id', type=int)
        appointment_date = _parse_date(request.args.get('appointment_date'))
        start_time = _parse_time(request.args.get('start_time'))
        duration_minutes = request.args.get('duration_minutes', type=int)
        exclude_appointment_id = request.args.get('exclude_appointment_id', type=int)

        if not all([employee_id, appointment_date, start_time, duration_minutes]):
            return jsonify({'success': False, 'error': 'Brakujące parametry'}), 400

        # Calculate end time
        from datetime import datetime, timedelta
        start_dt = datetime.combine(appointment_date, start_time)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time = end_dt.time()

        # Check for conflicts
        repo = AppointmentRepository()
        conflicts = repo.find_conflicting_appointments(
            employee_id=employee_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            exclude_appointment_id=exclude_appointment_id
        )

        has_conflict = len(conflicts) > 0
        message = None
        if has_conflict:
            message = f"Konflikt z wizytą o godz. {conflicts[0]['start_time']}-{conflicts[0]['end_time']}"

        return jsonify({
            'success': True,
            'has_conflict': has_conflict,
            'message': message,
            'conflicting_appointments': [dict(c) for c in conflicts]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
@module_permission_required('appointments')
def update_appointment(appointment_id):
    """Zaktualizuj wizytę (pełna edycja z usługami)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        required = ['client_id', 'employee_id', 'appointment_date', 'start_time', 'status', 'services']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({'success': False, 'error': f'Brakujące pola: {", ".join(missing)}'}), 400

        repo = AppointmentRepository()
        row = repo.get_by_id(appointment_id)
        if not row:
            return jsonify({'success': False, 'error': 'Wizyta nie istnieje'}), 404

        # Validate services
        if not data['services'] or len(data['services']) == 0:
            return jsonify({'success': False, 'error': 'Brak usług'}), 400

        # Calculate total duration and end time
        total_duration = sum(int(s['duration_minutes']) for s in data['services'])
        from datetime import datetime, timedelta
        start_time = _parse_time(data['start_time'])
        appointment_date = _parse_date(data['appointment_date'])
        start_dt = datetime.combine(appointment_date, start_time)
        end_dt = start_dt + timedelta(minutes=total_duration)
        end_time = end_dt.time()

        # Check for conflicts (exclude current appointment)
        conflicts = repo.find_conflicting_appointments(
            employee_id=int(data['employee_id']),
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            exclude_appointment_id=appointment_id
        )

        if conflicts:
            conflict_start = conflicts[0]['start_time']
            conflict_end = conflicts[0]['end_time']
            return jsonify({
                'success': False,
                'error': f"Konflikt z wizytą o godz. {conflict_start}-{conflict_end}"
            }), 400

        # Update appointment using business service
        service = AppointmentBusinessService()
        result = service.update_appointment(
            appointment_id=appointment_id,
            client_id=int(data['client_id']),
            employee_id=int(data['employee_id']),
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=data['status'],
            notes=data.get('notes'),
            services=data['services']
        )

        return jsonify({'success': True, **result})
    except AppointmentError as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>/status', methods=['PUT'])
@login_required
@module_permission_required('appointments')
def update_appointment_status(appointment_id):
    """Zmień status wizyty"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        if not new_status:
            return jsonify({'success': False, 'error': 'Brak statusu'}), 400

        service = AppointmentBusinessService()
        success = service.transition_status(
            appointment_id, new_status,
            cancellation_reason=data.get('cancellation_reason')
        )
        return jsonify({'success': success})
    except AppointmentError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>/complete', methods=['POST'])
@login_required
@module_permission_required('appointments')
def complete_appointment(appointment_id):
    """Zamknij wizytę i utwórz rekord przychodu"""
    try:
        data = request.get_json() or {}
        service = AppointmentBusinessService()
        result = service.complete_appointment(
            appointment_id,
            payment_method=data.get('payment_method'),
            discount_amount=Decimal(str(data['discount_amount'])) if data.get('discount_amount') else None
        )

        # Convert Decimal for JSON
        for key in result:
            if isinstance(result[key], Decimal):
                result[key] = float(result[key])

        return jsonify({'success': True, **result})
    except AppointmentError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>/addons', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_available_addons(appointment_id):
    """Pobierz dostępne mikrousługi dla wizyty"""
    try:
        service = AppointmentBusinessService()
        addons = service.get_available_addons(appointment_id)

        # Convert Decimal for JSON
        for addon in addons:
            if isinstance(addon.get('price'), Decimal):
                addon['price'] = float(addon['price'])

        return jsonify({'success': True, 'addons': addons, 'count': len(addons)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>/addons', methods=['POST'])
@login_required
@module_permission_required('appointments')
def add_addon(appointment_id):
    """Dodaj mikrousługę do trwającej wizyty"""
    try:
        data = request.get_json()
        service_id = data.get('service_id')
        if not service_id:
            return jsonify({'success': False, 'error': 'Brak service_id'}), 400

        service = AppointmentBusinessService()
        result = service.add_addon_to_appointment(appointment_id, int(service_id))

        # Convert Decimal for JSON
        for key in result:
            if isinstance(result[key], Decimal):
                result[key] = float(result[key])

        return jsonify({'success': True, **result}), 201
    except AppointmentError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['DELETE'])
@login_required
@module_permission_required('appointments')
def delete_appointment(appointment_id):
    """Usuń wizytę"""
    try:
        repo = AppointmentRepository()
        success = repo.delete(appointment_id)
        if not success:
            return jsonify({'success': False, 'error': 'Wizyta nie istnieje'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/available-slots', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_available_slots():
    """Pobierz wolne sloty dla pracownika na dany dzień"""
    try:
        employee_id = request.args.get('employee_id', type=int)
        slot_date = _parse_date(request.args.get('date'))
        duration = request.args.get('duration', 60, type=int)

        if not employee_id or not slot_date:
            return jsonify({'success': False, 'error': 'Wymagane: employee_id, date'}), 400

        service = AppointmentBusinessService()
        slots = service.get_available_slots(employee_id, slot_date, duration)

        return jsonify({'success': True, 'slots': slots})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/employees', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employees_for_appointments():
    """Pobierz listę pracowników do wyboru w kalendarzu wizyt (uproszczona)"""
    try:
        from repositories.employees.employee_repository import EmployeeRepository

        repo = EmployeeRepository()
        rows = repo.get_all(active_only=True)

        # Return simplified employee data for dropdown
        employees = []
        for row in rows:
            # Construct full_name from first_name and last_name
            full_name = f"{row['first_name']} {row['last_name']}"
            employees.append({
                'id': row['id'],
                'full_name': full_name,
                'position': row['position']
            })

        return jsonify(employees)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/daily-schedule', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_daily_schedule():
    """Pobierz harmonogram dnia pracownika"""
    try:
        employee_id = request.args.get('employee_id', type=int)
        schedule_date = _parse_date(request.args.get('date'))

        if not employee_id or not schedule_date:
            return jsonify({'success': False, 'error': 'Wymagane: employee_id, date'}), 400

        repo = AppointmentRepository()
        rows = repo.get_daily_schedule(employee_id, schedule_date)

        schedule = [dict(row) for row in rows]
        return jsonify({'success': True, 'schedule': schedule, 'count': len(schedule)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/multi-employee-schedule', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_multi_employee_schedule():
    """
    Pobierz harmonogram dnia dla wielu pracowników jednocześnie

    Query params:
        - date: Data harmonogramu (YYYY-MM-DD) [wymagane]
        - offset: Offset paginacji pracowników [opcjonalne, default=0]
        - limit: Limit pracowników na stronę [opcjonalne, default=8]

    Returns:
        {
            'success': True,
            'date': str,
            'employees': [{'id', 'full_name', 'position'}, ...],  # Max 'limit' pracowników
            'schedules': {employee_id: [appointments...], ...},
            'total_employees': int,  # Łączna liczba pracowników z wizytami
            'page': int,  # Aktualna strona (0-indexed)
            'total_pages': int
        }
    """
    try:
        schedule_date = _parse_date(request.args.get('date'))
        if not schedule_date:
            return jsonify({'success': False, 'error': 'Wymagane: date'}), 400

        offset = request.args.get('offset', default=0, type=int)
        limit = request.args.get('limit', default=8, type=int)

        # Validate pagination params
        if offset < 0:
            offset = 0
        if limit < 1 or limit > 20:  # Max 20 employees per page
            limit = 8

        repo = AppointmentRepository()

        # Pobierz wszystkich pracowników z wizytami tego dnia
        all_data = repo.get_multi_employee_schedule(schedule_date, employee_ids=None)
        all_employees = all_data['employees']
        total_employees = len(all_employees)

        # Oblicz paginację
        total_pages = (total_employees + limit - 1) // limit if total_employees > 0 else 0
        current_page = offset // limit

        # Wybierz pracowników dla bieżącej strony
        page_employees = all_employees[offset:offset + limit]
        page_employee_ids = [emp['id'] for emp in page_employees]

        # Pobierz wizyty tylko dla pracowników z bieżącej strony
        page_schedules = {
            emp_id: all_data['schedules'].get(emp_id, [])
            for emp_id in page_employee_ids
        }

        return jsonify({
            'success': True,
            'date': schedule_date.isoformat(),
            'employees': page_employees,
            'schedules': page_schedules,
            'total_employees': total_employees,
            'page': current_page,
            'total_pages': total_pages,
            'has_prev': current_page > 0,
            'has_next': current_page < total_pages - 1
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
