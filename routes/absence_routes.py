"""
Routes zarządzania nieobecnościami pracowników.

GET  /my-absences                    — pracownik: własna lista + formularz wniosku
POST /my-absences/submit             — złóż wniosek
POST /my-absences/<id>/cancel        — anuluj własny wniosek

GET  /absences                       — przełożony: 3-tabowy widok zarządzania
POST /absences/<id>/approve          — zatwierdź (JSON; może zwrócić conflict)
POST /absences/<id>/approve/force    — zatwierdź z pominięciem konfliktów
POST /absences/<id>/reject           — odrzuć (JSON, wymaga rejection_reason)
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
        flash('Twoje konto użytkownika nie ma przypisanego pracownika.', 'error')
        return None
    return emp


def _svc():
    return AbsenceService()


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
        flash('Wniosek o nieobecność został złożony.', 'success')
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
        flash('Wniosek został anulowany.', 'success')
    except (AbsenceError, AppError) as e:
        flash(str(e), 'error')
    return redirect(url_for('absence.my_absences'))


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


@absence_bp.route('/absences/<int:absence_id>/approve', methods=['POST'])
@absence_management_required
def approve_request(absence_id: int):
    emp = get_linked_employee(current_user)
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        result = _svc().approve(absence_id, emp['id'])
        return jsonify({'success': True, **result})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/approve/force', methods=['POST'])
@absence_management_required
def force_approve(absence_id: int):
    emp = get_linked_employee(current_user)
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    try:
        _svc().force_approve(absence_id, emp['id'])
        return jsonify({'success': True, 'status': 'approved'})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/<int:absence_id>/reject', methods=['POST'])
@absence_management_required
def reject_request(absence_id: int):
    emp = get_linked_employee(current_user)
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    data = request.get_json(silent=True) or {}
    rejection_reason = data.get('rejection_reason', '').strip()
    try:
        _svc().reject(absence_id, emp['id'], rejection_reason)
        return jsonify({'success': True, 'status': 'rejected'})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@absence_bp.route('/absences/manual', methods=['POST'])
@absence_management_required
def create_manual():
    emp = get_linked_employee(current_user)
    if not emp:
        return jsonify({'success': False, 'error': 'Brak przypisanego pracownika'}), 403
    data = request.get_json(silent=True) or request.form
    try:
        employee_id = int(data['employee_id'])
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
            creator_employee_id=emp['id'],
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
        _svc().soft_delete(absence_id)
        return jsonify({'success': True})
    except (AbsenceError, AppError) as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ── categories (admin only) ───────────────────────────────────────────────────

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
    try:
        cat = AbsenceCategory(name=name, description=description, absence_full_day=full_day)
        new_id = current_app.absence_category_repo.create(cat)
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
    cat = AbsenceCategory(name=name, description=description, absence_full_day=full_day)
    updated = current_app.absence_category_repo.update(category_id, cat)
    if not updated:
        return jsonify({'success': False, 'error': 'Kategoria nie istnieje'}), 404
    return jsonify({'success': True})


@absence_bp.route('/absences/categories/<int:category_id>', methods=['DELETE'])
@module_permission_required('absences')
def delete_category(category_id: int):
    from flask import current_app
    deleted = current_app.absence_category_repo.soft_delete(category_id)
    if not deleted:
        return jsonify({'success': False, 'error': 'Kategoria nie istnieje lub już usunięta'}), 404
    return jsonify({'success': True})
