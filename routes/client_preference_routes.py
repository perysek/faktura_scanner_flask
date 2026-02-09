"""
API routes for client preferences (preferred employee per service/category)
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.auth_config import module_permission_required
from database.models import ClientPreference
from repositories.clients.client_preference_repository import ClientPreferenceRepository

client_preference_bp = Blueprint('client_preferences', __name__)


@client_preference_bp.route('/clients/<int:client_id>/preferences', methods=['GET'])
@login_required
@module_permission_required('clients')
def get_preferences(client_id):
    """Pobierz preferencje klienta"""
    try:
        repo = ClientPreferenceRepository()
        rows = repo.get_preferences_for_client(client_id)
        preferences = [dict(row) for row in rows]

        return jsonify({'success': True, 'preferences': preferences, 'count': len(preferences)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@client_preference_bp.route('/clients/<int:client_id>/preferences', methods=['POST'])
@login_required
@module_permission_required('clients')
def create_preference(client_id):
    """Utwórz preferencję klienta"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        employee_id = data.get('preferred_employee_id')
        if not employee_id:
            return jsonify({'success': False, 'error': 'Brak preferred_employee_id'}), 400

        pref = ClientPreference(
            client_id=client_id,
            preferred_employee_id=int(employee_id),
            service_id=int(data['service_id']) if data.get('service_id') else None,
            service_category=data.get('service_category'),
            notes=data.get('notes')
        )

        repo = ClientPreferenceRepository()
        pref_id = repo.create(pref)
        return jsonify({'success': True, 'id': pref_id}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@client_preference_bp.route('/clients/<int:client_id>/preferences/<int:pref_id>', methods=['PUT'])
@login_required
@module_permission_required('clients')
def update_preference(client_id, pref_id):
    """Zaktualizuj preferencję klienta"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        employee_id = data.get('preferred_employee_id')
        if not employee_id:
            return jsonify({'success': False, 'error': 'Brak preferred_employee_id'}), 400

        repo = ClientPreferenceRepository()
        success = repo.update(pref_id, int(employee_id), data.get('notes'))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@client_preference_bp.route('/clients/<int:client_id>/preferences/<int:pref_id>', methods=['DELETE'])
@login_required
@module_permission_required('clients')
def delete_preference(client_id, pref_id):
    """Usuń preferencję klienta"""
    try:
        repo = ClientPreferenceRepository()
        success = repo.delete(pref_id)
        if not success:
            return jsonify({'success': False, 'error': 'Preferencja nie istnieje'}), 404
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@client_preference_bp.route('/clients/<int:client_id>/suggested-employee', methods=['GET'])
@login_required
@module_permission_required('clients')
def get_suggested_employee(client_id):
    """Pobierz sugerowanego pracownika dla klienta i usługi"""
    try:
        service_id = request.args.get('service_id', type=int)
        category = request.args.get('category')

        repo = ClientPreferenceRepository()
        result = repo.get_suggested_employee(client_id, service_id, category)

        if result:
            return jsonify({
                'success': True,
                'found': True,
                'employee_id': result['preferred_employee_id'],
                'employee_name': result['employee_name']
            })
        else:
            return jsonify({'success': True, 'found': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
