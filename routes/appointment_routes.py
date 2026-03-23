"""
API routes for appointment management
"""
from datetime import datetime, date, time
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from config.auth_config import module_permission_required, role_required
from services.appointment_service import AppointmentBusinessService, AppointmentError
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
from repositories.audit_repository import AuditRepository


def _audit(entity_type, action, entity_id=None, entity_label=None,
           field_name=None, old_value=None, new_value=None):
    """Helper: log audit event with current user context. Logs errors to stderr."""
    try:
        uid = current_user.id if current_user.is_authenticated else None
        uname = current_user.full_name if current_user.is_authenticated else None
        AuditRepository().log_event(
            entity_type=entity_type, action=action,
            entity_id=entity_id, entity_label=entity_label,
            field_name=field_name, old_value=old_value, new_value=new_value,
            user_id=uid, user_name=uname,
        )
    except Exception as e:
        import sys
        print(f"[AUDIT ERROR] {entity_type}/{action} id={entity_id}: {e}", file=sys.stderr)


def _canonical(value) -> str:
    """Canonical string for change-detection — same logic as in api_routes."""
    if value is None or value == '':
        return ''
    try:
        f = float(str(value))
        return str(int(f)) if f == int(f) else str(f)
    except (ValueError, TypeError):
        return str(value).strip()

appointment_bp = Blueprint('appointments', __name__)


def _parse_date(date_str):
    """Parse date string (YYYY-MM-DD) to date object"""
    if not date_str:
        return None
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def _parse_time(time_str):
    """Parse time string (HH:MM or HH:MM:SS) to time object"""
    if not time_str:
        return None
    time_str = str(time_str).strip()
    # Try HH:MM:SS first, then HH:MM
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Nieprawidłowy format czasu: {time_str}")


@appointment_bp.route('/appointments', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_appointments():
    """Pobierz wizyty z opcjonalnym filtrowaniem po dacie/pracowniku/statusie"""
    try:
        mode = request.args.get('mode')
        employee_id = request.args.get('employee_id', type=int)
        status = request.args.get('status')
        repo = AppointmentRepository()

        if mode == 'latest':
            rows = repo.get_latest(limit=100, employee_id=employee_id, status=status)
        else:
            start_date = _parse_date(request.args.get('start_date'))
            end_date = _parse_date(request.args.get('end_date'))

            if not start_date or not end_date:
                # Domyślnie bieżący tydzień
                today = date.today()
                start_date = today
                end_date = today

            rows = repo.get_by_date_range(start_date, end_date, employee_id, status)

        appointments = [dict(row) for row in rows]
        return jsonify({'success': True, 'appointments': appointments, 'count': len(appointments)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/table-data', methods=['GET'])
@login_required
@module_permission_required('data_correction')
def get_table_data():
    """Pobierz wizyty z usługami do edytowalnej tabeli"""
    try:
        status = request.args.get('status')
        limit = min(request.args.get('limit', 100, type=int), 200)
        offset = request.args.get('offset', 0, type=int)

        repo = AppointmentRepository()
        rows = repo.get_latest(limit=limit, offset=offset, status=status)
        appointments = [dict(row) for row in rows]

        if appointments:
            appt_ids = [a['id'] for a in appointments]
            svc_repo = AppointmentServiceRepository()
            services_map = svc_repo.get_all_for_appointments_batch(appt_ids)

            for appt in appointments:
                svcs = services_map.get(appt['id'], [])
                for s in svcs:
                    for key in s:
                        if isinstance(s[key], Decimal):
                            s[key] = float(s[key])
                appt['services'] = svcs
                for key in appt:
                    if isinstance(appt[key], Decimal):
                        appt[key] = float(appt[key])
        else:
            for appt in appointments:
                appt['services'] = []

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

        appt_date = data.get('appointment_date', '')
        _audit('appointment', 'CREATE', entity_id=result.get('appointment_id'),
               entity_label=f"{appt_date} {data.get('start_time','')}",
               new_value=f"klient={data.get('client_id')} pracownik={data.get('employee_id')}")
        return jsonify({'success': True, **result}), 201
    except AppointmentError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['GET'])
@login_required
@module_permission_required('appointments', 'data_correction')
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
@module_permission_required('appointments', 'data_correction')
def check_appointment_conflict():
    """
    Sprawdź czy wizyta koliduje z innymi wizytami.

    Sprawdza dwa rodzaje konfliktów:
    1. Konflikt pracownika - czy pracownik ma już wizytę w tym czasie
    2. Konflikt klienta - czy klient ma już wizytę w tym czasie (z dowolnym pracownikiem)
    """
    try:
        employee_id = request.args.get('employee_id', type=int)
        client_id = request.args.get('client_id', type=int)
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

        repo = AppointmentRepository()

        # Check for employee conflicts
        employee_conflicts = repo.find_conflicting_appointments(
            employee_id=employee_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            exclude_appointment_id=exclude_appointment_id
        )

        # Check for client conflicts (if client_id provided)
        client_conflicts = []
        if client_id:
            client_conflicts = repo.check_client_conflicts(
                client_id=client_id,
                appt_date=appointment_date,
                start_time=start_time,
                end_time=end_time,
                exclude_appointment_id=exclude_appointment_id
            )

        # Determine conflict type and message
        has_conflict = len(employee_conflicts) > 0 or len(client_conflicts) > 0
        message = None
        conflict_type = None

        if len(employee_conflicts) > 0:
            conflict_type = 'employee'
            message = f"Konflikt pracownika - wizyta o godz. {employee_conflicts[0]['start_time']}-{employee_conflicts[0]['end_time']}"
        elif len(client_conflicts) > 0:
            conflict_type = 'client'
            conflict = client_conflicts[0]
            conflict_time = f"{conflict['start_time']}-{conflict['end_time']}"
            try:
                employee_name = conflict['employee_name']
            except (KeyError, TypeError):
                employee_name = 'inny pracownik'
            message = f"Konflikt klienta - ma już wizytę o {conflict_time} z {employee_name}"

        def _serialize_conflict(row):
            d = dict(row)
            for k, v in d.items():
                if hasattr(v, 'strftime'):
                    d[k] = v.strftime('%H:%M:%S') if hasattr(v, 'hour') else v.isoformat()
                elif isinstance(v, Decimal):
                    d[k] = float(v)
            return d

        return jsonify({
            'success': True,
            'has_conflict': has_conflict,
            'conflict_type': conflict_type,
            'message': message,
            'employee_conflicts': [_serialize_conflict(c) for c in employee_conflicts],
            'client_conflicts': [_serialize_conflict(c) for c in client_conflicts]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
@module_permission_required('appointments', 'data_correction')
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

        force = data.get('force', False)

        # Check for conflicts (skip if force=True, e.g. superadmin override)
        if not force:
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
            services=data['services'],
            force_save=force,
        )

        entity_label = f"{data.get('appointment_date')} {data.get('start_time','')}"
        old_row = dict(row)
        for field in ['appointment_date', 'start_time', 'end_time',
                      'employee_id', 'client_id', 'status', 'notes']:
            if field not in data:   # field was not sent — not a change
                continue
            old_val = _canonical(old_row.get(field))
            new_val = _canonical(data.get(field))
            if old_val != new_val:
                _audit('appointment', 'UPDATE', entity_id=appointment_id,
                       entity_label=entity_label,
                       field_name=field,
                       old_value=old_val or None,
                       new_value=new_val or None)
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

        # Fetch old status before the transition
        old_row = AppointmentRepository().get_by_id(appointment_id)
        old_status = old_row['status'] if old_row else None

        service = AppointmentBusinessService()
        success = service.transition_status(
            appointment_id, new_status,
            cancellation_reason=data.get('cancellation_reason')
        )
        if success:
            cancellation_reason = data.get('cancellation_reason')
            new_val = f"{new_status} ({cancellation_reason})" if cancellation_reason else new_status
            _audit('appointment', 'STATUS_CHANGE', entity_id=appointment_id,
                   field_name='status',
                   old_value=old_status,
                   new_value=new_val)
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

        _audit('appointment', 'COMPLETE', entity_id=appointment_id,
               field_name='status', new_value='completed')
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


@appointment_bp.route('/appointments/past-pending', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_past_pending_appointments():
    """
    Pobierz przeszłe wizyty z nieukończonym statusem (do aktualizacji).

    Zwraca wizyty które:
    - Zakończyły się (data + end_time < NOW)
    - Mają status inny niż: 'completed', 'cancelled', 'no_show'

    Returns:
        JSON z listą wizyt do aktualizacji statusu
    """
    try:
        repo = AppointmentRepository()
        rows = repo.get_past_pending_appointments()

        # Convert rows to dictionaries
        appointments = []
        for row in rows:
            appointments.append({
                'id': row['id'],
                'client_id': row['client_id'],
                'client_name': row['client_name'],
                'employee_id': row['employee_id'],
                'employee_name': row['employee_name'],
                'appointment_date': row['appointment_date'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'status': row['status'],
                'service_names': row['service_names'],
                'total_price': float(row['total_price']) if row['total_price'] else 0.0,
                'notes': row['notes']
            })

        return jsonify({
            'success': True,
            'appointments': appointments,
            'count': len(appointments)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/appointments/<int:appointment_id>/past-status', methods=['PUT'])
@login_required
@module_permission_required('appointments')
def update_past_appointment_status(appointment_id):
    """
    Zaktualizuj status przeszłej wizyty (omija standardową walidację przejść).

    Dedykowany endpoint dla skanera przeszłych wizyt.
    Pozwala na bezpośrednie ustawienie statusów finalnych dla wizyt które się już odbyły.

    Walidacja:
    - Wizyta musi być przeszła (appointment_date + end_time < NOW)
    - Nowy status musi być finalny: 'completed', 'cancelled', 'no_show'
    """
    try:
        data = request.get_json()
        new_status = data.get('status')

        if not new_status:
            return jsonify({'success': False, 'error': 'Brak statusu'}), 400

        # Walidacja: czy status jest finalny
        ALLOWED_FINAL_STATUSES = ['completed', 'cancelled', 'no_show']
        if new_status not in ALLOWED_FINAL_STATUSES:
            return jsonify({
                'success': False,
                'error': f'Dozwolone statusy: {", ".join(ALLOWED_FINAL_STATUSES)}'
            }), 400

        repo = AppointmentRepository()
        row = repo.get_by_id(appointment_id)

        if not row:
            return jsonify({'success': False, 'error': 'Wizyta nie istnieje'}), 404

        # Walidacja: czy wizyta jest przeszła
        from datetime import datetime
        appointment_datetime_str = f"{row['appointment_date']} {row['end_time']}"
        appointment_datetime = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()

        if appointment_datetime >= now:
            return jsonify({
                'success': False,
                'error': 'Można aktualizować tylko wizyty które się już zakończyły'
            }), 400

        # Walidacja: czy status już nie jest finalny
        if row['status'] in ALLOWED_FINAL_STATUSES:
            return jsonify({
                'success': False,
                'error': f'Wizyta ma już finalny status: {row["status"]}'
            }), 400

        # Aktualizacja statusu bezpośrednio (omijamy transition_status)
        old_status = row['status']
        cancellation_reason = data.get('cancellation_reason') if new_status == 'cancelled' else None
        success = repo.update_status(appointment_id, new_status, cancellation_reason)

        if success:
            appt_label = f"{row['appointment_date']} {row.get('start_time','')}"
            new_val = f"{new_status} ({cancellation_reason})" if cancellation_reason else new_status
            _audit('appointment', 'STATUS_CHANGE', entity_id=appointment_id,
                   entity_label=appt_label,
                   field_name='status',
                   old_value=old_status,
                   new_value=new_val)
            return jsonify({'success': True, 'message': f'Status zaktualizowany na: {new_status}'})
        else:
            return jsonify({'success': False, 'error': 'Nie udało się zaktualizować statusu'}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@appointment_bp.route('/clients/<int:client_id>/appointments', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_client_appointments(client_id):
    """Pobierz historię wizyt klienta (wszystkie, posortowane malejąco po dacie)"""
    try:
        limit = request.args.get('limit', 100, type=int)
        repo = AppointmentRepository()
        rows = repo.get_client_appointments(client_id, limit=limit)
        appointments = []
        for row in rows:
            a = dict(row)
            for key in ['total_price', 'discount_amount']:
                if a.get(key) is not None:
                    a[key] = float(a[key])
            if a.get('appointment_date'):
                a['appointment_date'] = str(a['appointment_date'])
            if a.get('start_time'):
                a['start_time'] = str(a['start_time'])
            if a.get('end_time'):
                a['end_time'] = str(a['end_time'])
            appointments.append(a)
        return jsonify({'success': True, 'appointments': appointments, 'count': len(appointments)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@appointment_bp.route('/appointments/<int:appointment_id>/satisfaction', methods=['PATCH'])
@login_required
@module_permission_required('appointments')
def set_satisfaction_score(appointment_id: int):
    """Ustaw ocenę satysfakcji (1–5) dla zakończonej wizyty."""
    data = request.get_json()
    score = data.get('score') if data else None
    if not isinstance(score, int) or score < 1 or score > 5:
        return jsonify({'success': False, 'error': 'Wynik musi być liczbą całkowitą 1–5'}), 400
    repo = AppointmentRepository()
    ok = repo.update_satisfaction_score(appointment_id, score)
    if not ok:
        return jsonify({'success': False, 'error': 'Nie można ocenić — wizyta nie jest zakończona lub nie istnieje'}), 404
    return jsonify({'success': True, 'appointment_id': appointment_id, 'score': score})


@appointment_bp.route('/appointments/adjacent', methods=['GET'])
@login_required
@module_permission_required('data_correction')
def get_adjacent_appointments():
    """Zwróć ID poprzedniej i następnej wizyty."""
    appointment_id = request.args.get('id', type=int)
    mode = request.args.get('mode', 'all')  # 'all' | 'day'
    if not appointment_id:
        return jsonify({'success': False, 'error': 'Missing id'}), 400
    repo = AppointmentRepository()
    result = repo.get_adjacent_appointments(appointment_id, mode)
    return jsonify({'success': True, **result})
