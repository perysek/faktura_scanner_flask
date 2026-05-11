"""
Repository dla ról i uprawnień modułów
"""
from typing import Any, Optional
from config.database import get_db_connection

# All known modules (must match auth_config.MODULE_PERMISSIONS keys)
ALL_MODULES = ['invoices', 'appointments', 'clients', 'employees', 'services', 'settings', 'reports', 'data_correction', 'absences']

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
            # Fall back to static MODULE_PERMISSIONS when DB has no entry for this module
            from config.auth_config import MODULE_PERMISSIONS
            return role_name in MODULE_PERMISSIONS.get(module_name, [])
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
        # For modules with no DB row yet, fall back to static MODULE_PERMISSIONS
        from config.auth_config import MODULE_PERMISSIONS
        return {
            m: db_perms[m] if m in db_perms else (role_name in MODULE_PERMISSIONS.get(m, []))
            for m in ALL_MODULES
        }
