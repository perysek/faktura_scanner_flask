"""
Repository dla ról i uprawnień modułów
"""
from typing import Any, Optional
from config.database import get_db_connection

# All known modules (must match auth_config.MODULE_PERMISSIONS keys)
ALL_MODULES = ['invoices', 'appointments', 'clients', 'employees', 'services', 'settings', 'reports', 'data_correction', 'data_import', 'absences', 'service_prices']

MODULE_DISPLAY_NAMES = {
    'invoices':         'Faktury / Koszty',
    'appointments':     'Wizyty',
    'clients':          'Klienci',
    'employees':        'Pracownicy',
    'services':         'Usługi',
    'settings':         'Ustawienia',
    'reports':          'Historia / Raporty',
    'data_correction':  'Korekta danych',
    'absences':         'Nieobecnosci',
    'service_prices':   'Ceny usług (historia)',
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
        Zwraca słownik modułów z pełnymi flagami dostępu dla danej roli.
        Przykład: {'invoices': {'has_access': True, 'read_only': False, 'own_data': False}, ...}
        """
        query = ("SELECT module_name, has_access, read_only, own_data, can_edit_price_history "
                 "FROM role_permissions WHERE role_id = %s")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_id,))
            rows = cursor.fetchall()

        db_perms = {
            row['module_name']: {
                'has_access': bool(row['has_access']),
                'read_only': bool(row['read_only']),
                'own_data': bool(row['own_data']),
                'can_edit_price_history': bool(row['can_edit_price_history']),
            }
            for row in rows
        }
        default = {'has_access': False, 'read_only': False, 'own_data': False,
                   'can_edit_price_history': False}
        return {m: db_perms.get(m, dict(default)) for m in ALL_MODULES}

    def set_permissions(self, role_id: int, permissions: dict):
        """
        Ustaw uprawnienia roli.
        permissions = {
            'invoices': {'has_access': True, 'read_only': False, 'own_data': False},
            ...
        }
        Akceptuje też stary format {'invoices': True} dla kompatybilności wstecznej.
        """
        query = """
            INSERT INTO role_permissions
                (role_id, module_name, has_access, read_only, own_data, can_edit_price_history)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (role_id, module_name) DO UPDATE
                SET has_access = EXCLUDED.has_access,
                    read_only  = EXCLUDED.read_only,
                    own_data   = EXCLUDED.own_data,
                    can_edit_price_history = EXCLUDED.can_edit_price_history
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for module in ALL_MODULES:
                val = permissions.get(module, False)
                if isinstance(val, dict):
                    has_access = bool(val.get('has_access', False))
                    read_only = bool(val.get('read_only', False))
                    own_data = bool(val.get('own_data', False))
                    can_edit_price_history = bool(val.get('can_edit_price_history', False))
                else:
                    has_access = bool(val)
                    read_only = False
                    own_data = False
                    can_edit_price_history = False
                cursor.execute(query, (role_id, module, has_access, read_only,
                                       own_data, can_edit_price_history))
            conn.commit()

    def get_permission_flags(self, role_name: str, module_name: str) -> dict:
        """
        Zwraca pełne flagi uprawnień dla pary rola+moduł.
        Przykład: {'has_access': True, 'read_only': False, 'own_data': True}
        """
        query = """
            SELECT rp.has_access, rp.read_only, rp.own_data
            FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = %s AND rp.module_name = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_name, module_name))
            row = cursor.fetchone()
        if row is None:
            from config.auth_config import MODULE_PERMISSIONS
            has_access = role_name in MODULE_PERMISSIONS.get(module_name, [])
            return {'has_access': has_access, 'read_only': False, 'own_data': False}
        return {
            'has_access': bool(row['has_access']),
            'read_only': bool(row['read_only']),
            'own_data': bool(row['own_data']),
        }

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
            # Fall back to static MODULE_PERMISSIONS when DB has no entry for this module
            from config.auth_config import MODULE_PERMISSIONS
            return role_name in MODULE_PERMISSIONS.get(module_name, [])
        return bool(row['has_access'])

    def role_can_edit_price_history(self, role_name: str) -> bool:
        """True if the role may delete/edit service price-history entries.

        Requires BOTH 'services' module access AND the can_edit_price_history
        sub-flag. Used to gate the price-history delete endpoint and UI.
        """
        query = """
            SELECT rp.has_access, rp.can_edit_price_history
            FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = %s AND rp.module_name = 'services'
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (role_name,))
            row = cursor.fetchone()
        if row is None:
            # No DB row yet → only built-in admins get it (matches migration seed)
            return role_name in ('superuser', 'admin')
        return bool(row['has_access']) and bool(row['can_edit_price_history'])

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
        # For modules with no DB row yet, fall back to static MODULE_PERMISSIONS
        from config.auth_config import MODULE_PERMISSIONS
        return {
            m: db_perms[m] if m in db_perms else (role_name in MODULE_PERMISSIONS.get(m, []))
            for m in ALL_MODULES
        }
