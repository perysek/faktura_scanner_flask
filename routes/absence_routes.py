"""
Routes zarządzania nieobecnościami pracowników.

GET  /my-absences                    — pracownik: własna lista + formularz wniosku
POST /my-absences/submit             — złóż wniosek
POST /my-absences/<id>/cancel        — anuluj własny wniosek (pending)
POST /my-absences/<id>/cancel-approved — anuluj własną zatwierdzoną nieobecność (zwalnia sloty)

GET  /absences                       — przełożony: 3-tabowy widok zarządzania
POST /absences/<id>/approve          — zatwierdź (JSON; może zwrócić conflict)
POST /absences/<id>/approve/force    — zatwierdź z pominięciem konfliktów
POST /absences/<id>/reject           — odrzuć (JSON, wymaga rejection_reason)
POST /absences/<id>/cancel-approved  — anuluj zatwierdzoną nieobecność (superuser; zwalnia sloty)
POST /absences/manual                — ręczna rejestracja nieobecności (L4)
PUT  /absences/<id>                  — edytuj manualną nieobecność
DELETE /absences/<id>               — soft delete

POST   /absences/categories          — utwórz kategorię (admin only)
PUT    /absences/categories/<id>     — edytuj kategorię (admin only)
DELETE /absences/categories/<id>    — usuń kategorię (admin only)
"""
import logging
from datetime import datetime, date, time

from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from config.auth_config import (
    module_permission_required,
    absence_management_required,
    get_linked_employee,
)
from database.models import AbsenceCategory
from exceptions import AppError
from repositories.audit_repository import AuditRepository
from services.absence_service import AbsenceService, AbsenceError

logger = logging.getLogger(__name__)

absence_bp = Blueprint('absence', __name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_date(s: str) -> date:
    if not s:
        raise AbsenceError("Brakująca data")
    try:
        y, m, d = s.split('-')
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        raise AbsenceError(f"Nieprawidłowy format daty: {s}")


def _parse_time_opt(s: str):
    """Parse HH:MM, return None if empty."""
    if not s or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), '%H:%M').time()
    except ValueError:
        raise AbsenceError(f"Nieprawidłowy format godziny: {s}")


def _get_employee_or_403():
    """Return the employee row for current_user, or abort with 403 flash."""
    emp = get_linked_employee(current_user)
    if not emp:
        flash('Twoje konto wisi w próżni — żaden pracownik do niego nie przypisany.', 'error')
        return None
    return emp


def _svc():
    return AbsenceService()


def _serialize_absence(a: dict) -> dict:
    """date/time/datetime fields → JSON-safe strings (react-migration JSON
    endpoints). The Jinja templates stringify these implicitly via `{{ }}`;
    jsonify() needs it done explicitly, same pattern as resolution_history()
    above."""
    out = dict(a)
    for key in ('date_from', 'date_to'):
        if out.get(key) is not None:
            out[key] = str(out[key])
    for key in ('time_from', 'time_to'):
        if out.get(key) is not None:
            out[key] = str(out[key])[:5]
    for key in ('requested_at', 'responded_at'):
        v = out.get(key)
        if v is not None and hasattr(v, 'isoformat'):
            out[key] = v.isoformat()
    return out


def _notify_reassigned_employee(appointment_id: int, new_employee_id: int) -> None:
    """Direct SMS to the newly-assigned employee about their new appointment —
    an internal staff notice, not a client-facing configurable template (see
    SmsService.notify_employee_direct). Never raises: a notification failure
    must not fail the reassignment that triggered it."""
    try:
        from repositories.appointments.appointment_repository import AppointmentRepository
        from repositories.clients.client_repository import ClientRepository
        from services.sms_service import SmsService

        appt = AppointmentRepository().get_by_id(appointment_id)
        if not appt:
            return
        client = ClientRepository().get_by_id(appt['client_id'])
        client_name = f"{client['first_name']} {client['last_name']}" if client else 'klient'
        start_time = str(appt['start_time'])[:5]
        appt_date = appt['appointment_date']
        date_fmt = appt_date.strftime('%d.%m.%Y') if hasattr(appt_date, 'strftime') else str(appt_date)

        body = (
            f"Zostałeś przypisany do wizyty: {client_name}, {date_fmt} godz. {start_time}. "
            f"Sprawdź grafik w systemie."
        )
        SmsService().notify_employee_direct(new_employee_id, body)
    except Exception:
        logger.exception('_notify_reassigned_employee failed appt_id=%s new_employee_id=%s',
                         appointment_id, new_employee_id)


def _send_absence_cancellation_sms(appointment_id: int) -> None:
    """Client-facing cancellation notice, sent through the ordinary SMS type
    machinery (type_key='absence_cancellation', seeded in Faza 0 — admin opts in
    from the SMS settings page like any other custom type). Mirrors
    _send_confirmation_request_sms's error-swallowing convention: a failed
    notice must never fail the cancellation itself."""
    try:
        from services.sms_service import SmsService
        from flask import current_app
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        SmsService().send(appointment_id, 'absence_cancellation', base_url=base_url)
    except Exception:
        logger.exception('_send_absence_cancellation_sms failed appt_id=%s', appointment_id)


# ── employee self-service ─────────────────────────────────────────────────────

@absence_bp.route('/my-absences')
@login_required
def my_absences():
    """Własna lista nieobecności + formularz wniosku (Phase 4 renders template)."""
    emp = _get_employee_or_403()
    if not emp:
        return redirect(url_for('main.dashboard'))

    svc = _svc()
    absences = svc.list_for_employee(emp['id'])

    from flask import current_app
    categories = current_app.absence_category_repo.list_active()
    supervisors = current_app.supervisor_repo.list_supervisors_for(emp['id'])

    return render_template(
        'absences/my.html',
        absences=absences,
        categories=categories,
        supervisors=supervisors,
        employee=emp,
    )


@absence_bp.route('/my-absences/preview-conflicts', methods=['GET'])
@login_required
def preview_conflicts():
    """Nieblokujący podgląd konfliktów z wizytami przed złożeniem wniosku (Faza 2).

    Zawsze rozwiązuje employee_id z zalogowanego użytkownika — nigdy z parametru
    żądania, żeby nie dało się podejrzeć konfliktów cudzego grafiku."""
    emp = get_linked_employee(current_user)
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        date_from = _parse_date(request.args.get('date_from'))
        date_to = _parse_date(request.args.get('date_to', request.args.get('date_from')))
        time_from = _parse_time_opt(request.args.get('time_from'))
        time_to = _parse_time_opt(request.args.get('time_to'))
        conflicts = _svc().preview_conflicts(emp['id'], date_from, date_to, time_from, time_to)
        return jsonify({'success': True, 'conflicts': conflicts})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/my-absences/submit', methods=['POST'])
@login_required
def submit_request():
    emp = _get_employee_or_403()
    if not emp:
        return redirect(url_for('main.dashboard'))

    try:
        category_id      = int(request.form['category_id'])
        date_from        = _parse_date(request.form.get('date_from'))
        date_to          = _parse_date(request.form.get('date_to', request.form.get('date_from')))
        time_from        = _parse_time_opt(request.form.get('time_from'))
        time_to          = _parse_time_opt(request.form.get('time_to'))
        approver_emp_id  = int(request.form['approver_id'])
        notes            = request.form.get('notes', '').strip() or None

        _svc().submit_request(
            employee_id=emp['id'],
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            approver_employee_id=approver_emp_id,
            notes=notes,
            created_by=current_user.id,
        )
        flash('Wniosek poszedł. Teraz czekaj i módl się o zatwierdzenie.', 'success')
    except (AbsenceError, AppError, ValueError, KeyError) as e:
        flash(str(e), 'error')

    return redirect(url_for('absence.my_absences'))


@absence_bp.route('/my-absences/<int:absence_id>/cancel', methods=['POST'])
@login_required
def cancel_own_request(absence_id: int):
    emp = _get_employee_or_403()
    if not emp:
        return redirect(url_for('main.dashboard'))
    try:
        _svc().cancel_own(absence_id, emp['id'])
        flash('Wniosek anulowany. Rozmyśliłeś się, bywa.', 'success')
    except (AbsenceError, AppError) as e:
        flash(str(e), 'error')
    return redirect(url_for('absence.my_absences'))


@absence_bp.route('/my-absences/<int:absence_id>/cancel-approved', methods=['POST'])
@login_required
def cancel_own_approved_request(absence_id: int):
    """Pracownik anuluje własną już zatwierdzoną nieobecność.

    Ownership wymuszany w serwisie. Zwalnia sloty pracownika w kalendarzu
    (status approved → cancelled).
    """
    emp = _get_employee_or_403()
    if not emp:
        return redirect(url_for('main.dashboard'))
    try:
        _svc().cancel_own_approved(absence_id, emp['id'], cancelled_by=current_user.id)
        flash('Nieobecność anulowana — sloty wróciły do kalendarza, jakby nigdy nic.', 'success')
    except (AbsenceError, AppError) as e:
        flash(str(e), 'error')
    return redirect(url_for('absence.my_absences'))


# ── employee self-service — JSON siblings (react-migration) ───────────────────
# Additive JSON versions of the three form-POST/redirect routes above, for the
# React /moje-nieobecnosci page. `templates/absences/my.html`'s own form posts
# stay untouched (plan.md §1: backend changes are additive, not replacements).

@absence_bp.route('/api/my-absences', methods=['GET'])
@login_required
def api_my_absences():
    emp = get_linked_employee(current_user)
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    from flask import current_app
    svc = _svc()
    absences = [_serialize_absence(a) for a in svc.list_for_employee(emp['id'])]
    categories = current_app.absence_category_repo.list_active()
    supervisors = current_app.supervisor_repo.list_supervisors_for(emp['id'])
    return jsonify({'success': True, 'absences': absences, 'categories': categories, 'supervisors': supervisors})


@absence_bp.route('/api/my-absences/submit', methods=['POST'])
@login_required
def api_submit_request():
    emp = _get_employee_or_403()
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    data = request.get_json(silent=True) or {}
    try:
        category_id = int(data['category_id'])
        date_from = _parse_date(data.get('date_from'))
        date_to = _parse_date(data.get('date_to', data.get('date_from')))
        time_from = _parse_time_opt(data.get('time_from'))
        time_to = _parse_time_opt(data.get('time_to'))
        approver_emp_id = int(data['approver_id'])
        notes = (data.get('notes') or '').strip() or None

        _svc().submit_request(
            employee_id=emp['id'],
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            approver_employee_id=approver_emp_id,
            notes=notes,
            created_by=current_user.id,
        )
        return jsonify({'success': True}), 201
    except (AbsenceError, AppError, ValueError, KeyError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/api/my-absences/<int:absence_id>/cancel', methods=['POST'])
@login_required
def api_cancel_own_request(absence_id: int):
    emp = _get_employee_or_403()
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        _svc().cancel_own(absence_id, emp['id'])
        return jsonify({'success': True})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/api/my-absences/<int:absence_id>/cancel-approved', methods=['POST'])
@login_required
def api_cancel_own_approved_request(absence_id: int):
    emp = _get_employee_or_403()
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        _svc().cancel_own_approved(absence_id, emp['id'], cancelled_by=current_user.id)
        return jsonify({'success': True})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ── supervisor management ─────────────────────────────────────────────────────

@absence_bp.route('/absences')
@absence_management_required
def management_index():
    """3-tabowy widok zarządzania nieobecnościami (Phase 4 renders full template)."""
    from flask import current_app
    emp = get_linked_employee(current_user)
    supervisor_emp_id = emp['id'] if emp else None

    svc = _svc()

    if current_user.role in ('superuser', 'admin'):
        requests_list = svc.list_all(status_in=['pending', 'approved', 'rejected', 'cancelled'])
        manual_list   = svc.list_all(status_in=['approved'], include_deleted=False)
    else:
        requests_list = svc.list_for_approver(supervisor_emp_id) if supervisor_emp_id else []
        manual_list   = svc.list_all(
            status_in=['approved'],
            employee_id=supervisor_emp_id,
        ) if supervisor_emp_id else []

    categories = current_app.absence_category_repo.list_with_deleted()
    pending_count = sum(1 for a in requests_list if a.get('status') == 'pending')

    return render_template(
        'absences/management.html',
        requests_list=requests_list,
        manual_list=manual_list,
        categories=categories,
        pending_count=pending_count,
        supervisor_emp_id=supervisor_emp_id,
    )


@absence_bp.route('/api/absences/management', methods=['GET'])
@absence_management_required
def api_management_index():
    """JSON sibling of management_index() for the React /nieobecnosci page —
    same data, same role branching, just returned instead of rendered."""
    from flask import current_app
    emp = get_linked_employee(current_user)
    supervisor_emp_id = emp['id'] if emp else None

    svc = _svc()
    if current_user.role in ('superuser', 'admin'):
        requests_list = svc.list_all(status_in=['pending', 'approved', 'rejected', 'cancelled'])
        manual_list = svc.list_all(status_in=['approved'], include_deleted=False)
    else:
        requests_list = svc.list_for_approver(supervisor_emp_id) if supervisor_emp_id else []
        manual_list = svc.list_all(status_in=['approved'], employee_id=supervisor_emp_id) if supervisor_emp_id else []

    categories = current_app.absence_category_repo.list_with_deleted()
    pending_count = sum(1 for a in requests_list if a.get('status') == 'pending')

    return jsonify({
        'success': True,
        'requests_list': [_serialize_absence(a) for a in requests_list],
        'manual_list': [_serialize_absence(a) for a in manual_list],
        'categories': categories,
        'pending_count': pending_count,
        'is_superuser': current_user.role == 'superuser',
    })


@absence_bp.route('/absences/<int:absence_id>/approve', methods=['POST'])
@absence_management_required
def approve_request(absence_id: int):
    emp = get_linked_employee(current_user)
    emp_id = emp['id'] if emp else None
    if emp_id is None and current_user.role not in ('superuser', 'admin'):
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        result = _svc().approve(absence_id, emp_id)
        return jsonify({'success': True, **result})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/approve/force', methods=['POST'])
@absence_management_required
def force_approve(absence_id: int):
    emp = get_linked_employee(current_user)
    emp_id = emp['id'] if emp else None
    if emp_id is None and current_user.role not in ('superuser', 'admin'):
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        _svc().force_approve(absence_id, emp_id)
        return jsonify({'success': True, 'status': 'approved'})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/reject', methods=['POST'])
@absence_management_required
def reject_request(absence_id: int):
    emp = get_linked_employee(current_user)
    emp_id = emp['id'] if emp else None
    if emp_id is None and current_user.role not in ('superuser', 'admin'):
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    data = request.get_json(silent=True) or {}
    rejection_reason = data.get('rejection_reason', '').strip()
    try:
        _svc().reject(absence_id, emp_id, rejection_reason)
        return jsonify({'success': True, 'status': 'rejected'})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/cancel-approved', methods=['POST'])
@absence_management_required
def cancel_approved_absence(absence_id: int):
    """Anuluj już zatwierdzoną nieobecność — wyłącznie superuser.

    Zwalnia sloty pracownika w kalendarzu (status approved → cancelled).
    `absence_management_required` wpuszcza też admina/przełożonych, więc
    zawężamy uprawnienie do superusera na poziomie serwera (a nie tylko UI).
    """
    if current_user.role != 'superuser':
        return jsonify({
            'success': False,
            'error': 'Tylko superuser może anulować zatwierdzone nieobecności',
        }), 403
    try:
        _svc().cancel_approved(absence_id, cancelled_by=current_user.id)
        return jsonify({'success': True, 'status': 'cancelled'})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/conflicts', methods=['GET'])
@absence_management_required
def live_conflicts(absence_id: int):
    """Żywy odczyt aktualnych konfliktów wniosku — re-fetched przez modal po
    każdej akcji rozwiązania konfliktu (Faza 3 / AD-8). Pusta lista = wszystko
    rozwiązane = przycisk 'Zatwierdź' może się odblokować."""
    try:
        conflicts = _svc().get_live_conflicts(absence_id)
        return jsonify({'success': True, 'conflicts': conflicts})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/resolutions', methods=['GET'])
@absence_management_required
def resolution_history(absence_id: int):
    """Historia rozwiązań konfliktów dla tego wniosku (Faza 3 — widok 'Historia
    rozwiązań' w modalu, tylko do odczytu)."""
    from repositories.absences.absence_conflict_resolution_repository import (
        AbsenceConflictResolutionRepository,
    )
    rows = AbsenceConflictResolutionRepository().list_for_absence(absence_id)
    resolutions = []
    for r in rows:
        resolutions.append({
            'id': r['id'],
            'resolution_type': r['resolution_type'],
            'client_name': r['client_name'],
            'service_name': r['service_name'],
            'previous_employee_name': r['previous_employee_name'],
            'new_employee_name': r['new_employee_name'],
            'previous_date': str(r['previous_date']) if r['previous_date'] else None,
            'previous_start_time': str(r['previous_start_time'])[:5] if r['previous_start_time'] else None,
            'previous_end_time': str(r['previous_end_time'])[:5] if r['previous_end_time'] else None,
            'new_date': str(r['new_date']) if r['new_date'] else None,
            'new_start_time': str(r['new_start_time'])[:5] if r['new_start_time'] else None,
            'new_end_time': str(r['new_end_time'])[:5] if r['new_end_time'] else None,
            'cancellation_reason': r['cancellation_reason'],
            'resolved_by_name': r['resolved_by_name'],
            'resolved_at': r['resolved_at'].strftime('%d.%m.%Y %H:%M') if r['resolved_at'] else None,
        })
    return jsonify({'success': True, 'resolutions': resolutions})


@absence_bp.route('/absences/manual', methods=['POST'])
@absence_management_required
def create_manual():
    emp = get_linked_employee(current_user)
    emp_id = emp['id'] if emp else None
    if emp_id is None and current_user.role not in ('superuser', 'admin'):
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    data = request.get_json(silent=True) or request.form
    try:
        employee_id = int(data['employee_id'])
        if employee_id == emp_id and current_user.role not in ('superuser', 'admin'):
            return jsonify({'success': False, 'error': 'Nie możesz tworzyć manualnej nieobecności dla siebie. Złóż wniosek przez "Moje nieobecności".'}), 403
        category_id = int(data['category_id'])
        date_from   = _parse_date(data.get('date_from'))
        date_to     = _parse_date(data.get('date_to', data.get('date_from')))
        time_from   = _parse_time_opt(data.get('time_from'))
        time_to     = _parse_time_opt(data.get('time_to'))
        notes       = (data.get('notes') or '').strip() or None

        result = _svc().create_manual(
            employee_id=employee_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            notes=notes,
            creator_employee_id=emp_id,
            created_by=current_user.id,
        )
        return jsonify({'success': True, **result})
    except (AbsenceError, AppError, ValueError, KeyError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>', methods=['PUT'])
@absence_management_required
def update_absence(absence_id: int):
    data = request.get_json(silent=True) or {}
    try:
        result = _svc().update_manual(
            absence_id=absence_id,
            category_id=int(data['category_id']),
            date_from=_parse_date(data.get('date_from')),
            date_to=_parse_date(data.get('date_to', data.get('date_from'))),
            time_from=_parse_time_opt(data.get('time_from')),
            time_to=_parse_time_opt(data.get('time_to')),
            notes=(data.get('notes') or '').strip() or None,
        )
        return jsonify({'success': True, **result})
    except (AbsenceError, AppError, ValueError, KeyError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>', methods=['DELETE'])
@absence_management_required
def delete_absence(absence_id: int):
    try:
        _svc().soft_delete(absence_id, deleted_by=current_user.id)
        return jsonify({'success': True})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/permanent', methods=['DELETE'])
@absence_management_required
def hard_delete_absence(absence_id: int):
    """Trwale usuń nieobecność — wyłącznie superuser (czyszczenie danych testowych).

    Fizycznie usuwa rekord employee_absences (nie soft-delete) niezależnie od
    statusu. Dla zatwierdzonej nieobecności zwalnia sloty w kalendarzu (kalendarz
    czyta tylko status='approved'). `absence_management_required` wpuszcza też
    admina/przełożonych, więc zawężamy do superusera na poziomie serwera.
    """
    if current_user.role != 'superuser':
        return jsonify({
            'success': False,
            'error': 'Tylko superuser może trwale usuwać nieobecności',
        }), 403
    try:
        result = _svc().hard_delete(absence_id, deleted_by=current_user.id)
        return jsonify({'success': True, **result})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ── categories (admin only) ───────────────────────────────────────────────────

def _parse_category_balance_fields(data: dict) -> dict:
    """Wyciągnij pola balance-tracking z danych żądania."""
    def _bool(key, default=False):
        v = data.get(key, default)
        if isinstance(v, bool):
            return v
        return str(v).lower() in ('true', '1', 'yes')

    def _float(key, default=0.0):
        try:
            return float(data.get(key, default))
        except (ValueError, TypeError):
            return default

    def _int_opt(key):
        v = data.get(key)
        if v is None or v == '':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    return {
        'is_tracked': _bool('is_tracked', False),
        'count_period': data.get('count_period', 'yearly') or 'yearly',
        'resets_at': _int_opt('resets_at'),
        'rolling_days': _int_opt('rolling_days'),
        'warning_threshold_pct': _float('warning_threshold_pct', 0.80),
        'default_max_value': _float('default_max_value', 0.0),
    }


@absence_bp.route('/absences/categories', methods=['POST'])
@module_permission_required('absences')
def create_category():
    from flask import current_app
    data = request.get_json(silent=True) or request.form
    name        = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip() or None
    full_day    = str(data.get('absence_full_day', 'true')).lower() in ('true', '1', 'yes')
    if not name:
        return jsonify({'success': False, 'error': 'Nazwa kategorii jest wymagana'}), 400
    bf = _parse_category_balance_fields(data)
    try:
        cat = AbsenceCategory(
            name=name, description=description, absence_full_day=full_day,
            **bf,
        )
        new_id = current_app.absence_category_repo.create(cat)
        AuditRepository().log_event(
            entity_type='absence_category',
            action='CREATE',
            entity_id=new_id,
            entity_label=name,
            user_id=current_user.id,
            user_name=current_user.full_name,
        )
        return jsonify({'success': True, 'id': new_id}), 201
    except Exception as e:
        logger.exception('create_category failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_bp.route('/absences/categories/<int:category_id>', methods=['PUT'])
@module_permission_required('absences')
def update_category(category_id: int):
    from flask import current_app
    data        = request.get_json(silent=True) or {}
    name        = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip() or None
    full_day    = str(data.get('absence_full_day', 'true')).lower() in ('true', '1', 'yes')
    if not name:
        return jsonify({'success': False, 'error': 'Nazwa kategorii jest wymagana'}), 400
    bf = _parse_category_balance_fields(data)
    cat = AbsenceCategory(name=name, description=description, absence_full_day=full_day, **bf)
    updated = current_app.absence_category_repo.update(category_id, cat)
    if not updated:
        return jsonify({'success': False, 'error': 'Kategoria nie istnieje'}), 404
    AuditRepository().log_event(
        entity_type='absence_category',
        action='UPDATE',
        entity_id=category_id,
        entity_label=name,
        user_id=current_user.id,
        user_name=current_user.full_name,
    )
    return jsonify({'success': True})


@absence_bp.route('/absences/categories/<int:category_id>', methods=['DELETE'])
@module_permission_required('absences')
def delete_category(category_id: int):
    from flask import current_app
    deleted = current_app.absence_category_repo.soft_delete(category_id)
    if not deleted:
        return jsonify({'success': False, 'error': 'Kategoria nie istnieje lub już usunięta'}), 404
    AuditRepository().log_event(
        entity_type='absence_category',
        action='DELETE',
        entity_id=category_id,
        entity_label=str(category_id),
        field_name='is_deleted',
        old_value='false',
        new_value='true',
        user_id=current_user.id,
        user_name=current_user.full_name,
    )
    return jsonify({'success': True})


@absence_bp.route('/absences/categories/<int:category_id>/permanent', methods=['DELETE'])
@module_permission_required('absences')
def hard_delete_category(category_id: int):
    """Trwale usuń (wyczyść) kategorię nieobecności — wyłącznie superuser.

    Dozwolone tylko dla kategorii już oznaczonej jako usunięta i niepowiązanej z
    żadną nieobecnością (FK RESTRICT z employee_absences). Konfiguracja i historia
    bilansu są kasowane kaskadowo. `module_permission_required('absences')` wpuszcza
    też admina, więc zawężamy do superusera na poziomie serwera.
    """
    if current_user.role != 'superuser':
        return jsonify({
            'success': False,
            'error': 'Tylko superuser może trwale usuwać kategorie',
        }), 403
    try:
        _svc().hard_delete_category(category_id, deleted_by=current_user.id)
        return jsonify({'success': True})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400
