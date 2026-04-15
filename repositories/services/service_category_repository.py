"""
Repository dla operacji na kategoriach usług (service_categories)
"""
from typing import Any, List, Optional
from datetime import datetime

from config.database import get_db_connection
from database.models import ServiceCategory


class ServiceCategoryRepository:
    """Repository do zarządzania kategoriami usług salonowych"""

    def row_to_category(self, row: Any) -> ServiceCategory:
        """Konwertuj Row na obiekt ServiceCategory"""
        if not row:
            return None
        return ServiceCategory(
            id=row['id'],
            name=row['name'],
            additional_description=row['additional_description'],
            is_deleted=bool(row['is_deleted']),
            deleted_at=row['deleted_at'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )

    def get_all(self, include_deleted: bool = False) -> List[Any]:
        """Pobierz wszystkie kategorie (domyślnie bez soft-deleted)"""
        if include_deleted:
            query = "SELECT * FROM service_categories ORDER BY name"
        else:
            query = "SELECT * FROM service_categories WHERE is_deleted = FALSE ORDER BY name"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_id(self, category_id: int) -> Optional[Any]:
        """Pobierz kategorię po ID (ignoruje soft-deleted)"""
        query = "SELECT * FROM service_categories WHERE id = %s AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_id,))
            return cursor.fetchone()

    def get_by_name(self, name: str) -> Optional[Any]:
        """Pobierz kategorię po nazwie (ignoruje soft-deleted)"""
        query = "SELECT * FROM service_categories WHERE name = %s AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (name,))
            return cursor.fetchone()

    def create(self, category: ServiceCategory) -> int:
        """Utwórz nową kategorię usług"""
        query = """
            INSERT INTO service_categories (name, additional_description)
            VALUES (%s, %s)
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category.name, category.additional_description))
            result_id = cursor.fetchone()['id']
            conn.commit()
            return result_id

    def update(self, category_id: int, category: ServiceCategory) -> bool:
        """Zaktualizuj kategorię usług"""
        query = """
            UPDATE service_categories
            SET name = %s,
                additional_description = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category.name, category.additional_description, category_id))
            conn.commit()
            return cursor.rowcount > 0

    def soft_delete(self, category_id: int) -> bool:
        """Soft-delete kategorii (oznacz jako usuniętą)"""
        query = """
            UPDATE service_categories
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_id,))
            conn.commit()
            return cursor.rowcount > 0

    def soft_delete_with_services(self, category_id: int, category_name: str) -> int:
        """Soft-delete kategorii WRAZ z powiązanymi usługami.

        Returns: liczba usuniętych usług
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Soft-delete powiązanych usług (matching by category name text)
            cursor.execute(
                """
                UPDATE services
                SET is_deleted = TRUE,
                    deleted_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE category = %s AND is_deleted = FALSE
                """,
                (category_name,)
            )
            deleted_services_count = cursor.rowcount

            # Soft-delete kategorii
            cursor.execute(
                """
                UPDATE service_categories
                SET is_deleted = TRUE,
                    deleted_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND is_deleted = FALSE
                """,
                (category_id,)
            )
            conn.commit()
            return deleted_services_count

    def get_service_count(self, category_name: str) -> int:
        """Policz usługi przypisane do kategorii (po nazwie, nie soft-deleted)"""
        query = """
            SELECT COUNT(*) as cnt
            FROM services
            WHERE category = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_name,))
            return cursor.fetchone()['cnt']

    def get_all_with_service_counts(self) -> List[dict]:
        """Pobierz wszystkie aktywne kategorie wraz z liczbą powiązanych usług"""
        query = """
            SELECT
                sc.id,
                sc.name,
                sc.additional_description,
                sc.is_deleted,
                sc.deleted_at,
                sc.created_at,
                sc.updated_at,
                COUNT(s.id) AS service_count
            FROM service_categories sc
            LEFT JOIN services s
                ON s.category = sc.name AND s.is_deleted = FALSE
            WHERE sc.is_deleted = FALSE
            GROUP BY sc.id, sc.name, sc.additional_description,
                     sc.is_deleted, sc.deleted_at, sc.created_at, sc.updated_at
            ORDER BY sc.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'additional_description': r['additional_description'],
                    'service_count': r['service_count'],
                    'created_at': r['created_at'].isoformat() if r['created_at'] else None,
                    'updated_at': r['updated_at'].isoformat() if r['updated_at'] else None,
                }
                for r in rows
            ]

    def get_services_for_category(self, category_name: str) -> List[dict]:
        """Pobierz usługi przypisane do kategorii (do podglądu w modalu)"""
        query = """
            SELECT id, name, price, duration_minutes, service_type, is_active
            FROM services
            WHERE category = %s AND is_deleted = FALSE
            ORDER BY name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_name,))
            rows = cursor.fetchall()
            return [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'price': float(r['price']),
                    'duration_minutes': r['duration_minutes'],
                    'service_type': r['service_type'],
                    'is_active': bool(r['is_active']),
                }
                for r in rows
            ]

    def name_exists(self, name: str, exclude_id: Optional[int] = None) -> bool:
        """Sprawdź czy kategoria o podanej nazwie już istnieje"""
        if exclude_id:
            query = """
                SELECT 1 FROM service_categories
                WHERE name = %s AND is_deleted = FALSE AND id != %s
            """
            params = (name, exclude_id)
        else:
            query = "SELECT 1 FROM service_categories WHERE name = %s AND is_deleted = FALSE"
            params = (name,)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone() is not None
