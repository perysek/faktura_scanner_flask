"""
Konfiguracja autentykacji i autoryzacji
Role-based access control (RBAC) configuration
"""
from functools import wraps
from flask import redirect, url_for, flash, request, jsonify
from flask_login import current_user
from config.ui_messages import msg

# HTTP methods that mutate state. A role flagged read_only for a module may reach
# view (GET) routes but must be blocked from any of these on that module.
MUTATING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def _wants_json() -> bool:
    """Heuristic: does the caller expect a JSON body rather than an HTML page?

    True for API paths, XHR/fetch requests, and Accept: application/json. Used so a
    denied write returns a 403 JSON error to fetch callers (which the frontend can
    surface) instead of a 302 redirect to an HTML page they can't parse.
    """
    if request.path.startswith('/api') or request.path.startswith('/appointments'):
        return True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    # Only treat as JSON when the client *explicitly* prefers it over HTML. A bare
    # `*/*` (json == html) or a browser's `text/html,...` (html > json) is a page
    # navigation → fall through to a flash + redirect, matching prior behaviour.
    accept = request.accept_mimetypes
    return accept['application/json'] > accept['text/html']


def _deny(msg_key: str, **fmt):
    """Uniform permission denial: JSON 403 for API/XHR callers, flash+redirect for
    normal page navigations. Keeps the security boundary consistent across both."""
    if _wants_json():
        return jsonify({'success': False, 'error': msg(msg_key, **fmt)}), 403
    flash(msg(msg_key, **fmt), 'error')
    return redirect(request.referrer or url_for('main.dashboard'))

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
    'data_import': ['superuser', 'admin'],
    'absences': ['superuser', 'admin'],  # full management (categories CRUD + global list)
    'service_prices': ['superuser', 'admin', 'accountant'],  # accountant = read-only (view history)
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
                flash(msg('auth.guard.login_required'), 'error')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                flash(msg('auth.permission.role_denied'), 'error')
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
                flash(msg('auth.guard.login_required'), 'error')
                return redirect(url_for('auth.login'))

            # Resolve access AND write-capability across the route's module list.
            # has_access = user can reach ANY listed module (OR logic, unchanged).
            # writable   = at least one accessible module is NOT read_only, i.e. the
            #              user may perform mutating requests through this route.
            has_access = False
            writable = False
            try:
                from repositories.roles.role_repository import RoleRepository
                role_repo = RoleRepository()
                for mod in module_names:
                    flags = role_repo.get_permission_flags(current_user.role, mod)
                    if flags['has_access']:
                        has_access = True
                        if not flags['read_only']:
                            writable = True
            except Exception:
                # DB unavailable → fall back to the static map (full access, no
                # read_only concept there, so any access implies write).
                for mod in module_names:
                    if current_user.role in MODULE_PERMISSIONS.get(mod, []):
                        has_access = True
                        writable = True

            if not has_access:
                return _deny('auth.permission.module_denied', module=module_names[0])

            # read_only enforcement: block state-changing methods for a role whose
            # only grant(s) to this route are read_only. GET/HEAD/OPTIONS pass — the
            # role can still view. (Form-serving GET routes stay reachable; the
            # submit they POST to is what gets stopped here.)
            if request.method in MUTATING_METHODS and not writable:
                return _deny('auth.permission.read_only', module=module_names[0])

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


def is_supervisor(user) -> bool:
    """True if the user's linked employee record appears on the supervisor side
    of any employee_supervisors row. Used by context processor + decorator.
    """
    if not user or not user.is_authenticated:
        return False
    try:
        from repositories.employees.employee_repository import EmployeeRepository
        from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
        emp_row = EmployeeRepository().get_by_user_id(user.id)
        if not emp_row:
            return False
        return EmployeeSupervisorRepository().is_supervisor(emp_row['id'])
    except Exception:
        return False


def get_linked_employee(user):
    """Return the employee row linked to this user, or None."""
    if not user or not user.is_authenticated:
        return None
    try:
        from repositories.employees.employee_repository import EmployeeRepository
        return EmployeeRepository().get_by_user_id(user.id)
    except Exception:
        return None


def absence_management_required(f):
    """Allow access to absence management views for admin/superuser OR supervisors.

    Supervisors (stylists who manage subordinates) get tabs #1 and #2 but NOT
    tab #3 (categories), which is gated by module_permission_required('absences').
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(msg('auth.guard.login_required'), 'error')
            return redirect(url_for('auth.login'))

        has_access = False
        try:
            from repositories.roles.role_repository import RoleRepository
            if RoleRepository().role_has_module_access(current_user.role, 'absences'):
                has_access = True
        except Exception:
            if current_user.role in MODULE_PERMISSIONS.get('absences', []):
                has_access = True

        if not has_access:
            has_access = is_supervisor(current_user)

        if not has_access:
            flash(msg('auth.permission.absences_denied'), 'error')
            return redirect(url_for('main.dashboard'))

        return f(*args, **kwargs)
    return decorated_function


def get_permission_flags(role_name: str, module_name: str) -> dict:
    """
    Zwraca pełne flagi uprawnień {has_access, read_only, own_data} dla roli+modułu.
    Używane przez dekoratory i helpery wymuszające ograniczenia read_only/own_data.
    """
    try:
        from repositories.roles.role_repository import RoleRepository
        return RoleRepository().get_permission_flags(role_name, module_name)
    except Exception:
        has_access = role_name in MODULE_PERMISSIONS.get(module_name, [])
        return {'has_access': has_access, 'read_only': False, 'own_data': False}


def is_read_only(role_name: str, module_name: str) -> bool:
    """True jeśli rola ma dostęp do modułu tylko do odczytu."""
    flags = get_permission_flags(role_name, module_name)
    return flags['has_access'] and flags['read_only']


def is_own_data_only(role_name: str, module_name: str) -> bool:
    """True jeśli rola może widzieć tylko własne dane w module."""
    flags = get_permission_flags(role_name, module_name)
    return flags['has_access'] and flags['own_data']


def own_data_employee_id(user, module_name: str):
    """Scope helper for the own_data flag.

    Returns the employee id that `module_name` records must be filtered to when the
    user's role is own_data-restricted for that module — i.e. the user's linked
    employee. When the role has own_data but the user has no linked employee record,
    returns a sentinel (-1) that matches nothing, so the user sees their own data
    (none) rather than everyone's. Returns None when own_data does not apply, meaning
    "no scoping — leave the query as-is".
    """
    role_name = getattr(user, 'role', None)
    if not role_name or not is_own_data_only(role_name, module_name):
        return None
    emp = get_linked_employee(user)
    return emp['id'] if emp else -1


def can_edit_service_price_history(role_name: str) -> bool:
    """True if the role may delete/edit service price-history entries.

    Requires 'services' access AND the can_edit_price_history flag. Falls back
    to built-in admin roles if the roles table is unavailable.
    """
    try:
        from repositories.roles.role_repository import RoleRepository
        return RoleRepository().role_can_edit_price_history(role_name)
    except Exception:
        return role_name in ('superuser', 'admin')


def can_send_appointment_sms(role_name: str) -> bool:
    """True if the role may send manual SMS from the appointment view.

    Requires 'appointments' access AND the can_send_sms flag. Falls back
    to built-in admin roles if the roles table is unavailable.
    """
    try:
        from repositories.roles.role_repository import RoleRepository
        return RoleRepository().role_can_send_sms(role_name)
    except Exception:
        return role_name in ('superuser', 'admin')


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


def get_all_permission_flags(role_name: str) -> dict:
    """Zwraca {module: {has_access, read_only, own_data}} dla całej roli w jednym
    zapytaniu. Używane przez context processor, aby wystawić do szablonów zarówno
    dostęp (user_permissions) jak i prawo zapisu (user_write_permissions).
    Fallback do statycznego MODULE_PERMISSIONS (bez read_only/own_data).
    """
    try:
        from repositories.roles.role_repository import RoleRepository
        return RoleRepository().get_all_flags(role_name)
    except Exception:
        return {
            module: {
                'has_access': role_name in allowed_roles,
                'read_only': False,
                'own_data': False,
            }
            for module, allowed_roles in MODULE_PERMISSIONS.items()
        }
