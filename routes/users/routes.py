"""
Zarządzanie użytkownikami — strony i API
Dostępne tylko dla: superuser, admin
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from config.auth_config import role_required
from repositories.users.user_repository import UserRepository
from repositories.roles.role_repository import RoleRepository

users_bp = Blueprint('users', __name__, url_prefix='/system/users')

ALLOWED_ROLES = ['superuser', 'admin']


def _user_repo() -> UserRepository:
    return UserRepository()


def _role_repo() -> RoleRepository:
    return RoleRepository()


# ─── Page Routes ─────────────────────────────────────────────────────────────

@users_bp.route('/')
@login_required
@role_required('superuser', 'admin')
def users_list():
    """Lista użytkowników"""
    return render_template('users/list.html')


@users_bp.route('/create')
@login_required
@role_required('superuser', 'admin')
def create_user():
    """Formularz tworzenia użytkownika"""
    user_repo = _user_repo()
    # Employees without user accounts + the currently linked one (if editing)
    available_employees = user_repo.get_available_employees()
    roles = _role_repo().get_all()
    # Superuser role only shown if current_user is superuser
    if current_user.role != 'superuser':
        roles = [r for r in roles if r['name'] != 'superuser']
    return render_template('users/create.html',
                           available_employees=available_employees,
                           roles=roles)


@users_bp.route('/<int:user_id>/edit')
@login_required
@role_required('superuser', 'admin')
def edit_user(user_id):
    """Formularz edycji użytkownika"""
    user_repo = _user_repo()
    row = user_repo.get_by_id(user_id)
    if not row:
        return render_template('errors/404.html'), 404

    user = user_repo.row_to_user(row)

    # Admin cannot edit superuser accounts
    if user.role == 'superuser' and current_user.role != 'superuser':
        flash('Brak uprawnień do edycji konta właściciela', 'error')
        return redirect(url_for('users.users_list'))

    linked_employee = user_repo.get_linked_employee(user_id)
    available_employees = user_repo.get_available_employees()

    roles = _role_repo().get_all()
    # Non-superusers cannot assign superuser role
    if current_user.role != 'superuser':
        roles = [r for r in roles if r['name'] != 'superuser']

    return render_template('users/edit.html',
                           user=user,
                           linked_employee=linked_employee,
                           available_employees=available_employees,
                           roles=roles)


# ─── API Endpoints ────────────────────────────────────────────────────────────

@users_bp.route('/api', methods=['GET'])
@login_required
@role_required('superuser', 'admin')
def api_list():
    """GET /system/users/api — lista wszystkich użytkowników"""
    user_repo = _user_repo()
    rows = user_repo.get_all_with_employee()
    users_data = []
    for row in rows:
        users_data.append({
            'id': row['id'],
            'email': row['email'],
            'full_name': row['full_name'],
            'role': row['role'],
            'is_active': bool(row['is_active']),
            'last_login': row['last_login'].isoformat() if row['last_login'] else None,
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'employee_id': row['employee_id'],
            'employee_name': f"{row['employee_first_name']} {row['employee_last_name']}"
                             if row['employee_id'] else None,
        })
    return jsonify({'users': users_data, 'count': len(users_data)})


@users_bp.route('/api', methods=['POST'])
@login_required
@role_required('superuser', 'admin')
def api_create():
    """POST /system/users/api — utwórz nowego użytkownika"""
    data = request.get_json() or {}

    email = (data.get('email') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    password = data.get('password') or ''
    role = (data.get('role') or '').strip()
    employee_id = data.get('employee_id')
    is_active = bool(data.get('is_active', True))

    # Validation
    if not email or not full_name or not password or not role:
        return jsonify({'error': 'Email, imię, hasło i rola są wymagane'}), 400

    if not employee_id:
        return jsonify({'error': 'Powiązanie z pracownikiem jest wymagane'}), 400

    # Non-superusers cannot create superuser accounts
    if role == 'superuser' and current_user.role != 'superuser':
        return jsonify({'error': 'Brak uprawnień do tworzenia konta właściciela'}), 403

    if len(password) < 8:
        return jsonify({'error': 'Hasło musi mieć co najmniej 8 znaków'}), 400

    user_repo = _user_repo()

    # Check email uniqueness
    if user_repo.get_by_email(email):
        return jsonify({'error': f'Użytkownik z adresem {email} już istnieje'}), 409

    try:
        user_id = user_repo.create_user(email=email, password=password,
                                        full_name=full_name, role=role)
        if employee_id:
            user_repo.link_employee(user_id, int(employee_id))

        # Log audit
        try:
            current_app.audit_repo.log_event(
                entity_type='user', action='CREATE',
                entity_id=user_id, entity_label=email,
                new_value=role,
                user_id=current_user.id, user_name=current_user.full_name,
            )
        except Exception:
            pass

        return jsonify({'success': True, 'user_id': user_id}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/<int:user_id>', methods=['PUT'])
@login_required
@role_required('superuser', 'admin')
def api_update(user_id):
    """PUT /system/users/api/<id> — zaktualizuj użytkownika"""
    user_repo = _user_repo()
    row = user_repo.get_by_id(user_id)
    if not row:
        return jsonify({'error': 'Użytkownik nie znaleziony'}), 404

    existing_user = user_repo.row_to_user(row)

    # Admin cannot edit superuser
    if existing_user.role == 'superuser' and current_user.role != 'superuser':
        return jsonify({'error': 'Brak uprawnień do edycji konta właściciela'}), 403

    data = request.get_json() or {}
    email = (data.get('email') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    role = (data.get('role') or '').strip()
    is_active = bool(data.get('is_active', True))
    employee_id = data.get('employee_id')
    new_password = data.get('new_password') or ''

    # Password-only update (from the separate password change form)
    if new_password and not email and not full_name and not role:
        if len(new_password) < 8:
            return jsonify({'error': 'Nowe hasło musi mieć co najmniej 8 znaków'}), 400
        try:
            user_repo.update_password(user_id, new_password)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    if not email or not full_name or not role:
        return jsonify({'error': 'Email, imię i rola są wymagane'}), 400

    # Non-superusers cannot assign superuser role
    if role == 'superuser' and current_user.role != 'superuser':
        return jsonify({'error': 'Brak uprawnień do nadania roli właściciela'}), 403

    # Check email uniqueness (excluding current user)
    existing_by_email = user_repo.get_by_email(email)
    if existing_by_email and existing_by_email.id != user_id:
        return jsonify({'error': f'Email {email} jest już zajęty'}), 409

    if new_password and len(new_password) < 8:
        return jsonify({'error': 'Nowe hasło musi mieć co najmniej 8 znaków'}), 400

    try:
        user_repo.update_user(user_id, email, full_name, role, is_active)

        if new_password:
            user_repo.update_password(user_id, new_password)

        # Handle employee link
        if employee_id:
            user_repo.link_employee(user_id, int(employee_id))

        try:
            current_app.audit_repo.log_event(
                entity_type='user', action='UPDATE',
                entity_id=user_id, entity_label=email,
                user_id=current_user.id, user_name=current_user.full_name,
            )
        except Exception:
            pass

        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/<int:user_id>/toggle-active', methods=['PUT'])
@login_required
@role_required('superuser', 'admin')
def api_toggle_active(user_id):
    """PUT /system/users/api/<id>/toggle-active — przełącz aktywność konta"""
    user_repo = _user_repo()
    row = user_repo.get_by_id(user_id)
    if not row:
        return jsonify({'error': 'Użytkownik nie znaleziony'}), 404

    existing = user_repo.row_to_user(row)
    if existing.role == 'superuser' and current_user.role != 'superuser':
        return jsonify({'error': 'Brak uprawnień'}), 403

    if existing.is_active:
        user_repo.deactivate(user_id)
        new_state = False
    else:
        user_repo.activate(user_id)
        new_state = True

    return jsonify({'success': True, 'is_active': new_state})
