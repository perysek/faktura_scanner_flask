"""
API routes for appointment management
"""
import logging
from datetime import datetime, date, time
from decimal import Decimal

import json
import time as _time

from flask import Blueprint, jsonify, request, Response, stream_with_context
from flask_login import login_required, current_user

from config.appointment_statuses import AppointmentStatus
from config.auth_config import module_permission_required, role_required
from exceptions import AppError, ValidationError, NotFoundError, ConflictError
from services.appointment_service import AppointmentBusinessService, AppointmentError
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
from repositories.appointments.income_repository import IncomeRepository
from repositories.audit_repository import AuditRepository


def _schedule_post_visit_sms(appointment_id: int) -> None:
    """Schedule post-visit rating SMS when visit status -> completed. Swallows errors.
    Called from admin status-change route AND employee mobile form route."""
    try:
        from services.sms_service import SmsService
        from flask import current_app
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        SmsService().schedule_status_triggered_sms(appointment_id, 'completed', base_url)
    except Exception as exc:
        logging.error('_schedule_post_visit_sms failed appt_id=%s: %s', appointment_id, exc)


def _cancel_event_sms(appointment_id: int) -> None:
    """Cancel all pending sms_events when appointment is cancelled."""
    try:
        from repositories.sms.sms_event_repository import SmsEventRepository
        SmsEventRepository().cancel_pending_for_appointment(appointment_id)
    except Exception as exc:
        logging.error('_cancel_event_sms failed appt_id=%s: %s', appointment_id, exc)


def _schedule_employee_reminder_sms(appointment_id: int,
                                     appointment_date, start_time_str: str) -> None:
    """Schedule employee_visit_reminder SMS 20 min before appointment start. Swallows errors.
    Also cancels any existing pending reminder (handles reschedules cleanly)."""
    try:
        from datetime import datetime
        from services.sms_service import SmsService
        h, m = str(start_time_str)[:5].split(':')
        if hasattr(appointment_date, 'year'):
            appt_dt = datetime.combine(appointment_date,
                                       datetime.min.time().replace(hour=int(h), minute=int(m)))
        else:
            appt_dt = datetime.strptime(f"{appointment_date} {h}:{m}", '%Y-%m-%d %H:%M')
        SmsService().schedule_employee_reminder(appointment_id, appt_dt)
    except Exception as exc:
        logging.error('_schedule_employee_reminder_sms failed appt_id=%s: %s', appointment_id, exc)


def _send_confirmation_request_sms(appointment_id: int) -> None:
    """Send a confirmation-request SMS immediately. Used when the salon reschedules
    a previously client-confirmed visit, so the client can re-confirm the new time.
    Swallows errors (incl. SMS disabled/unconfigured) so the save still succeeds."""
    try:
        from services.sms_service import SmsService
        from flask import current_app
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        uid = current_user.id if current_user.is_authenticated else None
        uname = current_user.full_name if current_user.is_authenticated else None
        SmsService().send(appointment_id, 'confirmation_request',
                          sender_user_id=uid, sender_name=uname, base_url=base_url)
    except Exception as exc:
        logging.error('_send_confirmation_request_sms failed appt_id=%s: %s', appointment_id, exc)


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


def _canonical_time(value) -> str:
    """Normalize time values to HH:MM — strips seconds so '09:30:00' == '09:30'."""
    s = _canonical(value)
    # HH:MM:SS → HH:MM (two colons present)
    if s.count(':') == 2:
        return s[:5]
    return s

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

        # Batch-load SMS state for the visible appointments
        sms_sent_map: dict = {}
        sms_types: list = []
        try:
            from repositories.sms.sms_repository import (
                SmsSettingsRepository, SmsMessageTypeRepository, SmsReminderRepository
            )
            sms_active = (SmsSettingsRepository().get_settings() or {}).get('is_active', False)
            if sms_active:
                appt_ids = [a['id'] for a in appointments]
                sms_sent_map = SmsReminderRepository().get_sent_types_batch(appt_ids)
                sms_types = SmsMessageTypeRepository().get_all()
        except Exception:
            logging.exception('SMS batch load failed in get_appointments (non-fatal)')

        return jsonify({
            'success': True,
            'appointments': appointments,
            'count': len(appointments),
            'sms_sent_map': sms_sent_map,
            'sms_types': sms_types,
        })
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_appointments')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/table-data', methods=['GET'])
@login_required
@module_permission_required('data_correction')
def get_table_data():
    """Pobierz wizyty z usługami do edytowalnej tabeli.

    Sortowanie (``sort_col`` / ``sort_dir``) i filtry kolumnowe (``f_<kolumna>``) są
    stosowane po stronie serwera na całym zbiorze danych, a dopiero potem paginacja.
    Dzięki temu po kliknięciu sortowania lub wpisaniu filtra strona zawiera dokładnie
    te wiersze, które byłyby widoczne, gdyby całą bazę posortowano i przefiltrowano.
    Odpowiedź zawiera ``total`` — liczbę wizyt pasujących do filtrów.
    """
    try:
        status = request.args.get('status')
        limit = min(request.args.get('limit', 100, type=int), 200)
        offset = request.args.get('offset', 0, type=int)

        sort_col = request.args.get('sort_col') or None
        sort_dir = request.args.get('sort_dir', 'desc')

        # Per-column filters arrive as f_<col>=substr (only non-empty values kept).
        FILTERABLE = ('id', 'appointment_date', 'start_time', 'client_name',
                      'employee_name', 'status', 'service_name', 'notes')
        filters = {}
        for col in FILTERABLE:
            val = (request.args.get(f'f_{col}') or '').strip()
            if val:
                filters[col] = val

        repo = AppointmentRepository()
        rows = repo.get_latest(limit=limit, offset=offset, status=status,
                               sort_col=sort_col, sort_dir=sort_dir, filters=filters)
        appointments = [dict(row) for row in rows]

        # COUNT(*) OVER() rides on every row; lift it out and drop the helper column.
        total = appointments[0].pop('total_count', len(appointments)) if appointments else 0
        for appt in appointments:
            appt.pop('total_count', None)

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

        return jsonify({'success': True, 'appointments': appointments,
                        'count': len(appointments), 'total': total})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_table_data')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments', methods=['POST'])
@login_required
@module_permission_required('appointments')
def create_appointment():
    """Utwórz nową wizytę"""
    try:
        data = request.get_json()
        if not data:
            raise ValidationError('Brak danych')

        required = ['client_id', 'employee_id', 'service_ids', 'appointment_date', 'start_time']
        missing = [f for f in required if f not in data]
        if missing:
            raise ValidationError(f'Brakujace pola: {", ".join(missing)}')

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

        _schedule_employee_reminder_sms(
            result.get('appointment_id'), appt_date, data.get('start_time', ''))

        return jsonify({'success': True, **result}), 201
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in create_appointment')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['GET'])
@login_required
@module_permission_required('appointments', 'data_correction')
def get_appointment(appointment_id):
    """Pobierz szczegóły wizyty"""
    try:
        service = AppointmentBusinessService()
        details = service.get_appointment_details(appointment_id)

        if not details:
            raise NotFoundError('Wizyta nie istnieje')

        # Convert Decimal to float for JSON serialization
        totals = details['totals']
        for key in totals:
            if isinstance(totals[key], Decimal):
                totals[key] = float(totals[key])

        return jsonify({'success': True, **details})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_appointment')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>/events')
@login_required
@module_permission_required('appointments', 'data_correction')
def appointment_events(appointment_id):
    """SSE stream: pushes confirmation_status changes to the edit page in real time."""
    repo = AppointmentRepository()

    def generate():
        row = repo.get_by_id(appointment_id)
        if not row:
            return
        last_status = row['confirmation_status']
        yield f"data: {json.dumps({'confirmation_status': last_status})}\n\n"

        tick = 0
        while True:
            _time.sleep(3)
            tick += 1
            row = repo.get_by_id(appointment_id)
            if not row:
                return
            current = row['confirmation_status']
            if current != last_status:
                last_status = current
                yield f"data: {json.dumps({'confirmation_status': current})}\n\n"
            elif tick % 5 == 0:
                yield ": hb\n\n"

    resp = Response(stream_with_context(generate()), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


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
            raise ValidationError('Brakujace parametry')

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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in check_appointment_conflict')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
@module_permission_required('appointments', 'data_correction')
def update_appointment(appointment_id):
    """Zaktualizuj wizytę (pełna edycja z usługami)"""
    try:
        data = request.get_json()
        if not data:
            raise ValidationError('Brak danych')

        required = ['client_id', 'employee_id', 'appointment_date', 'start_time', 'status', 'services']
        missing = [f for f in required if f not in data]
        if missing:
            raise ValidationError(f'Brakujace pola: {", ".join(missing)}')

        repo = AppointmentRepository()
        row = repo.get_by_id(appointment_id)
        if not row:
            raise NotFoundError('Wizyta nie istnieje')

        # Validate services
        if not data['services'] or len(data['services']) == 0:
            raise ValidationError('Brak uslug')

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
                raise ConflictError(f"Konflikt z wizyta o godz. {conflict_start}-{conflict_end}")

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
            discount_amount=data.get('discount_amount', 0),
            satisfaction_score=data.get('satisfaction_score'),
        )

        entity_label = f"{data.get('appointment_date')} {data.get('start_time','')}"
        old_row = dict(row)
        _TIME_FIELDS = {'start_time', 'end_time'}
        for field in ['appointment_date', 'start_time', 'end_time',
                      'employee_id', 'client_id', 'status', 'notes',
                      'discount_amount', 'satisfaction_score']:
            if field not in data:   # field was not sent — not a change
                continue
            _norm = _canonical_time if field in _TIME_FIELDS else _canonical
            old_val = _norm(old_row.get(field))
            new_val = _norm(data.get(field))
            if old_val != new_val:
                _audit('appointment', 'UPDATE', entity_id=appointment_id,
                       entity_label=entity_label,
                       field_name=field,
                       old_value=old_val or None,
                       new_value=new_val or None)

        # ── Bug #2: re-confirmation when a client-confirmed visit is rescheduled ──
        # If the date/start-time changed AND the client had already confirmed via SMS,
        # the frontend asks who requested the change and sends timing_change_by:
        #   'client' → keep the confirmation (client already agreed to the new time)
        #   'salon'  → reset status to 'scheduled', clear confirmation, re-send the
        #              confirmation-request SMS so the client confirms the new time.
        from datetime import timedelta as _timedelta
        old_start_val = row['start_time']
        if isinstance(old_start_val, _timedelta):
            old_start_val = (datetime.min + old_start_val).time()
        old_start_str = old_start_val.strftime('%H:%M') if hasattr(old_start_val, 'strftime') else str(old_start_val)[:5]
        old_date_obj = row['appointment_date']
        old_date_str = old_date_obj.isoformat() if hasattr(old_date_obj, 'isoformat') else str(old_date_obj)
        timing_changed = (old_date_str != appointment_date.isoformat()) or \
                         (old_start_str != start_time.strftime('%H:%M'))

        if (timing_changed and row.get('confirmation_status') == 'confirmed'
                and data.get('timing_change_by') == 'salon'):
            repo.reset_confirmation(appointment_id)
            repo.update_status(appointment_id, AppointmentStatus.SCHEDULED)
            _audit('appointment', 'STATUS_CHANGE', entity_id=appointment_id,
                   entity_label=entity_label, field_name='status',
                   old_value='confirmed',
                   new_value='scheduled (zmiana terminu przez salon)')
            _send_confirmation_request_sms(appointment_id)

        # Reschedule employee reminder whenever date/time/employee changes
        _schedule_employee_reminder_sms(
            appointment_id, data.get('appointment_date'), data.get('start_time', ''))

        return jsonify({'success': True, **result})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in update_appointment')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>/status', methods=['PUT'])
@login_required
@module_permission_required('appointments')
def update_appointment_status(appointment_id):
    """Zmień status wizyty"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        if not new_status:
            raise ValidationError('Brak statusu')

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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in update_appointment_status')
        raise AppError('Wystapil blad serwera')


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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in complete_appointment')
        raise AppError('Wystapil blad serwera')


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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_available_addons')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>/addons', methods=['POST'])
@login_required
@module_permission_required('appointments')
def add_addon(appointment_id):
    """Dodaj mikrousługę do trwającej wizyty"""
    try:
        data = request.get_json()
        service_id = data.get('service_id')
        if not service_id:
            raise ValidationError('Brak service_id')

        service = AppointmentBusinessService()
        result = service.add_addon_to_appointment(appointment_id, int(service_id))

        # Convert Decimal for JSON
        for key in result:
            if isinstance(result[key], Decimal):
                result[key] = float(result[key])

        return jsonify({'success': True, **result}), 201
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in add_addon')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>', methods=['DELETE'])
@login_required
@module_permission_required('appointments')
def delete_appointment(appointment_id):
    """Usuń wizytę"""
    try:
        repo = AppointmentRepository()
        existing = repo.get_by_id(appointment_id)
        if not existing:
            # Check if already deleted
            from config.database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, is_deleted FROM appointments WHERE id = %s", (appointment_id,))
                check = cursor.fetchone()
            if check and check.get('is_deleted'):
                raise ConflictError('Ta wizyta zostala juz usunieta')
            raise NotFoundError('Wizyta nie istnieje')

        success = repo.delete(appointment_id)
        if not success:
            raise AppError('Nie udalo sie usunac wizyty')

        # Hide the linked income record (if the visit was completed) so revenue
        # reports stop counting it; restore_appointment below brings it back.
        IncomeRepository().soft_delete_by_appointment(appointment_id)

        return jsonify({
            'success': True,
            'restore_url': f'/appointments/{appointment_id}/restore'
        })
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in delete_appointment')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/<int:appointment_id>/restore', methods=['POST'])
@login_required
@module_permission_required('appointments')
def restore_appointment(appointment_id):
    """Przywroc soft-deleted wizyte (undo delete)"""
    try:
        repo = AppointmentRepository()
        success = repo.restore(appointment_id)
        if not success:
            raise NotFoundError('Wizyta nie jest usunieta lub nie istnieje')

        IncomeRepository().restore_by_appointment(appointment_id)

        return jsonify({'success': True, 'message': 'Wizyta zostala przywrocona'})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in restore_appointment')
        raise AppError('Wystapil blad serwera')


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
            raise ValidationError('Wymagane: employee_id, date')

        service = AppointmentBusinessService()
        slots = service.get_available_slots(employee_id, slot_date, duration)

        return jsonify({'success': True, 'slots': slots})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_available_slots')
        raise AppError('Wystapil blad serwera')


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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_employees_for_appointments')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/absences', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_absences_for_calendar():
    """Return approved absences for a date range — used by week/month calendar views.

    Query params: start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
    Returns list of {employee_id, date_from, date_to, time_from, time_to, category_name}
    """
    try:
        start_date = _parse_date(request.args.get('start_date'))
        end_date   = _parse_date(request.args.get('end_date'))
        if not start_date or not end_date:
            raise ValidationError('Wymagane: start_date, end_date')

        from repositories.absences.absence_repository import AbsenceRepository
        rows = AbsenceRepository().list_all(
            status_in=['approved'],
            date_from=start_date,
            date_to=end_date,
        )

        absences = []
        for ab in rows:
            absences.append({
                'employee_id':   ab['employee_id'],
                'date_from':     str(ab['date_from']),
                'date_to':       str(ab['date_to']),
                'time_from':     str(ab['time_from'])[:5] if ab['time_from'] else None,
                'time_to':       str(ab['time_to'])[:5]   if ab['time_to']   else None,
                'category_name': ab.get('category_name', 'Nieobecność'),
            })

        return jsonify({'success': True, 'absences': absences})
    except AppError:
        raise
    except Exception:
        logging.exception('Error loading absences for calendar')
        raise AppError('Błąd ładowania nieobecności')


@appointment_bp.route('/appointments/daily-schedule', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_daily_schedule():
    """Pobierz harmonogram dnia pracownika"""
    try:
        employee_id = request.args.get('employee_id', type=int)
        schedule_date = _parse_date(request.args.get('date'))

        if not employee_id or not schedule_date:
            raise ValidationError('Wymagane: employee_id, date')

        repo = AppointmentRepository()
        rows = repo.get_daily_schedule(employee_id, schedule_date)

        schedule = [dict(row) for row in rows]
        return jsonify({'success': True, 'schedule': schedule, 'count': len(schedule)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_daily_schedule')
        raise AppError('Wystapil blad serwera')


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
            raise ValidationError('Wymagane: date')

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

        # Also include employees who have approved absences on this day but no appointments
        try:
            from repositories.absences.absence_repository import AbsenceRepository
            from repositories.employees.employee_repository import EmployeeRepository
            absence_rows = AbsenceRepository().list_all(
                status_in=['approved'],
                date_from=schedule_date,
                date_to=schedule_date,
            )
            existing_ids = {emp['id'] for emp in all_employees}
            emp_repo = EmployeeRepository()
            for ab_row in absence_rows:
                emp_id = ab_row['employee_id']
                if emp_id not in existing_ids:
                    emp = emp_repo.get_by_id(emp_id)
                    if emp and emp['is_active']:
                        all_employees.append({
                            'id':       emp['id'],
                            'full_name': f"{emp['first_name']} {emp['last_name']}",
                            'position': emp['position'],
                        })
                        all_data['schedules'].setdefault(emp_id, [])
                        existing_ids.add(emp_id)
        except Exception:
            logging.warning('Could not merge absence-only employees into day schedule', exc_info=True)

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

        # Merge approved absences for the visible employees
        page_absences = {}
        try:
            from repositories.absences.absence_repository import AbsenceRepository
            abs_rows = AbsenceRepository().list_all(
                status_in=['approved'],
                date_from=schedule_date,
                date_to=schedule_date,
            )
            for ab in abs_rows:
                emp_id = ab['employee_id']
                if emp_id not in page_employee_ids:
                    continue
                page_absences.setdefault(emp_id, []).append({
                    'id': ab['id'],
                    'category_name': ab.get('category_name', 'Nieobecność'),
                    'time_from': str(ab['time_from'])[:5] if ab['time_from'] else None,
                    'time_to':   str(ab['time_to'])[:5]   if ab['time_to']   else None,
                })
        except Exception:
            logging.warning('Could not load absences for calendar', exc_info=True)

        return jsonify({
            'success': True,
            'date': schedule_date.isoformat(),
            'employees': page_employees,
            'schedules': page_schedules,
            'absences': page_absences,
            'total_employees': total_employees,
            'page': current_page,
            'total_pages': total_pages,
            'has_prev': current_page > 0,
            'has_next': current_page < total_pages - 1
        })
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_multi_employee_schedule')
        raise AppError('Wystapil blad serwera')


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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_past_pending_appointments')
        raise AppError('Wystapil blad serwera')


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
            raise ValidationError('Brak statusu')

        # Walidacja: czy status jest finalny
        if new_status not in AppointmentStatus.FINAL:
            raise ValidationError(f'Dozwolone statusy: {", ".join(sorted(AppointmentStatus.FINAL))}')

        repo = AppointmentRepository()
        row = repo.get_by_id(appointment_id)

        if not row:
            raise NotFoundError('Wizyta nie istnieje')

        # Walidacja: czy wizyta jest przeszła
        from datetime import datetime
        appointment_datetime_str = f"{row['appointment_date']} {row['end_time']}"
        appointment_datetime = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()

        if appointment_datetime >= now:
            raise ValidationError('Mozna aktualizowac tylko wizyty ktore sie juz zakonczyly')

        # Walidacja: czy status już nie jest finalny
        if row['status'] in AppointmentStatus.FINAL:
            raise ValidationError(f'Wizyta ma juz finalny status: {row["status"]}')

        # Aktualizacja statusu bezpośrednio (omijamy transition_status), ale
        # przez serwis — 'completed' musi utworzyć rekord przychodu tak samo
        # jak przy edycji wizyty (patrz AppointmentBusinessService.resolve_past_status).
        old_status = row['status']
        cancellation_reason = data.get('cancellation_reason') if new_status == AppointmentStatus.CANCELLED else None
        success = AppointmentBusinessService().resolve_past_status(
            appointment_id, new_status, cancellation_reason
        )

        if success:
            appt_label = f"{row['appointment_date']} {row.get('start_time','')}"
            new_val = f"{new_status} ({cancellation_reason})" if cancellation_reason else new_status
            _audit('appointment', 'STATUS_CHANGE', entity_id=appointment_id,
                   entity_label=appt_label,
                   field_name='status',
                   old_value=old_status,
                   new_value=new_val)

            # Event-triggered SMS hooks
            if new_status == AppointmentStatus.COMPLETED:
                _schedule_post_visit_sms(appointment_id)
            elif new_status == AppointmentStatus.CANCELLED:
                _cancel_event_sms(appointment_id)

            return jsonify({'success': True, 'message': f'Status zaktualizowany na: {new_status}'})
        else:
            raise AppError('Nie udalo sie zaktualizowac statusu')

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in update_past_appointment_status')
        raise AppError('Wystapil blad serwera')


@appointment_bp.route('/appointments/status-events', methods=['GET'])
@login_required
def get_status_change_events():
    """5-second polling endpoint for real-time visit status toast notifications."""
    since_str = request.args.get('since', '')
    try:
        from datetime import datetime, timedelta, timezone
        since = datetime.fromisoformat(since_str) if since_str else \
                datetime.now(timezone.utc) - timedelta(seconds=10)
    except ValueError:
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(seconds=10)

    from repositories.appointments.status_change_event_repository import StatusChangeEventRepository
    from datetime import datetime, timezone
    events = StatusChangeEventRepository().get_since(since)
    # Serialize datetimes for JSON
    serialized = []
    for e in events:
        row = dict(e)
        for k, v in row.items():
            if hasattr(v, 'isoformat'):
                row[k] = v.isoformat()
        serialized.append(row)
    return jsonify({
        'events': serialized,
        'server_time': datetime.now(timezone.utc).isoformat(),
    })


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
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_client_appointments')
        raise AppError('Wystapil blad serwera')



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


@appointment_bp.route('/appointments/<int:appointment_id>/visit-link', methods=['GET'])
@login_required
def get_visit_link(appointment_id: int):
    """Return tokenized /visit/<token> URL for the employee owning this appointment.
    Time-gated: only available within 20 minutes of scheduled start."""
    from datetime import datetime, timedelta
    from repositories.employees.employee_repository import EmployeeRepository

    repo = AppointmentRepository()
    appt = repo.get_by_id(appointment_id)
    if not appt:
        return jsonify({'success': False, 'error': 'Wizyta nie istnieje'}), 404
    appt = dict(appt)

    # Verify the requesting user owns this appointment via employee record
    employee = EmployeeRepository().get_by_user_id(current_user.id)
    if not employee or employee['id'] != appt.get('employee_id'):
        return jsonify({'success': False, 'error': 'Brak dostępu do tej wizyty'}), 403

    # Time gate: only within 20 minutes of start (or already in progress)
    if appt.get('status') not in ('in_progress',):
        try:
            start_time = appt['start_time']
            h, m = str(start_time)[:5].split(':')
            appt_dt = datetime.combine(appt['appointment_date'],
                                       datetime.min.time().replace(hour=int(h), minute=int(m)))
            minutes_until = (appt_dt - datetime.now()).total_seconds() / 60
        except Exception:
            minutes_until = 9999

        if minutes_until > 20:
            return jsonify({
                'success': False,
                'too_early': True,
                'minutes_remaining': int(minutes_until - 20),
                'error': f'Link dostępny za {int(minutes_until - 20)} min',
            }), 425

    employee_token = appt.get('employee_token')
    if not employee_token:
        return jsonify({'success': False, 'error': 'Brak tokenu wizyty'}), 500

    base_url = current_app.config.get('BASE_URL', request.host_url.rstrip('/'))
    visit_url = f"{base_url}/visit/{employee_token}"
    return jsonify({'success': True, 'url': visit_url, 'appointment_id': appointment_id})


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
