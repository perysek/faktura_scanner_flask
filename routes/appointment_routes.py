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


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
@module_permission_required('appointments')
def update_appointment(appointment_id):
    """Zaktualizuj wizytę"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        repo = AppointmentRepository()
        row = repo.get_by_id(appointment_id)
        if not row:
            return jsonify({'success': False, 'error': 'Wizyta nie istnieje'}), 404

        from database.models import Appointment
        appt = repo.row_to_appointment(row)

        # Update fields from request data
        if 'client_id' in data:
            appt.client_id = int(data['client_id'])
        if 'employee_id' in data:
            appt.employee_id = int(data['employee_id'])
        if 'appointment_date' in data:
            appt.appointment_date = _parse_date(data['appointment_date'])
        if 'start_time' in data:
            appt.start_time = _parse_time(data['start_time'])
        if 'end_time' in data:
            appt.end_time = _parse_time(data['end_time'])
        if 'notes' in data:
            appt.notes = data.get('notes')
        if 'discount_amount' in data:
            appt.discount_amount = Decimal(str(data['discount_amount']))

        success = repo.update(appointment_id, appt)
        return jsonify({'success': success})
    except Exception as e:
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
