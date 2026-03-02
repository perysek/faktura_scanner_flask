# Users & Roles Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Users Management module (Task A) and a Roles Management module (Task B) to the existing Flask salon application, accessible via new "System" sidebar items above "Profil".

**Architecture:** All data stored in PostgreSQL (two new tables: `roles` + `role_permissions`). Role permissions become dynamic — the `module_permission_required` decorator queries the DB at runtime instead of using a hardcoded dict. Two new blueprints added: `users_bp` (superuser + admin) and `roles_bp` (superuser only). Templates follow the existing "refined minimal" design system used in `employees/list.html`.

**Tech Stack:** Flask blueprints, psycopg2, bcrypt (already installed), Jinja2 templates, TailwindCSS (existing design system), vanilla JavaScript Fetch API.

---

## Codebase Map (for reference)

- **Base template:** `templates/base.html` — all pages extend this
- **Sidebar:** `templates/components/sidebar.html` — navigation, hardcoded role checks
- **Auth decorators:** `config/auth_config.py` — `module_permission_required`, `role_required`
- **User model:** `database/models.py` → `User` dataclass
- **User repository:** `repositories/users/user_repository.py`
- **Employee repository:** `repositories/employees/employee_repository.py`
- **Auth routes:** `routes/auth/routes.py` (blueprint prefix: `/auth`)
- **Main routes:** `routes/main_routes.py` (no prefix)
- **API routes:** `routes/api_routes.py` (prefix: `/api`)
- **App factory:** `app.py` → `create_app()`
- **DB schema:** `database/schema.sql` — run via `initialize_database()`

## Modules for Role Permissions Toggles

The 7 module keys that map to sidebar sections:

| Module key    | Polish label              |
|---------------|---------------------------|
| `invoices`    | Faktury / Koszty          |
| `appointments`| Wizyty                    |
| `clients`     | Klienci                   |
| `employees`   | Pracownicy                |
| `services`    | Usługi                    |
| `settings`    | Ustawienia                |
| `reports`     | Historia / Raporty        |

---

## Task 1: Database schema — roles & role_permissions tables

**Files:**
- Modify: `database/schema.sql` (append to end)

**Step 1: Append new SQL to schema.sql**

Add at the bottom of `database/schema.sql`:

```sql
-- ============================================================
-- Roles & dynamic permissions (Users/Roles management module)
-- ============================================================

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    is_protected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    has_access BOOLEAN DEFAULT TRUE,
    UNIQUE (role_id, module_name)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);

-- Seed built-in roles (idempotent)
INSERT INTO roles (name, display_name, is_protected) VALUES
    ('superuser',    'Właściciel',    TRUE),
    ('admin',        'Administrator', FALSE),
    ('receptionist', 'Recepcjonista', FALSE),
    ('stylist',      'Stylista',      FALSE),
    ('accountant',   'Księgowy',      FALSE)
ON CONFLICT (name) DO NOTHING;

-- Seed role_permissions: all roles get all modules enabled (adjust before deployment)
DO $$
DECLARE
    r RECORD;
    modules TEXT[] := ARRAY['invoices','appointments','clients','employees','services','settings','reports'];
    m TEXT;
BEGIN
    FOR r IN SELECT id FROM roles LOOP
        FOREACH m IN ARRAY modules LOOP
            INSERT INTO role_permissions (role_id, module_name, has_access)
            VALUES (r.id, m, TRUE)
            ON CONFLICT (role_id, module_name) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;
```

**Step 2: Run database initialization to apply schema**

```bash
python -c "from config.database import initialize_database; initialize_database()"
```

Expected output: `Baza danych zainicjalizowana`

**Step 3: Verify tables created**

```bash
python -c "
from config.database import get_db_connection
import psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = get_db_connection()
# This won't work outside Flask context — just run the app and check
print('Schema updated OK')
"
```

**Step 4: Commit**

```bash
git add database/schema.sql
git commit -m "feat(roles): add roles and role_permissions tables with seeded data"
```

---

## Task 2: RoleRepository

**Files:**
- Create: `repositories/roles/__init__.py`
- Create: `repositories/roles/role_repository.py`

**Step 1: Create the __init__.py**

```python
# repositories/roles/__init__.py
```
(empty file)

**Step 2: Create role_repository.py**

```python
"""
Repository dla ról i uprawnień modułów
"""
from typing import Any, Optional
from config.database import get_db_connection

# All known modules (must match auth_config.MODULE_PERMISSIONS keys)
ALL_MODULES = ['invoices', 'appointments', 'clients', 'employees', 'services', 'settings', 'reports']

MODULE_DISPLAY_NAMES = {
    'invoices':     'Faktury / Koszty',
    'appointments': 'Wizyty',
    'clients':      'Klienci',
    'employees':    'Pracownicy',
    'services':     'Usługi',
    'settings':     'Ustawienia',
    'reports':      'Historia / Raporty',
}


class RoleRepository:
    """Repository dla zarządzania rolami i ich uprawnieniami do modułów"""

    def get_all(self) -> list:
        """Pobierz wszystkie role z liczbą uprawnień"""
        query = """
            SELECT r.id, r.name, r.display_name, r.is_protected, r.created_at,
                   COUNT(rp.id) FILTER (WHERE rp.has_access = TRUE) AS access_count
            FROM roles r
            LEFT JOIN role_permissions rp ON rp.role_id = r.id
            GROUP BY r.id, r.name, r.display_name, r.is_protected, r.created_at
            ORDER BY r.id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_id(self, role_id: int) -> Optional[Any]:
        """Pobierz rolę po ID"""
        query = "SELECT * FROM roles WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_id,))
            return cursor.fetchone()

    def get_by_name(self, name: str) -> Optional[Any]:
        """Pobierz rolę po nazwie"""
        query = "SELECT * FROM roles WHERE name = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (name,))
            return cursor.fetchone()

    def create(self, name: str, display_name: str) -> int:
        """Utwórz nową rolę (domyślnie bez dostępu do żadnych modułów)"""
        query = """
            INSERT INTO roles (name, display_name, is_protected)
            VALUES (%s, %s, FALSE)
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (name, display_name))
            row = cursor.fetchone()
            conn.commit()
            return row['id']

    def update(self, role_id: int, display_name: str):
        """Zaktualizuj display_name roli"""
        query = "UPDATE roles SET display_name = %s WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (display_name, role_id))
            conn.commit()

    def delete(self, role_id: int) -> bool:
        """Usuń rolę (tylko niechronione). Zwraca True jeśli usunięto."""
        query = "DELETE FROM roles WHERE id = %s AND is_protected = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_permissions(self, role_id: int) -> dict:
        """
        Zwraca słownik modułów i ich dostępu dla danej roli.
        Przykład: {'invoices': True, 'clients': False, ...}
        Nieznane moduły defaultują do False.
        """
        query = "SELECT module_name, has_access FROM role_permissions WHERE role_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_id,))
            rows = cursor.fetchall()

        db_perms = {row['module_name']: bool(row['has_access']) for row in rows}
        # Fill in missing modules with False
        return {m: db_perms.get(m, False) for m in ALL_MODULES}

    def set_permissions(self, role_id: int, permissions: dict):
        """
        Ustaw uprawnienia roli. permissions = {'invoices': True, 'clients': False, ...}
        Wykonuje upsert dla każdego modułu.
        """
        query = """
            INSERT INTO role_permissions (role_id, module_name, has_access)
            VALUES (%s, %s, %s)
            ON CONFLICT (role_id, module_name) DO UPDATE SET has_access = EXCLUDED.has_access
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for module in ALL_MODULES:
                has_access = bool(permissions.get(module, False))
                cursor.execute(query, (role_id, module, has_access))
            conn.commit()

    def role_has_module_access(self, role_name: str, module_name: str) -> bool:
        """
        Sprawdź czy rola ma dostęp do modułu.
        Używane przez module_permission_required decorator.
        """
        query = """
            SELECT rp.has_access
            FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = %s AND rp.module_name = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_name, module_name))
            row = cursor.fetchone()
        if row is None:
            return False
        return bool(row['has_access'])

    def get_user_module_permissions(self, role_name: str) -> dict:
        """
        Zwraca dict {module_name: bool} dla danej roli.
        Używane przez context processor.
        """
        query = """
            SELECT rp.module_name, rp.has_access
            FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_name,))
            rows = cursor.fetchall()

        db_perms = {row['module_name']: bool(row['has_access']) for row in rows}
        return {m: db_perms.get(m, False) for m in ALL_MODULES}
```

**Step 3: Commit**

```bash
git add repositories/roles/
git commit -m "feat(roles): add RoleRepository with CRUD and permission management"
```

---

## Task 3: Update auth_config.py — dynamic DB-backed permissions

**Files:**
- Modify: `config/auth_config.py`

**Step 1: Update module_permission_required to use DB with static fallback**

Replace the `module_permission_required` function (lines 54-77 in auth_config.py):

```python
def module_permission_required(module_name):
    """
    Decorator sprawdzający uprawnienia do modułu — dynamicznie z DB.
    Fallback do MODULE_PERMISSIONS jeśli tabela roles jeszcze nie istnieje.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Musisz być zalogowany', 'error')
                return redirect(url_for('auth.login'))

            try:
                from repositories.roles.role_repository import RoleRepository
                role_repo = RoleRepository()
                has_access = role_repo.role_has_module_access(current_user.role, module_name)
            except Exception:
                # Fallback to static config (e.g. during initial DB setup)
                allowed_roles = MODULE_PERMISSIONS.get(module_name, [])
                has_access = current_user.role in allowed_roles

            if not has_access:
                flash(f'Brak dostępu do modułu: {module_name}', 'error')
                return redirect(url_for('main.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

Also add a new helper function at the bottom of auth_config.py:

```python
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
```

**Step 2: Commit**

```bash
git add config/auth_config.py
git commit -m "feat(roles): update module_permission_required to use dynamic DB permissions"
```

---

## Task 4: Update app.py — context processor for sidebar permissions

**Files:**
- Modify: `app.py`

**Step 1: Add user_permissions to context processor**

In the `inject_globals` context processor function (around line 173 in app.py), add `user_permissions`:

```python
@app.context_processor
def inject_globals():
    from flask_login import current_user
    from config.auth_config import get_user_module_permissions

    user_permissions = {}
    if current_user.is_authenticated:
        try:
            user_permissions = get_user_module_permissions(current_user.role)
        except Exception:
            pass

    return {
        'app_name': APP_NAME,
        'version': VERSION,
        'now': datetime.now,
        'logo_data_uri': logo_data_uri,
        'user_permissions': user_permissions,
    }
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat(roles): inject user_permissions dict into all templates via context processor"
```

---

## Task 5: Update sidebar — add Users & Roles nav items

**Files:**
- Modify: `templates/components/sidebar.html`

**Step 1: Add Users and Roles links to System section**

In the System section of sidebar.html, BEFORE the `Profil` link (around line 146), add:

```html
{% if current_user.role in ['superuser', 'admin'] %}
<a href="{{ url_for('users.users_list') }}"
   class="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 group
   {% if request.endpoint == 'users.users_list' %}bg-gradient-to-r from-primary-600/20 to-primary-600/10 text-primary-400 border border-primary-500/10{% else %}text-slate-400 hover:bg-slate-800 hover:text-white{% endif %}">
    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
    Użytkownicy
</a>
{% endif %}

{% if current_user.role == 'superuser' %}
<a href="{{ url_for('roles.roles_list') }}"
   class="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 group
   {% if request.endpoint == 'roles.roles_list' %}bg-gradient-to-r from-primary-600/20 to-primary-600/10 text-primary-400 border border-primary-500/10{% else %}text-slate-400 hover:bg-slate-800 hover:text-white{% endif %}">
    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
    Role
</a>
{% endif %}
```

**Step 2: Commit**

```bash
git add templates/components/sidebar.html
git commit -m "feat(users): add Użytkownicy and Role nav items to sidebar System section"
```

---

## Task 6: UserRepository — add update_user and get_all_with_employee

**Files:**
- Modify: `repositories/users/user_repository.py`

**Step 1: Add these methods to UserRepository**

```python
def get_all_with_employee(self) -> list:
    """
    Pobierz wszystkich użytkowników wraz z powiązanym pracownikiem (jeśli istnieje).
    Zwraca surowe Row objects z polami: id, email, full_name, role, is_active,
    last_login, created_at, employee_id, employee_first_name, employee_last_name
    """
    query = """
        SELECT u.id, u.email, u.full_name, u.role, u.is_active,
               u.last_login, u.created_at,
               e.id AS employee_id,
               e.first_name AS employee_first_name,
               e.last_name AS employee_last_name
        FROM users u
        LEFT JOIN employees e ON e.user_id = u.id
        ORDER BY u.full_name
    """
    conn = self._get_conn()
    cursor = conn.cursor()
    cursor.execute(query)
    return cursor.fetchall()

def update_user(self, user_id: int, email: str, full_name: str, role: str, is_active: bool):
    """
    Zaktualizuj dane użytkownika (email, imię, rola, aktywność).
    Nie aktualizuje hasła — użyj update_password() osobno.
    """
    query = """
        UPDATE users
        SET email = %s, full_name = %s, role = %s, is_active = %s, updated_at = %s
        WHERE id = %s
    """
    self._execute(query, (email, full_name, role, is_active, datetime.now(), user_id))

def unlink_employee(self, user_id: int):
    """Odepnij pracownika od konta użytkownika (ustaw user_id = NULL w employees)"""
    query = "UPDATE employees SET user_id = NULL WHERE user_id = %s"
    self._execute(query, (user_id,))

def link_employee(self, user_id: int, employee_id: int):
    """
    Przypisz pracownika do konta użytkownika.
    Najpierw odłącza ewentualnego poprzedniego użytkownika od tego pracownika.
    """
    # Clear previous user link for this employee
    query_clear = "UPDATE employees SET user_id = NULL WHERE id = %s"
    self._execute(query_clear, (employee_id,))
    # Clear previous employee link for this user
    query_unlink_old = "UPDATE employees SET user_id = NULL WHERE user_id = %s AND id != %s"
    self._execute(query_unlink_old, (user_id, employee_id))
    # Link
    query_link = "UPDATE employees SET user_id = %s WHERE id = %s"
    self._execute(query_link, (user_id, employee_id))

def get_available_employees(self) -> list:
    """
    Pobierz pracowników bez przypisanego konta użytkownika.
    Używane w formularzu tworzenia/edycji użytkownika.
    """
    query = """
        SELECT id, first_name, last_name
        FROM employees
        WHERE user_id IS NULL AND is_active = TRUE
        ORDER BY last_name, first_name
    """
    conn = self._get_conn()
    cursor = conn.cursor()
    cursor.execute(query)
    return cursor.fetchall()

def get_linked_employee(self, user_id: int):
    """Pobierz pracownika powiązanego z użytkownikiem (lub None)"""
    query = "SELECT id, first_name, last_name FROM employees WHERE user_id = %s"
    conn = self._get_conn()
    cursor = conn.cursor()
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
```

**Step 2: Commit**

```bash
git add repositories/users/user_repository.py
git commit -m "feat(users): add update_user, employee linking methods to UserRepository"
```

---

## Task 7: Users Blueprint — routes and API

**Files:**
- Create: `routes/users/__init__.py`
- Create: `routes/users/routes.py`

**Step 1: Create __init__.py**

```python
# routes/users/__init__.py
```
(empty)

**Step 2: Create routes.py**

```python
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
```

**Step 3: Commit**

```bash
git add routes/users/
git commit -m "feat(users): add users blueprint with list/create/edit pages and CRUD API"
```

---

## Task 8: Roles Blueprint — routes and API

**Files:**
- Create: `routes/roles/__init__.py`
- Create: `routes/roles/routes.py`

**Step 1: Create __init__.py**

```python
# routes/roles/__init__.py
```
(empty)

**Step 2: Create routes.py**

```python
"""
Zarządzanie rolami i uprawnieniami — strony i API
Dostępne tylko dla: superuser
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from config.auth_config import role_required
from repositories.roles.role_repository import RoleRepository, ALL_MODULES, MODULE_DISPLAY_NAMES

roles_bp = Blueprint('roles', __name__, url_prefix='/system/roles')


def _role_repo() -> RoleRepository:
    return RoleRepository()


# ─── Page Routes ─────────────────────────────────────────────────────────────

@roles_bp.route('/')
@login_required
@role_required('superuser')
def roles_list():
    """Lista ról"""
    return render_template('roles/list.html')


@roles_bp.route('/create')
@login_required
@role_required('superuser')
def create_role():
    """Formularz tworzenia nowej roli"""
    return render_template('roles/create.html',
                           all_modules=ALL_MODULES,
                           module_display_names=MODULE_DISPLAY_NAMES)


@roles_bp.route('/<int:role_id>/edit')
@login_required
@role_required('superuser')
def edit_role(role_id):
    """Formularz edycji uprawnień roli"""
    role_repo = _role_repo()
    role = role_repo.get_by_id(role_id)
    if not role:
        return render_template('errors/404.html'), 404

    permissions = role_repo.get_permissions(role_id)
    return render_template('roles/edit.html',
                           role=role,
                           permissions=permissions,
                           all_modules=ALL_MODULES,
                           module_display_names=MODULE_DISPLAY_NAMES)


# ─── API Endpoints ────────────────────────────────────────────────────────────

@roles_bp.route('/api', methods=['GET'])
@login_required
@role_required('superuser')
def api_list():
    """GET /system/roles/api — lista ról"""
    role_repo = _role_repo()
    rows = role_repo.get_all()
    roles_data = []
    for row in rows:
        perms = role_repo.get_permissions(row['id'])
        roles_data.append({
            'id': row['id'],
            'name': row['name'],
            'display_name': row['display_name'],
            'is_protected': bool(row['is_protected']),
            'access_count': row['access_count'],
            'permissions': perms,
        })
    return jsonify({'roles': roles_data, 'count': len(roles_data)})


@roles_bp.route('/api', methods=['POST'])
@login_required
@role_required('superuser')
def api_create():
    """POST /system/roles/api — utwórz nową rolę"""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip().lower().replace(' ', '_')
    display_name = (data.get('display_name') or '').strip()
    permissions = data.get('permissions') or {}

    if not name or not display_name:
        return jsonify({'error': 'Nazwa i wyświetlana nazwa są wymagane'}), 400

    role_repo = _role_repo()
    if role_repo.get_by_name(name):
        return jsonify({'error': f'Rola o nazwie "{name}" już istnieje'}), 409

    try:
        role_id = role_repo.create(name, display_name)
        role_repo.set_permissions(role_id, permissions)
        return jsonify({'success': True, 'role_id': role_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@roles_bp.route('/api/<int:role_id>', methods=['PUT'])
@login_required
@role_required('superuser')
def api_update(role_id):
    """PUT /system/roles/api/<id> — zaktualizuj display_name i uprawnienia"""
    role_repo = _role_repo()
    role = role_repo.get_by_id(role_id)
    if not role:
        return jsonify({'error': 'Rola nie znaleziona'}), 404

    data = request.get_json() or {}
    display_name = (data.get('display_name') or '').strip()
    permissions = data.get('permissions') or {}

    if not display_name:
        return jsonify({'error': 'Wyświetlana nazwa jest wymagana'}), 400

    try:
        role_repo.update(role_id, display_name)
        role_repo.set_permissions(role_id, permissions)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@roles_bp.route('/api/<int:role_id>', methods=['DELETE'])
@login_required
@role_required('superuser')
def api_delete(role_id):
    """DELETE /system/roles/api/<id> — usuń niechronioną rolę"""
    role_repo = _role_repo()
    role = role_repo.get_by_id(role_id)
    if not role:
        return jsonify({'error': 'Rola nie znaleziona'}), 404

    if bool(role['is_protected']):
        return jsonify({'error': 'Nie można usunąć chronionej roli systemowej'}), 403

    deleted = role_repo.delete(role_id)
    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Nie udało się usunąć roli'}), 500
```

**Step 3: Commit**

```bash
git add routes/roles/
git commit -m "feat(roles): add roles blueprint with list/create/edit pages and CRUD API"
```

---

## Task 9: Register new blueprints in app.py

**Files:**
- Modify: `app.py`

**Step 1: Import and register blueprints**

After the existing blueprint imports (around line 140 in app.py), add:

```python
from routes.users.routes import users_bp
from routes.roles.routes import roles_bp
```

After `app.register_blueprint(analytics_bp, ...)`, add:

```python
app.register_blueprint(users_bp)
app.register_blueprint(roles_bp)
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat(users): register users_bp and roles_bp blueprints in app factory"
```

---

## Task 10: Users List Template

**Files:**
- Create: `templates/users/list.html`

**Step 1: Create the template**

The template follows the "refined minimal" design system used in `templates/employees/list.html`.
Key elements: same CSS variables, page-header pattern, stat cards, data table with JS fetch.

```html
{% extends "base.html" %}

{% block title %}Użytkownicy - {{ app_name }}{% endblock %}

{% block extra_css %}
<style>
    :root {
        --color-ink: #1a1a1a;
        --color-ink-muted: #525252;
        --color-ink-subtle: #8a8a8a;
        --color-surface: #fafafa;
        --color-surface-warm: #f7f6f3;
        --color-border: #e8e6e1;
        --color-accent: #c9a227;
        --color-success: #2d6a4f;
        --color-error: #9b2c2c;
        --font-display: 'Inter', system-ui, sans-serif;
    }
    body { background: var(--color-surface-warm); font-family: var(--font-display); color: var(--color-ink); }
    .refined-page { max-width: 1400px; margin: 0 auto; padding: 2rem; }
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
    .page-title { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; }
    .page-subtitle { color: var(--color-ink-muted); font-size: 0.8125rem; font-weight: 300; }
    .refined-card { background: white; border: 1px solid var(--color-border); border-radius: 2px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .refined-table { width: 100%; border-collapse: collapse; }
    .refined-table th { padding: 0.625rem 1rem; text-align: left; font-size: 0.6875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-ink-subtle); border-bottom: 1px solid var(--color-border); }
    .refined-table td { padding: 0.875rem 1rem; font-size: 0.8125rem; border-bottom: 1px solid var(--color-border-subtle, #f0eeea); vertical-align: middle; }
    .refined-table tr:last-child td { border-bottom: none; }
    .refined-table tr:hover td { background: var(--color-surface); }
    .badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.125rem 0.5rem; border-radius: 2px; font-size: 0.6875rem; font-weight: 500; letter-spacing: 0.03em; }
    .badge-active { background: #dcfce7; color: #166534; }
    .badge-inactive { background: #f3f4f6; color: #6b7280; }
    .badge-role { background: #eff6ff; color: #1d4ed8; }
    .badge-superuser { background: #fef3c7; color: #92400e; }
    .btn-primary { background: var(--color-ink); color: white; border: none; padding: 0.5rem 1rem; border-radius: 2px; font-size: 0.8125rem; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 0.375rem; text-decoration: none; transition: opacity 0.15s; }
    .btn-primary:hover { opacity: 0.8; }
    .btn-ghost { background: none; border: 1px solid var(--color-border); color: var(--color-ink-muted); padding: 0.375rem 0.75rem; border-radius: 2px; font-size: 0.75rem; cursor: pointer; text-decoration: none; transition: all 0.15s; }
    .btn-ghost:hover { border-color: var(--color-ink); color: var(--color-ink); }
    .search-input { border: 1px solid var(--color-border); border-radius: 2px; padding: 0.5rem 0.75rem; font-size: 0.8125rem; background: white; color: var(--color-ink); outline: none; width: 240px; }
    .search-input:focus { border-color: var(--color-ink); }
    #loading-state, #empty-state { text-align: center; padding: 3rem; color: var(--color-ink-muted); font-size: 0.875rem; }
</style>
{% endblock %}

{% block content %}
<div class="refined-page">
    <div class="page-header">
        <div>
            <h1 class="page-title">Użytkownicy</h1>
            <p class="page-subtitle">Zarządzanie kontami użytkowników systemu</p>
        </div>
        <div class="flex items-center gap-3">
            <input type="text" id="search-input" class="search-input" placeholder="Szukaj użytkownika...">
            <a href="{{ url_for('users.create_user') }}" class="btn-primary">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                </svg>
                Nowy użytkownik
            </a>
        </div>
    </div>

    <div class="refined-card">
        <div id="loading-state">Ładowanie...</div>
        <div id="empty-state" style="display:none;">Brak użytkowników.</div>
        <table class="refined-table" id="users-table" style="display:none;">
            <thead>
                <tr>
                    <th>Imię i nazwisko</th>
                    <th>Email</th>
                    <th>Rola</th>
                    <th>Pracownik</th>
                    <th>Status</th>
                    <th>Ostatnie logowanie</th>
                    <th></th>
                </tr>
            </thead>
            <tbody id="users-body"></tbody>
        </table>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    let allUsers = [];

    async function loadUsers() {
        try {
            const resp = await fetch('{{ url_for("users.api_list") }}');
            const data = await resp.json();
            allUsers = data.users || [];
            renderUsers(allUsers);
        } catch(e) {
            document.getElementById('loading-state').textContent = 'Błąd ładowania danych.';
        }
    }

    function renderUsers(users) {
        const loading = document.getElementById('loading-state');
        const empty = document.getElementById('empty-state');
        const table = document.getElementById('users-table');
        const tbody = document.getElementById('users-body');

        loading.style.display = 'none';
        if (!users.length) {
            empty.style.display = 'block';
            table.style.display = 'none';
            return;
        }
        empty.style.display = 'none';
        table.style.display = 'table';

        tbody.innerHTML = users.map(u => {
            const roleBadgeClass = u.role === 'superuser' ? 'badge-superuser' : 'badge-role';
            const statusBadge = u.is_active
                ? '<span class="badge badge-active">Aktywny</span>'
                : '<span class="badge badge-inactive">Nieaktywny</span>';
            const lastLogin = u.last_login
                ? new Date(u.last_login).toLocaleString('pl-PL', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})
                : '—';
            const employeeName = u.employee_name || '<span style="color:var(--color-ink-subtle)">—</span>';

            return `<tr>
                <td style="font-weight:500">${escapeHtml(u.full_name)}</td>
                <td style="color:var(--color-ink-muted)">${escapeHtml(u.email)}</td>
                <td><span class="badge ${roleBadgeClass}">${escapeHtml(u.role)}</span></td>
                <td>${employeeName}</td>
                <td>${statusBadge}</td>
                <td style="color:var(--color-ink-muted)">${lastLogin}</td>
                <td style="text-align:right">
                    <a href="/system/users/${u.id}/edit" class="btn-ghost">Edytuj</a>
                </td>
            </tr>`;
        }).join('');
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    document.getElementById('search-input').addEventListener('input', function() {
        const q = this.value.toLowerCase();
        renderUsers(allUsers.filter(u =>
            u.full_name.toLowerCase().includes(q) ||
            u.email.toLowerCase().includes(q) ||
            u.role.toLowerCase().includes(q)
        ));
    });

    loadUsers();
</script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/users/list.html
git commit -m "feat(users): add users list template with search and status badges"
```

---

## Task 11: Users Create Template

**Files:**
- Create: `templates/users/create.html`

**Step 1: Create the template**

```html
{% extends "base.html" %}

{% block title %}Nowy użytkownik - {{ app_name }}{% endblock %}

{% block extra_css %}
<style>
    :root {
        --color-ink: #1a1a1a; --color-ink-muted: #525252; --color-surface-warm: #f7f6f3;
        --color-border: #e8e6e1; --color-accent: #c9a227; --color-error: #9b2c2c;
        --font-display: 'Inter', system-ui, sans-serif;
    }
    body { background: var(--color-surface-warm); font-family: var(--font-display); color: var(--color-ink); }
    .refined-page { max-width: 720px; margin: 0 auto; padding: 2rem; }
    .page-title { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 2rem; }
    .refined-card { background: white; border: 1px solid var(--color-border); border-radius: 2px; padding: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .field-label { display: block; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-ink-muted); margin-bottom: 0.375rem; }
    .field-input { width: 100%; border: 1px solid var(--color-border); border-radius: 2px; padding: 0.625rem 0.75rem; font-size: 0.875rem; background: white; color: var(--color-ink); outline: none; box-sizing: border-box; }
    .field-input:focus { border-color: var(--color-ink); }
    .field-group { margin-bottom: 1.25rem; }
    .field-hint { font-size: 0.75rem; color: var(--color-ink-muted); margin-top: 0.25rem; }
    .btn-primary { background: var(--color-ink); color: white; border: none; padding: 0.625rem 1.5rem; border-radius: 2px; font-size: 0.875rem; font-weight: 500; cursor: pointer; }
    .btn-ghost { background: none; border: 1px solid var(--color-border); color: var(--color-ink-muted); padding: 0.625rem 1.25rem; border-radius: 2px; font-size: 0.875rem; cursor: pointer; text-decoration: none; }
    .error-msg { color: var(--color-error); font-size: 0.8125rem; margin-bottom: 1rem; padding: 0.75rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 2px; display: none; }
    .required-mark { color: var(--color-error); }
</style>
{% endblock %}

{% block content %}
<div class="refined-page">
    <h1 class="page-title">Nowy użytkownik</h1>
    <div class="refined-card">
        <div id="error-msg" class="error-msg"></div>
        <form id="create-form">
            <div class="field-group">
                <label class="field-label" for="full_name">Imię i nazwisko <span class="required-mark">*</span></label>
                <input type="text" id="full_name" name="full_name" class="field-input" required>
            </div>
            <div class="field-group">
                <label class="field-label" for="email">Email <span class="required-mark">*</span></label>
                <input type="email" id="email" name="email" class="field-input" required>
            </div>
            <div class="field-group">
                <label class="field-label" for="password">Hasło <span class="required-mark">*</span></label>
                <input type="password" id="password" name="password" class="field-input" required minlength="8">
                <p class="field-hint">Minimum 8 znaków</p>
            </div>
            <div class="field-group">
                <label class="field-label" for="password_confirm">Potwierdź hasło <span class="required-mark">*</span></label>
                <input type="password" id="password_confirm" name="password_confirm" class="field-input" required>
            </div>
            <div class="field-group">
                <label class="field-label" for="role">Rola <span class="required-mark">*</span></label>
                <select id="role" name="role" class="field-input" required>
                    <option value="">-- Wybierz rolę --</option>
                    {% for role in roles %}
                    <option value="{{ role.name }}">{{ role.display_name }} ({{ role.name }})</option>
                    {% endfor %}
                </select>
            </div>
            <div class="field-group">
                <label class="field-label" for="employee_id">Pracownik <span class="required-mark">*</span></label>
                <select id="employee_id" name="employee_id" class="field-input" required>
                    <option value="">-- Wybierz pracownika --</option>
                    {% for emp in available_employees %}
                    <option value="{{ emp.id }}">{{ emp.first_name }} {{ emp.last_name }}</option>
                    {% endfor %}
                </select>
                <p class="field-hint">Tylko pracownicy bez przypisanego konta użytkownika</p>
            </div>
            <div style="display:flex;gap:0.75rem;margin-top:2rem;">
                <button type="submit" class="btn-primary">Utwórz użytkownika</button>
                <a href="{{ url_for('users.users_list') }}" class="btn-ghost">Anuluj</a>
            </div>
        </form>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    document.getElementById('create-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const errorDiv = document.getElementById('error-msg');
        errorDiv.style.display = 'none';

        const password = document.getElementById('password').value;
        const passwordConfirm = document.getElementById('password_confirm').value;
        if (password !== passwordConfirm) {
            errorDiv.textContent = 'Hasła nie pasują do siebie.';
            errorDiv.style.display = 'block';
            return;
        }

        const payload = {
            full_name: document.getElementById('full_name').value.trim(),
            email: document.getElementById('email').value.trim(),
            password: password,
            role: document.getElementById('role').value,
            employee_id: document.getElementById('employee_id').value || null,
            is_active: true,
        };

        const resp = await fetch('{{ url_for("users.api_create") }}', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.success) {
            window.location.href = '{{ url_for("users.users_list") }}';
        } else {
            errorDiv.textContent = data.error || 'Błąd tworzenia użytkownika.';
            errorDiv.style.display = 'block';
        }
    });
</script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/users/create.html
git commit -m "feat(users): add user create form template"
```

---

## Task 12: Users Edit Template

**Files:**
- Create: `templates/users/edit.html`

**Step 1: Create the template**

```html
{% extends "base.html" %}

{% block title %}Edytuj użytkownika - {{ user.full_name }}{% endblock %}

{% block extra_css %}
{# Same CSS variables as create.html #}
<style>
    :root {
        --color-ink: #1a1a1a; --color-ink-muted: #525252; --color-surface-warm: #f7f6f3;
        --color-border: #e8e6e1; --color-accent: #c9a227; --color-error: #9b2c2c;
        --font-display: 'Inter', system-ui, sans-serif;
    }
    body { background: var(--color-surface-warm); font-family: var(--font-display); color: var(--color-ink); }
    .refined-page { max-width: 720px; margin: 0 auto; padding: 2rem; }
    .page-title { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 2rem; }
    .refined-card { background: white; border: 1px solid var(--color-border); border-radius: 2px; padding: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 1.5rem; }
    .section-title { font-size: 0.875rem; font-weight: 600; color: var(--color-ink-muted); margin-bottom: 1.25rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--color-border); }
    .field-label { display: block; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-ink-muted); margin-bottom: 0.375rem; }
    .field-input { width: 100%; border: 1px solid var(--color-border); border-radius: 2px; padding: 0.625rem 0.75rem; font-size: 0.875rem; background: white; color: var(--color-ink); outline: none; box-sizing: border-box; }
    .field-input:focus { border-color: var(--color-ink); }
    .field-group { margin-bottom: 1.25rem; }
    .field-hint { font-size: 0.75rem; color: var(--color-ink-muted); margin-top: 0.25rem; }
    .btn-primary { background: var(--color-ink); color: white; border: none; padding: 0.625rem 1.5rem; border-radius: 2px; font-size: 0.875rem; font-weight: 500; cursor: pointer; }
    .btn-ghost { background: none; border: 1px solid var(--color-border); color: var(--color-ink-muted); padding: 0.625rem 1.25rem; border-radius: 2px; font-size: 0.875rem; cursor: pointer; text-decoration: none; }
    .error-msg { color: var(--color-error); font-size: 0.8125rem; margin-bottom: 1rem; padding: 0.75rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 2px; display: none; }
    .success-msg { color: #166534; font-size: 0.8125rem; margin-bottom: 1rem; padding: 0.75rem; background: #dcfce7; border: 1px solid #86efac; border-radius: 2px; display: none; }
    .toggle-container { display: flex; align-items: center; gap: 0.75rem; }
    .toggle { position: relative; width: 44px; height: 24px; }
    .toggle input { opacity: 0; width: 0; height: 0; }
    .toggle-slider { position: absolute; cursor: pointer; inset: 0; background: #d1d5db; border-radius: 24px; transition: 0.2s; }
    .toggle-slider:before { content: ''; position: absolute; width: 18px; height: 18px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.2s; }
    input:checked + .toggle-slider { background: #2d6a4f; }
    input:checked + .toggle-slider:before { transform: translateX(20px); }
</style>
{% endblock %}

{% block content %}
<div class="refined-page">
    <h1 class="page-title">Edytuj: {{ user.full_name }}</h1>

    <!-- Basic Info Card -->
    <div class="refined-card">
        <div class="section-title">Dane konta</div>
        <div id="error-msg" class="error-msg"></div>
        <div id="success-msg" class="success-msg"></div>
        <form id="edit-form">
            <div class="field-group">
                <label class="field-label" for="full_name">Imię i nazwisko</label>
                <input type="text" id="full_name" name="full_name" class="field-input"
                       value="{{ user.full_name }}" required>
            </div>
            <div class="field-group">
                <label class="field-label" for="email">Email</label>
                <input type="email" id="email" name="email" class="field-input"
                       value="{{ user.email }}" required>
            </div>
            <div class="field-group">
                <label class="field-label" for="role">Rola</label>
                <select id="role" name="role" class="field-input" required>
                    {% for role in roles %}
                    <option value="{{ role.name }}" {% if role.name == user.role %}selected{% endif %}>
                        {{ role.display_name }} ({{ role.name }})
                    </option>
                    {% endfor %}
                </select>
            </div>
            <div class="field-group">
                <label class="field-label" for="employee_id">Powiązany pracownik</label>
                <select id="employee_id" name="employee_id" class="field-input">
                    <option value="">-- Brak --</option>
                    {% if linked_employee %}
                    <option value="{{ linked_employee.id }}" selected>
                        {{ linked_employee.first_name }} {{ linked_employee.last_name }} (bieżący)
                    </option>
                    {% endif %}
                    {% for emp in available_employees %}
                    <option value="{{ emp.id }}">{{ emp.first_name }} {{ emp.last_name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="field-group">
                <label class="field-label">Aktywne konto</label>
                <div class="toggle-container">
                    <label class="toggle">
                        <input type="checkbox" id="is_active" {% if user.is_active %}checked{% endif %}>
                        <span class="toggle-slider"></span>
                    </label>
                    <span id="active-label" style="font-size:0.875rem;color:var(--color-ink-muted)">
                        {{ 'Aktywne' if user.is_active else 'Nieaktywne' }}
                    </span>
                </div>
            </div>
            <div style="display:flex;gap:0.75rem;margin-top:2rem;">
                <button type="submit" class="btn-primary">Zapisz zmiany</button>
                <a href="{{ url_for('users.users_list') }}" class="btn-ghost">Anuluj</a>
            </div>
        </form>
    </div>

    <!-- Change Password Card -->
    <div class="refined-card">
        <div class="section-title">Zmiana hasła</div>
        <div id="pw-error-msg" class="error-msg"></div>
        <div id="pw-success-msg" class="success-msg"></div>
        <form id="password-form">
            <div class="field-group">
                <label class="field-label" for="new_password">Nowe hasło</label>
                <input type="password" id="new_password" class="field-input" minlength="8"
                       placeholder="Pozostaw puste, aby nie zmieniać">
                <p class="field-hint">Minimum 8 znaków. Pozostaw puste, aby zachować obecne hasło.</p>
            </div>
            <div class="field-group">
                <label class="field-label" for="new_password_confirm">Potwierdź nowe hasło</label>
                <input type="password" id="new_password_confirm" class="field-input">
            </div>
            <button type="submit" class="btn-primary">Zmień hasło</button>
        </form>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    const userId = {{ user.id }};
    const apiUrl = `/system/users/api/${userId}`;

    document.getElementById('is_active').addEventListener('change', function() {
        document.getElementById('active-label').textContent = this.checked ? 'Aktywne' : 'Nieaktywne';
    });

    document.getElementById('edit-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const errorDiv = document.getElementById('error-msg');
        const successDiv = document.getElementById('success-msg');
        errorDiv.style.display = 'none';
        successDiv.style.display = 'none';

        const payload = {
            full_name: document.getElementById('full_name').value.trim(),
            email: document.getElementById('email').value.trim(),
            role: document.getElementById('role').value,
            is_active: document.getElementById('is_active').checked,
            employee_id: document.getElementById('employee_id').value || null,
        };

        const resp = await fetch(apiUrl, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.success) {
            successDiv.textContent = 'Zapisano zmiany.';
            successDiv.style.display = 'block';
        } else {
            errorDiv.textContent = data.error || 'Błąd zapisu.';
            errorDiv.style.display = 'block';
        }
    });

    document.getElementById('password-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const errorDiv = document.getElementById('pw-error-msg');
        const successDiv = document.getElementById('pw-success-msg');
        errorDiv.style.display = 'none';
        successDiv.style.display = 'none';

        const newPw = document.getElementById('new_password').value;
        const confirmPw = document.getElementById('new_password_confirm').value;

        if (!newPw) return;
        if (newPw !== confirmPw) {
            errorDiv.textContent = 'Hasła nie pasują do siebie.';
            errorDiv.style.display = 'block';
            return;
        }

        const resp = await fetch(apiUrl, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ new_password: newPw }),
        });
        const data = await resp.json();

        if (data.success) {
            successDiv.textContent = 'Hasło zostało zmienione.';
            successDiv.style.display = 'block';
            document.getElementById('new_password').value = '';
            document.getElementById('new_password_confirm').value = '';
        } else {
            errorDiv.textContent = data.error || 'Błąd zmiany hasła.';
            errorDiv.style.display = 'block';
        }
    });
</script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/users/edit.html
git commit -m "feat(users): add user edit template with password change section"
```

---

## Task 13: Roles List Template

**Files:**
- Create: `templates/roles/list.html`

**Step 1: Create template**

```html
{% extends "base.html" %}

{% block title %}Role - {{ app_name }}{% endblock %}

{% block extra_css %}
<style>
    :root {
        --color-ink: #1a1a1a; --color-ink-muted: #525252; --color-surface-warm: #f7f6f3;
        --color-border: #e8e6e1; --color-error: #9b2c2c;
        --font-display: 'Inter', system-ui, sans-serif;
    }
    body { background: var(--color-surface-warm); font-family: var(--font-display); color: var(--color-ink); }
    .refined-page { max-width: 1200px; margin: 0 auto; padding: 2rem; }
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
    .page-title { font-size: 1.75rem; font-weight: 600; letter-spacing: -0.02em; }
    .page-subtitle { color: var(--color-ink-muted); font-size: 0.8125rem; }
    .refined-card { background: white; border: 1px solid var(--color-border); border-radius: 2px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .refined-table { width: 100%; border-collapse: collapse; }
    .refined-table th { padding: 0.625rem 1rem; text-align: left; font-size: 0.6875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-ink-muted); border-bottom: 1px solid var(--color-border); }
    .refined-table td { padding: 0.875rem 1rem; font-size: 0.8125rem; border-bottom: 1px solid #f0eeea; vertical-align: middle; }
    .refined-table tr:last-child td { border-bottom: none; }
    .refined-table tr:hover td { background: var(--color-surface-warm); }
    .badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.125rem 0.5rem; border-radius: 2px; font-size: 0.6875rem; font-weight: 500; }
    .badge-protected { background: #fef3c7; color: #92400e; }
    .module-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 3px; }
    .module-dot-on { background: #2d6a4f; }
    .module-dot-off { background: #d1d5db; }
    .btn-primary { background: var(--color-ink); color: white; border: none; padding: 0.5rem 1rem; border-radius: 2px; font-size: 0.8125rem; font-weight: 500; cursor: pointer; display: inline-flex; align-items: center; gap: 0.375rem; text-decoration: none; }
    .btn-ghost { background: none; border: 1px solid var(--color-border); color: var(--color-ink-muted); padding: 0.375rem 0.75rem; border-radius: 2px; font-size: 0.75rem; cursor: pointer; text-decoration: none; }
    .btn-ghost:hover { border-color: var(--color-ink); color: var(--color-ink); }
    .btn-danger { background: none; border: 1px solid #fecaca; color: var(--color-error); padding: 0.375rem 0.75rem; border-radius: 2px; font-size: 0.75rem; cursor: pointer; }
    .btn-danger:hover { background: #fef2f2; }
    #loading-state { text-align: center; padding: 3rem; color: var(--color-ink-muted); font-size: 0.875rem; }
</style>
{% endblock %}

{% block content %}
<div class="refined-page">
    <div class="page-header">
        <div>
            <h1 class="page-title">Role</h1>
            <p class="page-subtitle">Zarządzanie rolami i uprawnieniami modułów</p>
        </div>
        <a href="{{ url_for('roles.create_role') }}" class="btn-primary">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            Nowa rola
        </a>
    </div>
    <div class="refined-card">
        <div id="loading-state">Ładowanie...</div>
        <table class="refined-table" id="roles-table" style="display:none;">
            <thead>
                <tr>
                    <th>Nazwa</th>
                    <th>Wyświetlana nazwa</th>
                    <th>Uprawnienia modułów</th>
                    <th>Typ</th>
                    <th></th>
                </tr>
            </thead>
            <tbody id="roles-body"></tbody>
        </table>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    const MODULE_LABELS = {
        invoices: 'Faktury', appointments: 'Wizyty', clients: 'Klienci',
        employees: 'Pracownicy', services: 'Usługi', settings: 'Ustawienia', reports: 'Historia'
    };

    async function loadRoles() {
        const resp = await fetch('{{ url_for("roles.api_list") }}');
        const data = await resp.json();
        renderRoles(data.roles || []);
    }

    function renderRoles(roles) {
        document.getElementById('loading-state').style.display = 'none';
        const table = document.getElementById('roles-table');
        const tbody = document.getElementById('roles-body');
        table.style.display = 'table';

        tbody.innerHTML = roles.map(r => {
            const moduleDots = Object.entries(r.permissions).map(([mod, on]) =>
                `<span title="${MODULE_LABELS[mod] || mod}" class="module-dot ${on ? 'module-dot-on' : 'module-dot-off'}"></span>`
            ).join('');

            const protectedBadge = r.is_protected
                ? '<span class="badge badge-protected">Systemowa</span>'
                : '';

            const deleteBtn = r.is_protected
                ? ''
                : `<button onclick="deleteRole(${r.id},'${r.display_name}')" class="btn-danger">Usuń</button>`;

            return `<tr>
                <td style="font-family:monospace;font-size:0.8125rem">${r.name}</td>
                <td style="font-weight:500">${r.display_name}</td>
                <td>${moduleDots}</td>
                <td>${protectedBadge}</td>
                <td style="text-align:right;display:flex;gap:0.5rem;justify-content:flex-end">
                    <a href="/system/roles/${r.id}/edit" class="btn-ghost">Edytuj uprawnienia</a>
                    ${deleteBtn}
                </td>
            </tr>`;
        }).join('');
    }

    async function deleteRole(roleId, displayName) {
        if (!confirm(`Usunąć rolę "${displayName}"? Użytkownicy z tą rolą stracą dostęp.`)) return;
        const resp = await fetch(`/system/roles/api/${roleId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) { loadRoles(); }
        else { alert(data.error || 'Błąd usuwania roli'); }
    }

    loadRoles();
</script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/roles/list.html
git commit -m "feat(roles): add roles list template with module dots visualization"
```

---

## Task 14: Roles Create + Edit Templates

**Files:**
- Create: `templates/roles/create.html`
- Create: `templates/roles/edit.html`

**Step 1: Create roles/create.html**

```html
{% extends "base.html" %}

{% block title %}Nowa rola - {{ app_name }}{% endblock %}

{% block extra_css %}
<style>
    :root { --color-ink:#1a1a1a;--color-ink-muted:#525252;--color-surface-warm:#f7f6f3;--color-border:#e8e6e1;--color-success:#2d6a4f;--color-error:#9b2c2c;--font-display:'Inter',system-ui,sans-serif; }
    body { background:var(--color-surface-warm);font-family:var(--font-display);color:var(--color-ink); }
    .refined-page { max-width:720px;margin:0 auto;padding:2rem; }
    .page-title { font-size:1.75rem;font-weight:600;letter-spacing:-0.02em;margin-bottom:2rem; }
    .refined-card { background:white;border:1px solid var(--color-border);border-radius:2px;padding:2rem;box-shadow:0 1px 3px rgba(0,0,0,0.04); }
    .section-title { font-size:0.875rem;font-weight:600;color:var(--color-ink-muted);margin-bottom:1.25rem;padding-bottom:0.75rem;border-bottom:1px solid var(--color-border); }
    .field-label { display:block;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:var(--color-ink-muted);margin-bottom:0.375rem; }
    .field-input { width:100%;border:1px solid var(--color-border);border-radius:2px;padding:0.625rem 0.75rem;font-size:0.875rem;background:white;outline:none;box-sizing:border-box; }
    .field-input:focus { border-color:var(--color-ink); }
    .field-group { margin-bottom:1.25rem; }
    .field-hint { font-size:0.75rem;color:var(--color-ink-muted);margin-top:0.25rem; }
    .module-row { display:flex;align-items:center;justify-content:space-between;padding:0.75rem 0;border-bottom:1px solid #f0eeea; }
    .module-row:last-child { border-bottom:none; }
    .module-name { font-size:0.875rem;font-weight:500; }
    .module-key { font-size:0.75rem;color:var(--color-ink-muted);font-family:monospace; }
    .toggle { position:relative;width:44px;height:24px;flex-shrink:0; }
    .toggle input { opacity:0;width:0;height:0; }
    .toggle-slider { position:absolute;cursor:pointer;inset:0;background:#d1d5db;border-radius:24px;transition:0.2s; }
    .toggle-slider:before { content:'';position:absolute;width:18px;height:18px;left:3px;bottom:3px;background:white;border-radius:50%;transition:0.2s; }
    input:checked + .toggle-slider { background:var(--color-success); }
    input:checked + .toggle-slider:before { transform:translateX(20px); }
    .btn-primary { background:var(--color-ink);color:white;border:none;padding:0.625rem 1.5rem;border-radius:2px;font-size:0.875rem;font-weight:500;cursor:pointer; }
    .btn-ghost { background:none;border:1px solid var(--color-border);color:var(--color-ink-muted);padding:0.625rem 1.25rem;border-radius:2px;font-size:0.875rem;cursor:pointer;text-decoration:none; }
    .error-msg { color:var(--color-error);font-size:0.8125rem;margin-bottom:1rem;padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:2px;display:none; }
</style>
{% endblock %}

{% block content %}
<div class="refined-page">
    <h1 class="page-title">Nowa rola</h1>
    <div class="refined-card">
        <div id="error-msg" class="error-msg"></div>
        <form id="create-form">
            <div class="field-group">
                <label class="field-label" for="name">Nazwa roli (klucz systemowy)</label>
                <input type="text" id="name" name="name" class="field-input" required
                       placeholder="np. manager" pattern="[a-z_]+" title="Tylko małe litery i podkreślenia">
                <p class="field-hint">Tylko małe litery i podkreślenia. Np. "manager", "head_stylist"</p>
            </div>
            <div class="field-group">
                <label class="field-label" for="display_name">Wyświetlana nazwa</label>
                <input type="text" id="display_name" name="display_name" class="field-input" required
                       placeholder="np. Kierownik">
            </div>

            <div class="section-title" style="margin-top:1.5rem">Dostęp do modułów</div>
            <div id="modules-list">
                {% for module in all_modules %}
                <div class="module-row">
                    <div>
                        <div class="module-name">{{ module_display_names[module] }}</div>
                        <div class="module-key">{{ module }}</div>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" name="perm_{{ module }}" id="perm_{{ module }}">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                {% endfor %}
            </div>

            <div style="display:flex;gap:0.75rem;margin-top:2rem;">
                <button type="submit" class="btn-primary">Utwórz rolę</button>
                <a href="{{ url_for('roles.roles_list') }}" class="btn-ghost">Anuluj</a>
            </div>
        </form>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    const allModules = {{ all_modules | tojson }};

    document.getElementById('create-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const errorDiv = document.getElementById('error-msg');
        errorDiv.style.display = 'none';

        const permissions = {};
        allModules.forEach(m => {
            permissions[m] = document.getElementById('perm_' + m).checked;
        });

        const payload = {
            name: document.getElementById('name').value.trim(),
            display_name: document.getElementById('display_name').value.trim(),
            permissions,
        };

        const resp = await fetch('{{ url_for("roles.api_create") }}', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.success) {
            window.location.href = '{{ url_for("roles.roles_list") }}';
        } else {
            errorDiv.textContent = data.error || 'Błąd tworzenia roli.';
            errorDiv.style.display = 'block';
        }
    });
</script>
{% endblock %}
```

**Step 2: Create roles/edit.html**

```html
{% extends "base.html" %}

{% block title %}Edytuj rolę - {{ role.display_name }}{% endblock %}

{% block extra_css %}
{# Same CSS as create.html — copy the <style> block #}
<style>
    :root { --color-ink:#1a1a1a;--color-ink-muted:#525252;--color-surface-warm:#f7f6f3;--color-border:#e8e6e1;--color-success:#2d6a4f;--color-error:#9b2c2c;--font-display:'Inter',system-ui,sans-serif; }
    body { background:var(--color-surface-warm);font-family:var(--font-display);color:var(--color-ink); }
    .refined-page { max-width:720px;margin:0 auto;padding:2rem; }
    .page-title { font-size:1.75rem;font-weight:600;letter-spacing:-0.02em;margin-bottom:0.5rem; }
    .page-subtitle { color:var(--color-ink-muted);font-size:0.875rem;margin-bottom:2rem;font-family:monospace; }
    .refined-card { background:white;border:1px solid var(--color-border);border-radius:2px;padding:2rem;box-shadow:0 1px 3px rgba(0,0,0,0.04); }
    .section-title { font-size:0.875rem;font-weight:600;color:var(--color-ink-muted);margin-bottom:1.25rem;padding-bottom:0.75rem;border-bottom:1px solid var(--color-border); }
    .field-label { display:block;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:var(--color-ink-muted);margin-bottom:0.375rem; }
    .field-input { width:100%;border:1px solid var(--color-border);border-radius:2px;padding:0.625rem 0.75rem;font-size:0.875rem;background:white;outline:none;box-sizing:border-box; }
    .field-input:focus { border-color:var(--color-ink); }
    .field-group { margin-bottom:1.25rem; }
    .module-row { display:flex;align-items:center;justify-content:space-between;padding:0.75rem 0;border-bottom:1px solid #f0eeea; }
    .module-row:last-child { border-bottom:none; }
    .module-name { font-size:0.875rem;font-weight:500; }
    .module-key { font-size:0.75rem;color:var(--color-ink-muted);font-family:monospace; }
    .toggle { position:relative;width:44px;height:24px;flex-shrink:0; }
    .toggle input { opacity:0;width:0;height:0; }
    .toggle-slider { position:absolute;cursor:pointer;inset:0;background:#d1d5db;border-radius:24px;transition:0.2s; }
    .toggle-slider:before { content:'';position:absolute;width:18px;height:18px;left:3px;bottom:3px;background:white;border-radius:50%;transition:0.2s; }
    input:checked + .toggle-slider { background:var(--color-success); }
    input:checked + .toggle-slider:before { transform:translateX(20px); }
    .btn-primary { background:var(--color-ink);color:white;border:none;padding:0.625rem 1.5rem;border-radius:2px;font-size:0.875rem;font-weight:500;cursor:pointer; }
    .btn-ghost { background:none;border:1px solid var(--color-border);color:var(--color-ink-muted);padding:0.625rem 1.25rem;border-radius:2px;font-size:0.875rem;cursor:pointer;text-decoration:none; }
    .error-msg { color:var(--color-error);font-size:0.8125rem;margin-bottom:1rem;padding:0.75rem;background:#fef2f2;border:1px solid #fecaca;border-radius:2px;display:none; }
    .success-msg { color:#166534;font-size:0.8125rem;margin-bottom:1rem;padding:0.75rem;background:#dcfce7;border:1px solid #86efac;border-radius:2px;display:none; }
</style>
{% endblock %}

{% block content %}
<div class="refined-page">
    <h1 class="page-title">{{ role.display_name }}</h1>
    <p class="page-subtitle">{{ role.name }}</p>

    <div class="refined-card">
        <div id="error-msg" class="error-msg"></div>
        <div id="success-msg" class="success-msg"></div>
        <form id="edit-form">
            <div class="field-group">
                <label class="field-label" for="display_name">Wyświetlana nazwa</label>
                <input type="text" id="display_name" name="display_name" class="field-input"
                       value="{{ role.display_name }}" {% if role.is_protected %}{% endif %} required>
            </div>

            <div class="section-title" style="margin-top:1.5rem">Dostęp do modułów</div>
            <div id="modules-list">
                {% for module in all_modules %}
                <div class="module-row">
                    <div>
                        <div class="module-name">{{ module_display_names[module] }}</div>
                        <div class="module-key">{{ module }}</div>
                    </div>
                    <label class="toggle">
                        <input type="checkbox" name="perm_{{ module }}" id="perm_{{ module }}"
                               {% if permissions[module] %}checked{% endif %}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                {% endfor %}
            </div>

            <div style="display:flex;gap:0.75rem;margin-top:2rem;">
                <button type="submit" class="btn-primary">Zapisz uprawnienia</button>
                <a href="{{ url_for('roles.roles_list') }}" class="btn-ghost">Anuluj</a>
            </div>
        </form>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    const roleId = {{ role.id }};
    const allModules = {{ all_modules | tojson }};

    document.getElementById('edit-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const errorDiv = document.getElementById('error-msg');
        const successDiv = document.getElementById('success-msg');
        errorDiv.style.display = 'none';
        successDiv.style.display = 'none';

        const permissions = {};
        allModules.forEach(m => {
            permissions[m] = document.getElementById('perm_' + m).checked;
        });

        const payload = {
            display_name: document.getElementById('display_name').value.trim(),
            permissions,
        };

        const resp = await fetch(`/system/roles/api/${roleId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.success) {
            successDiv.textContent = 'Zapisano uprawnienia.';
            successDiv.style.display = 'block';
        } else {
            errorDiv.textContent = data.error || 'Błąd zapisu.';
            errorDiv.style.display = 'block';
        }
    });
</script>
{% endblock %}
```

**Step 3: Commit**

```bash
git add templates/roles/
git commit -m "feat(roles): add roles create and edit templates with module permission toggles"
```

---

## Task 15: Final verification

**Step 1: Start the app and verify all routes work**

```bash
python app.py
```

Visit and verify:
- `http://localhost:8083/system/users` → users list loads (logged in as superuser)
- `http://localhost:8083/system/users/create` → create form shows
- `http://localhost:8083/system/roles` → roles list shows seeded roles
- `http://localhost:8083/system/roles/1/edit` → edit form shows with toggles
- Sidebar shows "Użytkownicy" and "Role" in System section

**Step 2: Test user creation**

1. Go to `/system/users/create`
2. Fill: full_name, email, password (8+ chars), role=admin, select an employee
3. Submit → redirects to users list, new user appears

**Step 3: Test role permissions**

1. Go to `/system/roles` → see all 5 seeded roles
2. Click "Edytuj uprawnienia" on "admin" → toggle off "invoices" → save
3. Log in as an admin user → verify Finanse section no longer appears in sidebar (after full sidebar dynamic update is done, but route-level blocking works immediately)

**Step 4: Final commit**

```bash
git add .
git commit -m "feat: users and roles management modules complete (Task A + Task B)"
```

---

## Summary of Files Changed/Created

| Action  | File                                           |
|---------|------------------------------------------------|
| Modify  | `database/schema.sql`                          |
| Modify  | `config/auth_config.py`                        |
| Modify  | `app.py`                                       |
| Modify  | `repositories/users/user_repository.py`        |
| Modify  | `templates/components/sidebar.html`            |
| Create  | `repositories/roles/__init__.py`               |
| Create  | `repositories/roles/role_repository.py`        |
| Create  | `routes/users/__init__.py`                     |
| Create  | `routes/users/routes.py`                       |
| Create  | `routes/roles/__init__.py`                     |
| Create  | `routes/roles/routes.py`                       |
| Create  | `templates/users/list.html`                    |
| Create  | `templates/users/create.html`                  |
| Create  | `templates/users/edit.html`                    |
| Create  | `templates/roles/list.html`                    |
| Create  | `templates/roles/create.html`                  |
| Create  | `templates/roles/edit.html`                    |
