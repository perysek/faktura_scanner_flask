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
