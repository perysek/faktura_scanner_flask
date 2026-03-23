"""
Konfiguracja autentykacji i autoryzacji
Role-based access control (RBAC) configuration
"""
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

# Role hierarchy (higher number = more permissions)
ROLE_HIERARCHY = {
    'superuser': 5,
    'admin': 4,
    'receptionist': 3,
    'stylist': 2,
    'accountant': 1,
}

# Module permissions - which roles can access which modules
MODULE_PERMISSIONS = {
    'invoices': ['superuser', 'admin', 'accountant'],
    'appointments': ['superuser', 'admin', 'receptionist', 'stylist'],
    'clients': ['superuser', 'admin', 'receptionist', 'stylist'],
    'employees': ['superuser', 'admin'],
    'services': ['superuser', 'admin'],
    'settings': ['superuser', 'admin'],
    'reports': ['superuser', 'admin', 'accountant'],
    'data_correction': ['superuser'],
}

def role_required(*roles):
    """
    Decorator to require specific roles for a route

    Usage:
        @role_required('admin', 'superuser')
        def admin_only_view():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Musisz być zalogowany', 'error')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                flash('Brak uprawnień do tej strony', 'error')
                return redirect(url_for('main.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def module_permission_required(*module_names):
    """
    Decorator sprawdzający uprawnienia do modułu — dynamicznie z DB.
    Accepts one or more module names (OR logic — access to ANY grants entry).
    Fallback do MODULE_PERMISSIONS jeśli tabela roles jeszcze nie istnieje.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Musisz być zalogowany', 'error')
                return redirect(url_for('auth.login'))

            has_access = False
            try:
                from repositories.roles.role_repository import RoleRepository
                role_repo = RoleRepository()
                for mod in module_names:
                    if role_repo.role_has_module_access(current_user.role, mod):
                        has_access = True
                        break
            except Exception:
                for mod in module_names:
                    if current_user.role in MODULE_PERMISSIONS.get(mod, []):
                        has_access = True
                        break

            if not has_access:
                flash(f'Brak dostępu do modułu: {module_names[0]}', 'error')
                return redirect(url_for('main.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def can_access_module(user_role: str, module_name: str) -> bool:
    """
    Check if a user role can access a specific module

    Args:
        user_role: User's role (e.g., 'admin')
        module_name: Module name (e.g., 'clients')

    Returns:
        True if user has access, False otherwise
    """
    allowed_roles = MODULE_PERMISSIONS.get(module_name, [])
    return user_role in allowed_roles


def get_user_modules(user_role: str) -> list:
    """
    Get list of modules a user can access

    Args:
        user_role: User's role

    Returns:
        List of module names
    """
    accessible_modules = []
    for module, allowed_roles in MODULE_PERMISSIONS.items():
        if user_role in allowed_roles:
            accessible_modules.append(module)
    return accessible_modules


def get_user_module_permissions(role_name: str) -> dict:
    """
    Pobierz dict {module: bool} dla roli użytkownika.
    Używane przez context processor w app.py.
    Fallback do statycznego MODULE_PERMISSIONS.
    """
    try:
        from repositories.roles.role_repository import RoleRepository
        role_repo = RoleRepository()
        return role_repo.get_user_module_permissions(role_name)
    except Exception:
        # Fallback: build from static config
        return {
            module: role_name in allowed_roles
            for module, allowed_roles in MODULE_PERMISSIONS.items()
        }
