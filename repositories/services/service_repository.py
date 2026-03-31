"""
Repository dla operacji na usługach (services)
"""
from typing import Any, List, Optional
from datetime import datetime
from repositories.db_utils import parse_dt
from config.database import get_db_connection
from database.models import Service


class ServiceRepository:
    """Repository do zarządzania usługami salonowymi"""

    def row_to_service(self, row: Any) -> Service:
        """Konwertuj Row na obiekt Service"""
        if not row:
            return None

        return Service(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            category=row['category'],
            duration_minutes=row['duration_minutes'],
            price=float(row['price']),
            currency=row['currency'],
            service_type=row['service_type'] if 'service_type' in row.keys() else 'main',
            is_active=bool(row['is_active']),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at'])
        )

    def create(self, service: Service) -> int:
        """Utwórz nową usługę"""
        query = """
            INSERT INTO services (
                name, description, category, duration_minutes, price, currency, service_type, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                service.name,
                service.description,
                service.category,
                service.duration_minutes,
                service.price,
                service.currency,
                service.service_type,
                service.is_active
            ))
            result_id = cursor.fetchone()["id"]
            conn.commit()
            return result_id

    def get_by_id(self, service_id: int) -> Optional[Any]:
        """Pobierz usługę po ID"""
        query = "SELECT * FROM services WHERE id = %s AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_id,))
            return cursor.fetchone()

    def get_all(self, active_only: bool = True) -> List[Any]:
        """Pobierz wszystkie usługi"""
        if active_only:
            query = "SELECT * FROM services WHERE is_active = TRUE AND is_deleted = FALSE ORDER BY category, name"
        else:
            query = "SELECT * FROM services WHERE is_deleted = FALSE ORDER BY category, name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_category(self, category: str, active_only: bool = True) -> List[Any]:
        """Pobierz usługi według kategorii"""
        if active_only:
            query = "SELECT * FROM services WHERE category = %s AND is_active = TRUE AND is_deleted = FALSE ORDER BY name"
        else:
            query = "SELECT * FROM services WHERE category = %s AND is_deleted = FALSE ORDER BY name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category,))
            return cursor.fetchall()

    def search(self, query: str, active_only: bool = True) -> List[Any]:
        """Wyszukaj usługi po nazwie lub kategorii"""
        search_pattern = f"%{query}%"
        if active_only:
            sql = """
                SELECT * FROM services
                WHERE (name ILIKE %s OR category ILIKE %s OR description ILIKE %s)
                AND is_active = TRUE AND is_deleted = FALSE
                ORDER BY category, name
            """
        else:
            sql = """
                SELECT * FROM services
                WHERE (name ILIKE %s OR category ILIKE %s OR description ILIKE %s)
                AND is_deleted = FALSE
                ORDER BY category, name
            """

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (search_pattern, search_pattern, search_pattern))
            return cursor.fetchall()

    def update(self, service_id: int, service: Service) -> bool:
        """Zaktualizuj usługę"""
        query = """
            UPDATE services
            SET name = %s,
                description = %s,
                category = %s,
                duration_minutes = %s,
                price = %s,
                currency = %s,
                service_type = %s,
                is_active = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                service.name,
                service.description,
                service.category,
                service.duration_minutes,
                service.price,
                service.currency,
                service.service_type,
                service.is_active,
                service_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, service_id: int) -> bool:
        """Soft-delete uslugi (oznacz jako usunietą)"""
        query = "UPDATE services SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP WHERE id = %s AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_id,))
            conn.commit()
            return cursor.rowcount > 0

    def restore(self, service_id: int) -> bool:
        """Przywroc soft-deleted usluge"""
        query = "UPDATE services SET is_deleted = FALSE, deleted_at = NULL WHERE id = %s AND is_deleted = TRUE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_id,))
            conn.commit()
            return cursor.rowcount > 0

    def deactivate(self, service_id: int) -> bool:
        """Dezaktywuj usługę"""
        query = "UPDATE services SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_id,))
            conn.commit()
            return cursor.rowcount > 0

    def activate(self, service_id: int) -> bool:
        """Aktywuj usługę"""
        query = "UPDATE services SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_categories(self) -> List[str]:
        """Pobierz listę wszystkich kategorii"""
        query = "SELECT DISTINCT category FROM services WHERE is_deleted = FALSE ORDER BY category"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [row['category'] for row in cursor.fetchall()]

    def get_price_range(self) -> tuple:
        """Pobierz zakres cen (min, max)"""
        query = "SELECT MIN(price) as min_price, MAX(price) as max_price FROM services WHERE is_active = TRUE AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return (float(row['min_price']) if row['min_price'] else 0,
                   float(row['max_price']) if row['max_price'] else 0)

    def get_statistics(self) -> dict:
        """Pobierz statystyki usług"""
        query = """
            SELECT
                COUNT(*) as total_services,
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_services,
                COUNT(DISTINCT category) as total_categories,
                AVG(CASE WHEN is_active = TRUE THEN price END) as avg_price,
                AVG(CASE WHEN is_active = TRUE THEN duration_minutes END) as avg_duration
            FROM services
            WHERE is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            return {
                'total_services': row['total_services'],
                'active_services': row['active_services'],
                'inactive_services': row['total_services'] - row['active_services'],
                'total_categories': row['total_categories'],
                'avg_price': float(row['avg_price']) if row['avg_price'] else 0,
                'avg_duration': int(row['avg_duration']) if row['avg_duration'] else 0
            }

    def get_by_price_range(self, min_price: float, max_price: float) -> List[Any]:
        """Pobierz usługi w danym zakresie cen"""
        query = """
            SELECT * FROM services
            WHERE is_active = TRUE AND is_deleted = FALSE AND price BETWEEN %s AND %s
            ORDER BY price, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (min_price, max_price))
            return cursor.fetchall()

    def get_by_duration_range(self, min_minutes: int, max_minutes: int) -> List[Any]:
        """Pobierz usługi w danym zakresie czasu trwania"""
        query = """
            SELECT * FROM services
            WHERE is_active = TRUE AND is_deleted = FALSE AND duration_minutes BETWEEN %s AND %s
            ORDER BY duration_minutes, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (min_minutes, max_minutes))
            return cursor.fetchall()

    def get_main_services(self, active_only: bool = True) -> List[Any]:
        """Pobierz usługi główne (service_type='main')"""
        active_filter = "AND is_active = TRUE" if active_only else ""
        query = f"""
            SELECT * FROM services
            WHERE service_type = 'main' AND is_deleted = FALSE {active_filter}
            ORDER BY category, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_addon_services(self, active_only: bool = True) -> List[Any]:
        """Pobierz mikrousługi (service_type='addon')"""
        active_filter = "AND is_active = TRUE" if active_only else ""
        query = f"""
            SELECT * FROM services
            WHERE service_type = 'addon' AND is_deleted = FALSE {active_filter}
            ORDER BY category, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_type(self, service_type: str, active_only: bool = True) -> List[Any]:
        """Pobierz usługi według typu ('main' lub 'addon')"""
        active_filter = "AND is_active = TRUE" if active_only else ""
        query = f"""
            SELECT * FROM services
            WHERE service_type = %s AND is_deleted = FALSE {active_filter}
            ORDER BY category, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_type,))
            return cursor.fetchall()
