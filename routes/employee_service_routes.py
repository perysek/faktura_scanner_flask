"""
API routes for employee-service assignments (per-employee pricing)
"""
from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.auth_config import module_permission_required
from database.models import EmployeeService
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
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@employee_service_bp.route('/employees/<int:employee_id>/services', methods=['POST'])
@login_required
@module_permission_required('employees')
def assign_service(employee_id):
    """Przypisz usługę do pracownika"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        # Bulk assign
        if 'service_ids' in data:
            repo = EmployeeServiceRepository()
            count = repo.bulk_assign_services(employee_id, [int(sid) for sid in data['service_ids']])
            return jsonify({'success': True, 'assigned_count': count}), 201

        # Single assign with optional pricing
        service_id = data.get('service_id')
        if not service_id:
            return jsonify({'success': False, 'error': 'Brak service_id'}), 400

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
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@employee_service_bp.route('/employees/<int:employee_id>/services/<int:es_id>', methods=['PUT'])
@login_required
@module_permission_required('employees')
def update_employee_service(employee_id, es_id):
    """Zaktualizuj cenowanie usługi dla pracownika"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        repo = EmployeeServiceRepository()
        success = repo.update(
            es_id,
            custom_price=Decimal(str(data['custom_price'])) if 'custom_price' in data else None,
            commission_rate=Decimal(str(data['commission_rate'])) if 'commission_rate' in data else None,
            duration_override=int(data['duration_override']) if 'duration_override' in data else None,
            is_active=data.get('is_active')
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@employee_service_bp.route('/employees/<int:employee_id>/services/<int:es_id>', methods=['DELETE'])
@login_required
@module_permission_required('employees')
def remove_employee_service(employee_id, es_id):
    """Usuń przypisanie usługi od pracownika"""
    try:
        repo = EmployeeServiceRepository()
        success = repo.delete(es_id)
        if not success:
            return jsonify({'success': False, 'error': 'Przypisanie nie istnieje'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@employee_service_bp.route('/employees/<int:employee_id>/analytics', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employee_analytics(employee_id):
    """Pobierz metryki wydajności pracownika"""
    try:
        from repositories.analytics.analytics_repository import AnalyticsRepository
        repo = AnalyticsRepository()
        data = repo.get_employee_analytics(employee_id)
        return jsonify({'success': True, **data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
