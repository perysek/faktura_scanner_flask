"""
API routes for service addon compatibility management
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.auth_config import module_permission_required
from repositories.services.service_addon_repository import ServiceAddonRepository
from repositories.services.service_repository import ServiceRepository

service_addon_bp = Blueprint('service_addons', __name__)


@service_addon_bp.route('/services/<int:service_id>/compatible-addons', methods=['GET'])
@login_required
@module_permission_required('services')
def get_compatible_addons(service_id):
    """Pobierz mikrousługi kompatybilne z daną usługą główną"""
    try:
        repo = ServiceAddonRepository()
        rows = repo.get_compatible_addons(service_id)
        addons = [dict(row) for row in rows]

        return jsonify({'success': True, 'addons': addons, 'count': len(addons)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@service_addon_bp.route('/services/<int:service_id>/compatible-mains', methods=['GET'])
@login_required
@module_permission_required('services')
def get_compatible_mains(service_id):
    """Pobierz usługi główne kompatybilne z daną mikrousługą"""
    try:
        repo = ServiceAddonRepository()
        rows = repo.get_compatible_mains(service_id)
        mains = [dict(row) for row in rows]

        return jsonify({'success': True, 'main_services': mains, 'count': len(mains)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@service_addon_bp.route('/services/<int:service_id>/compatibility', methods=['PUT'])
@login_required
@module_permission_required('services')
def set_compatibility(service_id):
    """Ustaw reguły kompatybilności mikrousługi z usługami głównymi.

    Body: {"main_service_ids": [1, 2, 3]}
    Pusta lista = kompatybilna ze wszystkimi.
    """
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'Brak danych'}), 400

        main_service_ids = data.get('main_service_ids', [])

        repo = ServiceAddonRepository()
        repo.bulk_set_compatibility(service_id, [int(sid) for sid in main_service_ids])

        return jsonify({
            'success': True,
            'addon_service_id': service_id,
            'compatible_with': len(main_service_ids),
            'universal': len(main_service_ids) == 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@service_addon_bp.route('/services/<int:service_id>/addon-rules', methods=['GET'])
@login_required
@module_permission_required('services')
def get_addon_rules(service_id):
    """Pobierz aktualne reguły kompatybilności mikrousługi"""
    try:
        repo = ServiceAddonRepository()
        has_rules = repo.has_compatibility_rules(service_id)
        rules = repo.get_all_for_addon(service_id)

        return jsonify({
            'success': True,
            'has_rules': has_rules,
            'universal': not has_rules,
            'rules': [dict(r) for r in rules]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@service_addon_bp.route('/services/addons', methods=['GET'])
@login_required
@module_permission_required('services')
def get_all_addon_services():
    """Pobierz wszystkie mikrousługi"""
    try:
        repo = ServiceRepository()
        rows = repo.get_addon_services()
        addons = [dict(row) for row in rows]

        return jsonify({'success': True, 'addons': addons, 'count': len(addons)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@service_addon_bp.route('/services/main', methods=['GET'])
@login_required
@module_permission_required('services')
def get_all_main_services():
    """Pobierz wszystkie usługi główne"""
    try:
        repo = ServiceRepository()
        rows = repo.get_main_services()
        services = [dict(row) for row in rows]

        return jsonify({'success': True, 'services': services, 'count': len(services)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
