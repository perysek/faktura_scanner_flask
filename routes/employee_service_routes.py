"""
API routes for employee-service assignments (per-employee pricing)
"""
import logging
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.auth_config import module_permission_required
from database.models import EmployeeService
from exceptions import AppError, ValidationError, NotFoundError
from repositories.employees.employee_service_repository import EmployeeServiceRepository

employee_service_bp = Blueprint('employee_services', __name__)


@employee_service_bp.route('/employees/<int:employee_id>/services', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employee_services(employee_id):
    """Pobierz usługi przypisane do pracownika z efektywnym cenowaniem"""
    try:
        repo = EmployeeServiceRepository()
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        rows = repo.get_services_for_employee(employee_id, active_only)

        services = []
        for row in rows:
            svc = dict(row)
            # Convert Decimal fields for JSON
            for key in ['custom_price', 'commission_rate', 'default_price',
                        'effective_price', 'effective_commission', 'employee_default_commission']:
                if svc.get(key) is not None:
                    svc[key] = float(svc[key])
            services.append(svc)

        return jsonify({'success': True, 'services': services, 'count': len(services)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_employee_services')
        raise AppError('Wystapil blad serwera')


@employee_service_bp.route('/employees/<int:employee_id>/services', methods=['POST'])
@login_required
@module_permission_required('employees')
def assign_service(employee_id):
    """Przypisz usługę do pracownika"""
    try:
        data = request.get_json()
        if not data:
            raise ValidationError('Brak danych')

        # Bulk assign
        if 'service_ids' in data:
            repo = EmployeeServiceRepository()
            count = repo.bulk_assign_services(employee_id, [int(sid) for sid in data['service_ids']])
            return jsonify({'success': True, 'assigned_count': count}), 201

        # Single assign with optional pricing
        service_id = data.get('service_id')
        if not service_id:
            raise ValidationError('Brak service_id')

        es = EmployeeService(
            employee_id=employee_id,
            service_id=int(service_id),
            custom_price=Decimal(str(data['custom_price'])) if data.get('custom_price') is not None else None,
            commission_rate=Decimal(str(data['commission_rate'])) if data.get('commission_rate') is not None else None,
            duration_override=int(data['duration_override']) if data.get('duration_override') is not None else None
        )

        repo = EmployeeServiceRepository()
        es_id = repo.create(es)
        return jsonify({'success': True, 'id': es_id}), 201
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in assign_service')
        raise AppError('Wystapil blad serwera')


@employee_service_bp.route('/employees/<int:employee_id>/services/<int:es_id>', methods=['PUT'])
@login_required
@module_permission_required('employees')
def update_employee_service(employee_id, es_id):
    """Zaktualizuj cenowanie/ocenę usługi dla pracownika"""
    try:
        data = request.get_json()
        if not data:
            raise ValidationError('Brak danych')

        skill_rating = None
        if 'skill_rating' in data:
            sr = data['skill_rating']
            if sr is not None:
                if not isinstance(sr, int) or not (1 <= sr <= 5):
                    raise ValidationError('skill_rating musi byc liczba 1-5')
                skill_rating = sr

        repo = EmployeeServiceRepository()
        success = repo.update(
            es_id,
            custom_price=Decimal(str(data['custom_price'])) if 'custom_price' in data else None,
            commission_rate=Decimal(str(data['commission_rate'])) if 'commission_rate' in data else None,
            duration_override=int(data['duration_override']) if 'duration_override' in data else None,
            skill_rating=skill_rating,
            is_active=data.get('is_active')
        )
        return jsonify({'success': success})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in update_employee_service')
        raise AppError('Wystapil blad serwera')


@employee_service_bp.route('/employees/<int:employee_id>/services-with-ratings', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_services_with_ratings(employee_id):
    """Pobierz przypisane usługi z oceną manualną i wyliczoną z wizyt klientów"""
    try:
        repo = EmployeeServiceRepository()
        services = repo.get_services_with_dual_ratings(employee_id)
        return jsonify({'success': True, 'services': services, 'count': len(services)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_services_with_ratings')
        raise AppError('Wystapil blad serwera')


@employee_service_bp.route('/employees/<int:employee_id>/services/<int:es_id>', methods=['DELETE'])
@login_required
@module_permission_required('employees')
def remove_employee_service(employee_id, es_id):
    """Usuń przypisanie usługi od pracownika"""
    try:
        repo = EmployeeServiceRepository()
        success = repo.delete(es_id)
        if not success:
            raise NotFoundError('Przypisanie nie istnieje')
        return jsonify({'success': True})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in remove_employee_service')
        raise AppError('Wystapil blad serwera')


@employee_service_bp.route('/employees/<int:employee_id>/analytics', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employee_analytics(employee_id):
    """Pobierz metryki wydajności pracownika"""
    try:
        # Widok administratora: the owner's employee is non-existent (404) while
        # admin view is OFF, so this analytics endpoint can't reveal their metrics.
        from config.admin_view import is_employee_hidden
        if is_employee_hidden(employee_id):
            raise NotFoundError('Pracownik nie istnieje')
        from repositories.analytics.analytics_repository import AnalyticsRepository
        repo = AnalyticsRepository()
        data = repo.get_employee_analytics(employee_id)
        return jsonify({'success': True, **data})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_employee_analytics')
        raise AppError('Wystapil blad serwera')


@employee_service_bp.route('/services/<int:service_id>/employees', methods=['GET'])
@login_required
@module_permission_required('services')
def get_service_employees(service_id):
    """Pobierz pracowników mogących wykonać daną usługę"""
    try:
        repo = EmployeeServiceRepository()
        rows = repo.get_employees_for_service(service_id)

        employees = []
        for row in rows:
            emp = dict(row)
            for key in ['custom_price', 'commission_rate', 'default_price',
                        'effective_price', 'effective_commission', 'employee_default_commission']:
                if emp.get(key) is not None:
                    emp[key] = float(emp[key])
            employees.append(emp)

        return jsonify({'success': True, 'employees': employees, 'count': len(employees)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_service_employees')
        raise AppError('Wystapil blad serwera')
