"""
Zarządzanie użytkownikami — strony i API
Dostępne tylko dla: superuser, admin
"""
import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from config.auth_config import role_required
from config.ui_messages import msg
from exceptions import AppError, ValidationError, NotFoundError, ConflictError, PermissionDeniedError
from repositories.users.user_repository import UserRepository
from repositories.roles.role_repository import RoleRepository, MODULE_DISPLAY_NAMES

users_bp = Blueprint('users', __name__, url_prefix='/system/users')

ALLOWED_ROLES = ['superuser', 'admin']


def _user_repo() -> UserRepository:
    return UserRepository()


def _role_repo() -> RoleRepository:
    return RoleRepository()


def _iso(value):
    return value.isoformat() if value else None


def _role_summary(role_name):
    """(display_name, permissions) for a role key. Falls back to the bare key when
    the role row no longer exists (users.role has no FK)."""
    role_repo = _role_repo()
    row = role_repo.get_by_name(role_name)
    if not row:
        return role_name, {}
    return row['display_name'], role_repo.get_permissions(row['id'])


def _audit_user(action, user_id, label, field_name=None, old_value=None, new_value=None):
    current_app.audit_repo.safe_log_event(
        entity_type='user', action=action,
        entity_id=user_id, entity_label=label,
        field_name=field_name, old_value=old_value, new_value=new_value,
        user_id=current_user.id, user_name=current_user.full_name,
    )


def _employee_label(emp) -> str:
    return f"{emp['first_name']} {emp['last_name']}"


def _employee_id_or_none(raw):
    """None for "no employee" (null / '' / 0), an int otherwise."""
    if raw is None or raw in ('', 0, '0'):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValidationError('Nieprawidłowy pracownik')


def _assert_employee_assignable(user_repo, employee_id, for_user_id=None):
    """The employee must exist and be free (or already this account's). Without this
    check `link_employee` would silently steal an employee from another account."""
    state = user_repo.get_employee_link_state(employee_id)
    if not state:
        raise NotFoundError('Pracownik nie znaleziony')
    if state['user_id'] is not None and state['user_id'] != for_user_id:
        raise ConflictError(f'{_employee_label(state)} ma już przypisane inne konto')
    return state


def _plan_employee_link(user_repo, user_id, data):
    """Validate an (un)link request BEFORE any write. Returns None when nothing
    changes, else (new_employee_id | None, old_label, new_label)."""
    if 'employee_id' not in data:
        return None
    new_id = _employee_id_or_none(data['employee_id'])
    current = user_repo.get_linked_employee(user_id)
    if new_id == (current['id'] if current else None):
        return None
    new_label = _employee_label(_assert_employee_assignable(user_repo, new_id, user_id)) if new_id else '(brak)'
    return new_id, (_employee_label(current) if current else '(brak)'), new_label


def _guard_last_superuser(user_repo, target, *, stays_superuser, stays_active):
    """Nobody may remove the last active superuser (deactivate, delete or demote)
    — the salon would have no one left who can manage accounts and roles."""
    if target.role == 'superuser' and target.is_active and not (stays_superuser and stays_active):
        if user_repo.count_active_superusers() <= 1:
            raise ConflictError('To ostatnie aktywne konto właściciela (superuser) — najpierw wyznacz innego.')


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
        flash(msg('users.edit.owner_denied'), 'error')
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

@users_bp.route('/api/form-options', methods=['GET'])
@login_required
@role_required('superuser', 'admin')
def api_form_options():
    """JSON sibling of create_user()/edit_user()'s dropdown-data assembly
    (react-migration) — available employees + assignable roles, filtered the
    same way (non-superusers never see the superuser role as an option)."""
    user_repo = _user_repo()
    role_repo = _role_repo()
    available_employees = user_repo.get_available_employees()
    roles = role_repo.get_all()
    if current_user.role != 'superuser':
        roles = [r for r in roles if r['name'] != 'superuser']
    return jsonify({
        'success': True,
        'available_employees': [{'id': e['id'], 'first_name': e['first_name'], 'last_name': e['last_name']} for e in available_employees],
        'roles': [{'name': r['name'], 'display_name': r['display_name'],
                   'permissions': role_repo.get_permissions(r['id'])} for r in roles],
        'module_display_names': MODULE_DISPLAY_NAMES,
    })


@users_bp.route('/api/<int:user_id>', methods=['GET'])
@login_required
@role_required('superuser', 'admin')
def api_get(user_id):
    """JSON sibling of edit_user()'s single-user data assembly — user +
    linked_employee, for the React edit-form pre-fill."""
    user_repo = _user_repo()
    row = user_repo.get_by_id(user_id)
    if not row:
        raise NotFoundError('Uzytkownik nie znaleziony')
    user = user_repo.row_to_user(row)
    if user.role == 'superuser' and current_user.role != 'superuser':
        raise PermissionDeniedError('Brak uprawnien do wyswietlenia konta wlasciciela')
    linked = user_repo.get_linked_employee(user_id)
    role_display_name, permissions = _role_summary(user.role)
    return jsonify({
        'success': True,
        'user': {
            'id': user.id, 'email': user.email, 'full_name': user.full_name,
            'role': user.role, 'is_active': user.is_active,
            'role_display_name': role_display_name,
            'last_login': _iso(user.last_login), 'created_at': _iso(user.created_at),
        },
        'linked_employee': {'id': linked['id'], 'first_name': linked['first_name'], 'last_name': linked['last_name']} if linked else None,
        'permissions': permissions,
        'module_display_names': MODULE_DISPLAY_NAMES,
    })


@users_bp.route('/api', methods=['GET'])
@login_required
@role_required('superuser', 'admin')
def api_list():
    """GET /system/users/api — lista wszystkich użytkowników"""
    try:
        user_repo = _user_repo()
        rows = user_repo.get_all_with_employee()
        users_data = []
        for row in rows:
            users_data.append({
                'id': row['id'],
                'email': row['email'],
                'full_name': row['full_name'],
                'role': row['role'],
                'role_display_name': row['role_display_name'] or row['role'],
                'is_active': bool(row['is_active']),
                'last_login': row['last_login'].isoformat() if row['last_login'] else None,
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'employee_id': row['employee_id'],
                'employee_name': f"{row['employee_first_name']} {row['employee_last_name']}"
                                 if row['employee_id'] else None,
            })
        return jsonify({'users': users_data, 'count': len(users_data)})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in api_list (users)')
        raise AppError('Wystapil blad serwera')


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
        raise ValidationError('Email, imie, haslo i rola sa wymagane')

    if not employee_id:
        raise ValidationError('Powiazanie z pracownikiem jest wymagane')

    # Non-superusers cannot create superuser accounts
    if role == 'superuser' and current_user.role != 'superuser':
        raise PermissionDeniedError('Brak uprawnien do tworzenia konta wlasciciela')

    if len(password) < 8:
        raise ValidationError('Haslo musi miec co najmniej 8 znakow')

    user_repo = _user_repo()

    # Check email uniqueness
    if user_repo.get_by_email(email):
        raise ConflictError(f'Uzytkownik z adresem {email} juz istnieje')

    # Validate the employee before anything is written.
    employee = _assert_employee_assignable(user_repo, _employee_id_or_none(employee_id))

    try:
        user_id = user_repo.create_user(email=email, password=password,
                                        full_name=full_name, role=role)
        user_repo.link_employee(user_id, employee['id'])

        # Log audit
        current_app.audit_repo.safe_log_event(
            entity_type='user', action='CREATE',
            entity_id=user_id, entity_label=email,
            new_value=role,
            user_id=current_user.id, user_name=current_user.full_name,
        )
        _audit_user('CREATE', user_id, email, 'pracownik', None, _employee_label(employee))

        return jsonify({'success': True, 'user_id': user_id}), 201
    except ValueError as e:
        raise ValidationError(str(e))
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in api_create (users)')
        raise AppError('Wystapil blad serwera')


@users_bp.route('/api/<int:user_id>', methods=['PUT'])
@login_required
@role_required('superuser', 'admin')
def api_update(user_id):
    """PUT /system/users/api/<id> — zaktualizuj użytkownika"""
    user_repo = _user_repo()
    row = user_repo.get_by_id(user_id)
    if not row:
        raise NotFoundError('Uzytkownik nie znaleziony')

    existing_user = user_repo.row_to_user(row)

    # Admin cannot edit superuser
    if existing_user.role == 'superuser' and current_user.role != 'superuser':
        raise PermissionDeniedError('Brak uprawnien do edycji konta wlasciciela')

    data = request.get_json() or {}
    email = (data.get('email') or '').strip()
    full_name = (data.get('full_name') or '').strip()
    role = (data.get('role') or '').strip()
    is_active = bool(data.get('is_active', True))
    new_password = data.get('new_password') or ''

    # Password-only update (from the separate password change form)
    if new_password and not email and not full_name and not role:
        if len(new_password) < 8:
            raise ValidationError('Nowe haslo musi miec co najmniej 8 znakow')
        try:
            user_repo.update_password(user_id, new_password)
            _audit_user('PASSWORD_RESET', user_id, existing_user.email, 'hasło', None, '(zmieniono przez administratora)')
            return jsonify({'success': True})
        except ValueError as e:
            raise ValidationError(str(e))
        except AppError:
            raise
        except Exception as e:
            logging.exception('Unexpected error in api_update password (users)')
            raise AppError('Wystapil blad serwera')

    if not email or not full_name or not role:
        raise ValidationError('Email, imie i rola sa wymagane')

    # Non-superusers cannot assign superuser role
    if role == 'superuser' and current_user.role != 'superuser':
        raise PermissionDeniedError('Brak uprawnien do nadania roli wlasciciela')

    # Nobody edits their own access: no self-demotion, no self-deactivation.
    if user_id == current_user.id:
        if role != existing_user.role:
            raise ValidationError('Nie możesz zmienić własnej roli')
        if existing_user.is_active and not is_active:
            raise ValidationError('Nie możesz dezaktywować własnego konta')
    _guard_last_superuser(user_repo, existing_user, stays_superuser=(role == 'superuser'), stays_active=is_active)

    # Check email uniqueness (excluding current user)
    existing_by_email = user_repo.get_by_email(email)
    if existing_by_email and existing_by_email.id != user_id:
        raise ConflictError(f'Email {email} jest juz zajety')

    if new_password and len(new_password) < 8:
        raise ValidationError('Nowe haslo musi miec co najmniej 8 znakow')

    # Everything that can be rejected is checked above / here — before the first write.
    link_plan = _plan_employee_link(user_repo, user_id, data)

    try:
        user_repo.update_user(user_id, email, full_name, role, is_active)

        if new_password:
            user_repo.update_password(user_id, new_password)
            _audit_user('PASSWORD_RESET', user_id, email, 'hasło', None, '(zmieniono przez administratora)')

        if link_plan:
            new_employee_id, old_label, new_label = link_plan
            if new_employee_id is None:
                user_repo.unlink_employee(user_id)
            else:
                user_repo.link_employee(user_id, new_employee_id)
            _audit_user('UPDATE', user_id, email, 'pracownik', old_label, new_label)

        # One audit row per field that actually changed (none for a no-op save).
        if full_name != existing_user.full_name:
            _audit_user('UPDATE', user_id, email, 'imię i nazwisko', existing_user.full_name, full_name)
        if email != existing_user.email:
            _audit_user('UPDATE', user_id, email, 'email', existing_user.email, email)
        if role != existing_user.role:
            _audit_user('UPDATE', user_id, email, 'rola', existing_user.role, role)
        if is_active != existing_user.is_active:
            _audit_user('STATUS_CHANGE', user_id, email, 'is_active',
                        'aktywne' if existing_user.is_active else 'nieaktywne',
                        'aktywne' if is_active else 'nieaktywne')

        return jsonify({'success': True})
    except ValueError as e:
        raise ValidationError(str(e))
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in api_update (users)')
        raise AppError('Wystapil blad serwera')


@users_bp.route('/api/<int:user_id>', methods=['DELETE'])
@login_required
@role_required('superuser', 'admin')
def api_delete(user_id):
    """DELETE /system/users/api/<id> — usuń użytkownika"""
    if user_id == current_user.id:
        raise ValidationError('Nie możesz usunąć własnego konta')

    user_repo = _user_repo()
    row = user_repo.get_by_id(user_id)
    if not row:
        raise NotFoundError('Uzytkownik nie znaleziony')

    existing = user_repo.row_to_user(row)
    if existing.role == 'superuser' and current_user.role != 'superuser':
        raise PermissionDeniedError('Brak uprawnien do usunięcia konta właściciela')
    _guard_last_superuser(user_repo, existing, stays_superuser=False, stays_active=False)

    try:
        deleted = user_repo.delete_user(user_id)
        if not deleted:
            raise NotFoundError('Uzytkownik nie znaleziony')
        current_app.audit_repo.safe_log_event(
            entity_type='user', action='DELETE',
            entity_id=user_id, entity_label=existing.email,
            user_id=current_user.id, user_name=current_user.full_name,
        )
        return jsonify({'success': True})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in api_delete (users)')
        raise AppError('Wystapil blad serwera')


@users_bp.route('/api/<int:user_id>/toggle-active', methods=['PUT'])
@login_required
@role_required('superuser', 'admin')
def api_toggle_active(user_id):
    """PUT /system/users/api/<id>/toggle-active — przełącz aktywność konta"""
    try:
        user_repo = _user_repo()
        row = user_repo.get_by_id(user_id)
        if not row:
            raise NotFoundError('Uzytkownik nie znaleziony')

        existing = user_repo.row_to_user(row)
        if existing.role == 'superuser' and current_user.role != 'superuser':
            raise PermissionDeniedError('Brak uprawnien')
        if user_id == current_user.id:
            raise ValidationError('Nie możesz dezaktywować własnego konta')
        _guard_last_superuser(user_repo, existing, stays_superuser=True, stays_active=not existing.is_active)

        if existing.is_active:
            user_repo.deactivate(user_id)
            new_state = False
        else:
            user_repo.activate(user_id)
            new_state = True

        current_app.audit_repo.safe_log_event(
            entity_type='user', action='STATUS_CHANGE',
            entity_id=user_id, entity_label=existing.email,
            field_name='is_active',
            old_value='aktywne' if existing.is_active else 'nieaktywne',
            new_value='aktywne' if new_state else 'nieaktywne',
            user_id=current_user.id, user_name=current_user.full_name,
        )
        return jsonify({'success': True, 'is_active': new_state})
    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in api_toggle_active (users)')
        raise AppError('Wystapil blad serwera')
