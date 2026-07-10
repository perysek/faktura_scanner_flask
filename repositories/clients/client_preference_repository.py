"""
Repository dla operacji na preferencjach klientów (client_preferences)
"""
from typing import Any, List, Optional
from datetime import datetime
from config.database import get_db_connection
from config.admin_view import emp_exclusion_sql
from database.models import ClientPreference
from repositories.db_utils import parse_dt


class ClientPreferenceRepository:
    """Repository do zarządzania preferencjami klientów (preferowani pracownicy)"""

    def row_to_preference(self, row: Any) -> Optional[ClientPreference]:
        """Konwertuj Row na obiekt ClientPreference"""
        if not row:
            return None

        return ClientPreference(
            id=row['id'],
            client_id=row['client_id'],
            preferred_employee_id=row['preferred_employee_id'],
            service_id=row['service_id'],
            service_category=row['service_category'],
            notes=row['notes'],
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at'])
        )

    def create(self, pref: ClientPreference) -> int:
        """Utwórz preferencję klienta"""
        query = """
            INSERT INTO client_preferences (
                client_id, preferred_employee_id, service_id, service_category, notes
            ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                pref.client_id,
                pref.preferred_employee_id,
                pref.service_id,
                pref.service_category,
                pref.notes
            ))
            result_id = cursor.fetchone()["id"]
            conn.commit()
            return result_id

    def update(self, pref_id: int, preferred_employee_id: int,
               notes: Optional[str] = None) -> bool:
        """Zaktualizuj preferencję"""
        query = """
            UPDATE client_preferences
            SET preferred_employee_id = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (preferred_employee_id, notes, pref_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, pref_id: int) -> bool:
        """Usuń preferencję"""
        query = "DELETE FROM client_preferences WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (pref_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_preferences_for_client(self, client_id: int) -> List[Any]:
        """Pobierz wszystkie preferencje klienta z danymi pracownika i usługi"""
        # Widok administratora: hide preference rows pointing at the owner unless ON.
        excl_sql, excl_params = emp_exclusion_sql('cp.preferred_employee_id')
        query = f"""
            SELECT
                cp.*,
                e.first_name || ' ' || e.last_name as employee_name,
                e.position as employee_position,
                s.name as service_name,
                s.category as service_category_from_service
            FROM client_preferences cp
            JOIN employees e ON e.id = cp.preferred_employee_id
            LEFT JOIN services s ON s.id = cp.service_id
            WHERE cp.client_id = %s {excl_sql}
            ORDER BY cp.service_category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id, *excl_params))
            return cursor.fetchall()

    def get_suggested_employee(self, client_id: int, service_id: Optional[int] = None,
                                category: Optional[str] = None) -> Optional[Any]:
        """Znajdź preferowanego pracownika dla klienta i usługi/kategorii.

        Priorytet: dokładne dopasowanie usługi > dopasowanie kategorii > brak preferencji.
        """
        # Widok administratora: never auto-suggest the owner as preferred employee
        # while admin view is OFF (they aren't bookable then, and it would leak them).
        excl_sql, excl_params = emp_exclusion_sql('cp.preferred_employee_id')

        # Najpierw szukaj po konkretnej usłudze
        if service_id:
            query = f"""
                SELECT cp.*, e.first_name || ' ' || e.last_name as employee_name
                FROM client_preferences cp
                JOIN employees e ON e.id = cp.preferred_employee_id AND e.is_active = TRUE
                WHERE cp.client_id = %s AND cp.service_id = %s {excl_sql}
                LIMIT 1
            """
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (client_id, service_id, *excl_params))
                result = cursor.fetchone()
                if result:
                    return result

        # Potem szukaj po kategorii
        if category:
            query = f"""
                SELECT cp.*, e.first_name || ' ' || e.last_name as employee_name
                FROM client_preferences cp
                JOIN employees e ON e.id = cp.preferred_employee_id AND e.is_active = TRUE
                WHERE cp.client_id = %s AND cp.service_category = %s AND cp.service_id IS NULL {excl_sql}
                LIMIT 1
            """
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (client_id, category, *excl_params))
                result = cursor.fetchone()
                if result:
                    return result

        return None

    def get_clients_preferring_employee(self, employee_id: int) -> List[Any]:
        """Pobierz klientów, którzy preferują danego pracownika"""
        excl_sql, excl_params = emp_exclusion_sql('cp.preferred_employee_id')
        query = f"""
            SELECT DISTINCT
                c.id, c.first_name, c.last_name, c.phone, c.email
            FROM client_preferences cp
            JOIN clients c ON c.id = cp.client_id AND c.is_active = TRUE
            WHERE cp.preferred_employee_id = %s {excl_sql}
            ORDER BY c.last_name, c.first_name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, *excl_params))
            return cursor.fetchall()
