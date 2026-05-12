"""
Routes zarządzania bilansem nieobecności.

GET  /absence-balances                           — strona zarządzania bilansami
GET  /api/absence-categories/tracked             — JSON: lista śledzonych kategorii (dla dropdownów)
GET  /api/absence-balances/summary               — JSON: podsumowanie dla listy pracowników
GET  /api/employees/<id>/absence-balances        — JSON: bilanse danego pracownika
POST /api/employees/<id>/absence-limits          — ustaw indywidualny limit
DELETE /api/employees/<id>/absence-limits/<lid>  — usuń limit
GET  /api/employees/<id>/absence-adjustments     — historia korekt
POST /api/employees/<id>/absence-adjustments     — utwórz korektę
DELETE /api/employees/<id>/absence-adjustments/<aid> — usuń korektę
GET  /api/employees/<id>/absence-balance-audit   — historia zmian (audit log)
"""
import logging

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from config.auth_config import absence_management_required, get_linked_employee
from services.absence_balance_service import AbsenceBalanceService

logger = logging.getLogger(__name__)

absence_balance_bp = Blueprint('absence_balance', __name__)


def _balance_svc() -> AbsenceBalanceService:
    return AbsenceBalanceService()


# ── HTML page ─────────────────────────────────────────────────────────────────

@absence_balance_bp.route('/absence-balances')
@absence_management_required
def balances_index():
    employees = current_app.employee_repo.get_all(active_only=True)
    tracked_categories = current_app.absence_category_repo.list_tracked()
    return render_template(
        'absences/balances.html',
        employees=employees,
        tracked_categories=tracked_categories,
    )


# ── JSON API ──────────────────────────────────────────────────────────────────

@absence_balance_bp.route('/api/absence-categories/tracked')
@absence_management_required
def tracked_categories_json():
    """Zwraca aktualne śledzone kategorie jako JSON (do dynamicznych dropdownów)."""
    try:
        rows = current_app.absence_category_repo.list_tracked()
        cats = [{'id': r['id'], 'name': r['name']} for r in rows]
        return jsonify({'success': True, 'categories': cats})
    except Exception as e:
        logger.exception('tracked_categories_json failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route('/api/absence-categories')
@absence_management_required
def all_categories_json():
    """Zwraca wszystkie aktywne kategorie jako JSON (do formularzy tworzenia nieobecności)."""
    try:
        rows = current_app.absence_category_repo.list_active()
        cats = [{'id': r['id'], 'name': r['name'],
                 'absence_full_day': bool(r['absence_full_day'])} for r in rows]
        return jsonify({'success': True, 'categories': cats})
    except Exception as e:
        logger.exception('all_categories_json failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route('/api/absence-balances/summary')
@absence_management_required
def balances_summary():
    """Podsumowanie bilansu dla wszystkich pracowników (do listy pracowników)."""
    try:
        summary = _balance_svc().get_balance_summary_for_list()
        return jsonify({'success': True, 'balances': summary})
    except Exception as e:
        logger.exception('balances_summary failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route('/api/employees/<int:employee_id>/absence-balances')
@login_required
def employee_balances(employee_id: int):
    """Bilanse konkretnego pracownika. Własne dane lub widok menedżerski."""
    emp = get_linked_employee(current_user)
    own_employee_id = emp['id'] if emp else None

    is_own = own_employee_id == employee_id
    is_manager = (
        current_user.role in ('superuser', 'admin')
        or current_app.supervisor_repo.is_supervisor(own_employee_id or -1)
    )
    if not is_own and not is_manager:
        return jsonify({'success': False, 'error': 'Brak uprawnień'}), 403

    try:
        balances = _balance_svc().get_all_balances_for_employee(employee_id)
        emp_row = current_app.employee_repo.get_by_id(employee_id)
        employee_name = (
            f"{emp_row['first_name']} {emp_row['last_name']}" if emp_row else ''
        )
        return jsonify({'success': True, 'balances': balances,
                        'employee_name': employee_name})
    except Exception as e:
        logger.exception('employee_balances failed')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── limits ────────────────────────────────────────────────────────────────────

@absence_balance_bp.route('/api/employees/<int:employee_id>/absence-limits',
                           methods=['POST'])
@absence_management_required
def set_employee_limit(employee_id: int):
    """Ustaw indywidualny limit dla pracownika."""
    data = request.get_json(silent=True) or {}
    try:
        category_id = int(data['category_id'])
        max_value = float(data['max_value'])
        notes = (data.get('notes') or '').strip() or None
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Nieprawidłowe dane: {e}'}), 400

    if max_value < 0:
        return jsonify({'success': False, 'error': 'Limit nie może być ujemny'}), 400

    try:
        emp_row = current_app.employee_repo.get_by_id(employee_id)
        cat_row = current_app.absence_category_repo.get_by_id(category_id)
        employee_name = (
            f"{emp_row['first_name']} {emp_row['last_name']}" if emp_row else str(employee_id)
        )
        category_name = cat_row['name'] if cat_row else str(category_id)

        svc = _balance_svc()
        limit_id = svc.set_limit(
            employee_id=employee_id,
            category_id=category_id,
            max_value=max_value,
            notes=notes,
            created_by=current_user.id,
            employee_name=employee_name,
            category_name=category_name,
        )
        return jsonify({'success': True, 'id': limit_id}), 201
    except Exception as e:
        logger.exception('set_employee_limit failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route(
    '/api/employees/<int:employee_id>/absence-limits/<int:limit_id>',
    methods=['DELETE'])
@absence_management_required
def delete_employee_limit(employee_id: int, limit_id: int):
    """Usuń indywidualny limit pracownika."""
    try:
        _balance_svc().remove_limit(
            limit_id=limit_id,
            user_id=current_user.id,
            user_name=current_user.full_name,
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.exception('delete_employee_limit failed')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── adjustments ───────────────────────────────────────────────────────────────

@absence_balance_bp.route('/api/employees/<int:employee_id>/absence-adjustments')
@absence_management_required
def list_employee_adjustments(employee_id: int):
    """Historia korekt bilansu dla pracownika."""
    try:
        rows = current_app.absence_adjustment_repo.list_for_employee(employee_id)
        adjustments = []
        for r in rows:
            adjustments.append({
                'id': r['id'],
                'category_name': r['category_name'],
                'delta_value': float(r['delta_value']),
                'reason': r['reason'],
                'period_label': r['period_label'],
                'created_at': r['created_at'].isoformat() if hasattr(r['created_at'], 'isoformat') else str(r['created_at']),
                'created_by_name': r['created_by_name'],
            })
        return jsonify({'success': True, 'adjustments': adjustments})
    except Exception as e:
        logger.exception('list_employee_adjustments failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route('/api/employees/<int:employee_id>/absence-adjustments',
                           methods=['POST'])
@absence_management_required
def create_employee_adjustment(employee_id: int):
    """Utwórz korektę bilansu."""
    data = request.get_json(silent=True) or {}
    try:
        category_id = int(data['category_id'])
        delta_value = float(data['delta_value'])
        reason = (data.get('reason') or '').strip()
        period_label = (data.get('period_label') or '').strip() or None
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Nieprawidłowe dane: {e}'}), 400

    if not reason:
        return jsonify({'success': False, 'error': 'Powód korekty jest wymagany'}), 400

    try:
        emp_row = current_app.employee_repo.get_by_id(employee_id)
        cat_row = current_app.absence_category_repo.get_by_id(category_id)
        employee_name = (
            f"{emp_row['first_name']} {emp_row['last_name']}" if emp_row else str(employee_id)
        )
        category_name = cat_row['name'] if cat_row else str(category_id)

        adj_id = _balance_svc().create_adjustment(
            employee_id=employee_id,
            category_id=category_id,
            delta_value=delta_value,
            reason=reason,
            period_label=period_label,
            created_by=current_user.id,
            employee_name=employee_name,
            category_name=category_name,
        )
        return jsonify({'success': True, 'id': adj_id}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.exception('create_employee_adjustment failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route(
    '/api/employees/<int:employee_id>/absence-adjustments/<int:adj_id>',
    methods=['DELETE'])
@absence_management_required
def delete_employee_adjustment(employee_id: int, adj_id: int):
    """Usuń korektę bilansu."""
    try:
        _balance_svc().delete_adjustment(
            adj_id=adj_id,
            user_id=current_user.id,
            user_name=current_user.full_name,
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.exception('delete_employee_adjustment failed')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── audit trail ───────────────────────────────────────────────────────────────

@absence_balance_bp.route('/api/employees/<int:employee_id>/absence-balance-audit')
@absence_management_required
def employee_balance_audit(employee_id: int):
    """Historia zmian limitów i korekt dla danego pracownika."""
    try:
        entries = current_app.audit_repo.get_for_employee_balance(employee_id)
        return jsonify({'success': True, 'entries': entries})
    except Exception as e:
        logger.exception('employee_balance_audit failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route(
    '/api/employees/<int:employee_id>/absence-balance-audit',
    methods=['DELETE'])
@absence_management_required
def clear_employee_balance_audit(employee_id: int):
    """Usuń historię zmian bilansów dla pracownika."""
    try:
        deleted = current_app.audit_repo.delete_for_employee_balance(employee_id)
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        logger.exception('clear_employee_balance_audit failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route('/api/absence-balance-audit/employees-with-history', methods=['GET'])
@login_required
def employees_with_balance_history():
    """Zwróć listę ID pracowników mających wpisy w historii bilansów."""
    try:
        ids = current_app.audit_repo.get_employee_ids_with_balance_history()
        return jsonify({'success': True, 'employee_ids': ids})
    except Exception as e:
        logger.exception('employees_with_balance_history failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@absence_balance_bp.route('/api/absence-balance/check', methods=['POST'])
@login_required
def check_absence_balance():
    """Sprawdź czy planowana nieobecność przekroczy limit bilansu."""
    data = request.get_json(silent=True) or {}
    try:
        employee_id = int(data['employee_id'])
        category_id = int(data['category_id'])
        date_from_str = data['date_from']
        date_to_str = data.get('date_to') or date_from_str
        time_from_str = data.get('time_from')
        time_to_str = data.get('time_to')
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': f'Nieprawidłowe dane: {e}'}), 400

    try:
        from datetime import date, datetime

        cat_row = current_app.absence_category_repo.get_by_id(category_id)
        if not cat_row or not bool(cat_row.get('is_tracked')):
            return jsonify({'success': True, 'check': {'ok': True, 'warning': False},
                            'will_exceed': False})

        if bool(cat_row['absence_full_day']):
            d_from = date.fromisoformat(date_from_str)
            d_to = date.fromisoformat(date_to_str)
            proposed_value = float((d_to - d_from).days + 1)
        else:
            if not time_from_str or not time_to_str:
                return jsonify({'success': True, 'check': {'ok': True, 'warning': False},
                                'will_exceed': False})
            t1 = datetime.strptime(time_from_str[:5], '%H:%M')
            t2 = datetime.strptime(time_to_str[:5], '%H:%M')
            proposed_value = (t2 - t1).seconds / 3600.0

        if proposed_value <= 0:
            return jsonify({'success': True, 'check': {'ok': True, 'warning': False},
                            'will_exceed': False})

        check = _balance_svc().check_before_submit(
            employee_id, category_id, proposed_value, 'manual'
        )

        will_exceed = False
        if check.get('warning') and check.get('balance') and check['balance'].get('has_limit'):
            bal = check['balance']
            will_exceed = (bal['net_used'] + proposed_value) > bal['limit']

        return jsonify({'success': True, 'check': check, 'will_exceed': will_exceed})
    except Exception as e:
        logger.exception('check_absence_balance failed')
        return jsonify({'success': False, 'error': str(e)}), 500
