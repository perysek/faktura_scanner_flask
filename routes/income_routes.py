"""
API routes for income records and financial reporting
"""
import logging
from datetime import date
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.auth_config import module_permission_required
from exceptions import AppError, ValidationError
from repositories.appointments.income_repository import IncomeRepository

income_bp = Blueprint('income', __name__)


def _decimal_to_float(obj):
    """Convert Decimal values in dict to float for JSON serialization"""
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


@income_bp.route('/income', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_income_records():
    """Pobierz rekordy przychodu z opcjonalnym filtrowaniem"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        employee_id = request.args.get('employee_id', type=int)

        if not start_date or not end_date:
            # Domyślnie bieżący miesiąc
            today = date.today()
            start_date = today.replace(day=1)
            end_date = today
        else:
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        repo = IncomeRepository()
        rows = repo.get_by_date_range(start_date, end_date, employee_id)

        records = [_decimal_to_float(dict(row)) for row in rows]
        return jsonify({'success': True, 'records': records, 'count': len(records)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_income_records')
        raise AppError('Wystapil blad serwera')


LOST_KINDS = ('client_cancel', 'no_show', 'salon_cancel')
MAX_LEDGER_DAYS = 3 * 366


def _parse_iso(value, field):
    from datetime import datetime
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError(f'Nieprawidłowa data: {field}')


def _ledger_stats(records, lost_rows):
    """Karty statystyk strony Przychody — liczone z tych samych wierszy, które
    trafiają do tabeli, więc karta i stopka tabeli nigdy się nie rozjadą."""
    count = len(records)
    total_gross = sum(r['gross_amount'] for r in records)
    total_net = sum(r['net_amount'] for r in records)
    new_gross = sum(r['gross_amount'] for r in records if r['is_new_client'])

    lost = {k: {'visits': 0, 'amount': 0.0} for k in LOST_KINDS}
    for row in lost_rows:
        if row['kind'] in lost:
            lost[row['kind']] = {'visits': int(row['visits']), 'amount': float(row['amount'])}

    return {
        'count': count,
        'total_gross': round(total_gross, 2),
        'total_net': round(total_net, 2),
        'avg_gross': round(total_gross / count, 2) if count else 0.0,
        'new_client_gross': round(new_gross, 2),
        'new_client_visits': sum(1 for r in records if r['is_new_client']),
        'new_client_pct': round(new_gross * 100 / total_gross, 1) if total_gross else 0.0,
        'lost': {
            **lost,
            'visits': sum(v['visits'] for v in lost.values()),
            'amount': round(sum(v['amount'] for v in lost.values()), 2),
        },
    }


@income_bp.route('/income/ledger', methods=['GET'])
@login_required
@module_permission_required('income')
def get_income_ledger():
    """Strona "Przychody": rekordy przychodu z okresu (wg daty wpływu) + statystyki."""
    try:
        start_date = _parse_iso(request.args.get('start_date'), 'start_date')
        end_date = _parse_iso(request.args.get('end_date'), 'end_date')
        if start_date > end_date:
            raise ValidationError('Data początkowa musi być wcześniejsza niż końcowa')
        if (end_date - start_date).days > MAX_LEDGER_DAYS:
            raise ValidationError('Zakres dat nie może przekraczać 3 lat')

        repo = IncomeRepository()
        records = []
        for row in repo.get_ledger(start_date, end_date):
            rec = _decimal_to_float(dict(row))
            rec['payment_date'] = str(rec['payment_date'])[:10]
            rec['appointment_date'] = str(rec['appointment_date'])[:10]
            rec['is_new_client'] = bool(rec['is_new_client'])
            records.append(rec)

        return jsonify({
            'success': True,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'records': records,
            'stats': _ledger_stats(records, repo.get_lost_summary(start_date, end_date)),
        })
    except AppError:
        raise
    except Exception:
        logging.exception('Unexpected error in get_income_ledger')
        raise AppError('Wystapil blad serwera')


@income_bp.route('/income/summary', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_income_summary():
    """Pobierz podsumowanie przychodów za miesiąc"""
    try:
        year = request.args.get('year', date.today().year, type=int)
        month = request.args.get('month', date.today().month, type=int)

        repo = IncomeRepository()
        summary = repo.get_monthly_summary(year, month)
        employee_summary = repo.get_employee_summary(year, month)

        return jsonify({
            'success': True,
            'summary': _decimal_to_float(summary),
            'by_employee': [_decimal_to_float(dict(row)) for row in employee_summary],
            'year': year,
            'month': month
        })
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_income_summary')
        raise AppError('Wystapil blad serwera')


@income_bp.route('/income/employee/<int:employee_id>', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_income(employee_id):
    """Pobierz przychody pracownika za miesiąc"""
    try:
        year = request.args.get('year', date.today().year, type=int)
        month = request.args.get('month', date.today().month, type=int)

        repo = IncomeRepository()
        rows = repo.get_by_employee(employee_id, year, month)

        records = [_decimal_to_float(dict(row)) for row in rows]
        return jsonify({'success': True, 'records': records, 'count': len(records)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_employee_income')
        raise AppError('Wystapil blad serwera')
