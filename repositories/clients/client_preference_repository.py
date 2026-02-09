"""
Repository dla operacji na preferencjach klientów (client_preferences)
"""
import sqlite3
from typing import List, Optional
from datetime import datetime
from config.database import get_db_connection
from database.models import ClientPreference


class ClientPreferenceRepository:
    """Repository do zarządzania preferencjami klientów (preferowani pracownicy)"""

    def row_to_preference(self, row: sqlite3.Row) -> Optional[ClientPreference]:
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
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

    def create(self, pref: ClientPreference) -> int:
        """Utwórz preferencję klienta"""
        query = """
            INSERT INTO client_preferences (
                client_id, preferred_employee_id, service_id, service_category, notes
            ) VALUES (?, ?, ?, ?, ?)
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
            conn.commit()
            return cursor.lastrowid

    def update(self, pref_id: int, preferred_employee_id: int,
               notes: Optional[str] = None) -> bool:
        """Zaktualizuj preferencję"""
        query = """
            UPDATE client_preferences
            SET preferred_employee_id = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (preferred_employee_id, notes, pref_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, pref_id: int) -> bool:
        """Usuń preferencję"""
        query = "DELETE FROM client_preferences WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (pref_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_preferences_for_client(self, client_id: int) -> List[sqlite3.Row]:
        """Pobierz wszystkie preferencje klienta z danymi pracownika i usługi"""
        query = """
            SELECT
                cp.*,
                e.first_name || ' ' || e.last_name as employee_name,
                e.position as employee_position,
                s.name as service_name,
                s.category as service_category_from_service
            FROM client_preferences cp
            JOIN employees e ON e.id = cp.preferred_employee_id
            LEFT JOIN services s ON s.id = cp.service_id
            WHERE cp.client_id = ?
            ORDER BY cp.service_category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            return cursor.fetchall()

    def get_suggested_employee(self, client_id: int, service_id: Optional[int] = None,
                                category: Optional[str] = None) -> Optional[sqlite3.Row]:
        """Znajdź preferowanego pracownika dla klienta i usługi/kategorii.

        Priorytet: dokładne dopasowanie usługi > dopasowanie kategorii > brak preferencji.
        """
        # Najpierw szukaj po konkretnej usłudze
        if service_id:
            query = """
                SELECT cp.*, e.first_name || ' ' || e.last_name as employee_name
                FROM client_preferences cp
                JOIN employees e ON e.id = cp.preferred_employee_id AND e.is_active = 1
                WHERE cp.client_id = ? AND cp.service_id = ?
                LIMIT 1
            """
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (client_id, service_id))
                result = cursor.fetchone()
                if result:
                    return result

        # Potem szukaj po kategorii
        if category:
            query = """
                SELECT cp.*, e.first_name || ' ' || e.last_name as employee_name
                FROM client_preferences cp
                JOIN employees e ON e.id = cp.preferred_employee_id AND e.is_active = 1
                WHERE cp.client_id = ? AND cp.service_category = ? AND cp.service_id IS NULL
                LIMIT 1
            """
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (client_id, category))
                result = cursor.fetchone()
                if result:
                    return result

        return None

    def get_clients_preferring_employee(self, employee_id: int) -> List[sqlite3.Row]:
        """Pobierz klientów, którzy preferują danego pracownika"""
        query = """
            SELECT DISTINCT
                c.id, c.first_name, c.last_name, c.phone, c.email
            FROM client_preferences cp
            JOIN clients c ON c.id = cp.client_id AND c.is_active = 1
            WHERE cp.preferred_employee_id = ?
            ORDER BY c.last_name, c.first_name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchall()
