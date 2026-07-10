"""
Repository dla operacji na przypisaniach usług do pracowników (employee_services)
"""
from decimal import Decimal
from typing import Any, List, Optional
from datetime import datetime
from repositories.db_utils import parse_dt
import psycopg2
from config.database import get_db_connection
from config.admin_view import emp_exclusion_sql_inline
from database.models import EmployeeService


class EmployeeServiceRepository:
    """Repository do zarządzania przypisaniami usług do pracowników z indywidualnym cenowaniem"""

    def row_to_employee_service(self, row: Any) -> Optional[EmployeeService]:
        """Konwertuj Row na obiekt EmployeeService"""
        if not row:
            return None

        return EmployeeService(
            id=row['id'],
            employee_id=row['employee_id'],
            service_id=row['service_id'],
            custom_price=Decimal(str(row['custom_price'])) if row['custom_price'] is not None else None,
            commission_rate=Decimal(str(row['commission_rate'])) if row['commission_rate'] is not None else None,
            duration_override=row['duration_override'],
            skill_rating=row['skill_rating'] if 'skill_rating' in row.keys() else None,
            is_active=bool(row['is_active']),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at'])
        )

    def create(self, es: EmployeeService) -> int:
        """Przypisz usługę do pracownika"""
        query = """
            INSERT INTO employee_services (
                employee_id, service_id, custom_price, commission_rate,
                duration_override, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                es.employee_id,
                es.service_id,
                str(es.custom_price) if es.custom_price is not None else None,
                str(es.commission_rate) if es.commission_rate is not None else None,
                es.duration_override,
                es.is_active
            ))
            result_id = cursor.fetchone()["id"]
            conn.commit()
            return result_id

    def update(self, es_id: int, custom_price: Optional[Decimal] = None,
               commission_rate: Optional[Decimal] = None,
               duration_override: Optional[int] = None,
               skill_rating: Optional[int] = None,
               is_active: Optional[bool] = None) -> bool:
        """Zaktualizuj przypisanie usługi do pracownika"""
        updates = []
        params = []

        if custom_price is not None:
            updates.append("custom_price = %s")
            params.append(str(custom_price))
        if commission_rate is not None:
            updates.append("commission_rate = %s")
            params.append(str(commission_rate))
        if duration_override is not None:
            updates.append("duration_override = %s")
            params.append(duration_override)
        if skill_rating is not None:
            updates.append("skill_rating = %s")
            params.append(skill_rating)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(es_id)

        query = f"UPDATE employee_services SET {', '.join(updates)} WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, es_id: int) -> bool:
        """Usuń przypisanie usługi do pracownika"""
        query = "DELETE FROM employee_services WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (es_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_by_id(self, es_id: int) -> Optional[Any]:
        """Pobierz przypisanie po ID"""
        query = "SELECT * FROM employee_services WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (es_id,))
            return cursor.fetchone()

    def get_services_for_employee(self, employee_id: int, active_only: bool = True) -> List[Any]:
        """Pobierz usługi przypisane do pracownika z efektywnym cenowaniem.

        Zwraca JOIN z tabelą services + employees dla rozwiązania łańcucha COALESCE:
        - effective_price = COALESCE(es.custom_price, s.price)
        - effective_commission = COALESCE(es.commission_rate, e.commission_rate, 0)
        - effective_duration = COALESCE(es.duration_override, s.duration_minutes)
        """
        active_filter = "AND es.is_active = TRUE AND s.is_active = TRUE" if active_only else ""
        query = f"""
            SELECT
                es.*,
                s.name as service_name,
                s.category as service_category,
                s.price as default_price,
                s.duration_minutes as default_duration,
                s.service_type,
                s.currency,
                e.commission_rate as employee_default_commission,
                COALESCE(es.custom_price, s.price) as effective_price,
                COALESCE(es.commission_rate, e.commission_rate, 0) as effective_commission,
                COALESCE(es.duration_override, s.duration_minutes) as effective_duration
            FROM employee_services es
            JOIN services s ON s.id = es.service_id
            JOIN employees e ON e.id = es.employee_id
            WHERE es.employee_id = %s {active_filter} {emp_exclusion_sql_inline('es.employee_id')}
            ORDER BY s.service_type, s.category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchall()

    def get_employees_for_service(self, service_id: int, active_only: bool = True) -> List[Any]:
        """Pobierz pracowników mogących wykonać daną usługę"""
        active_filter = "AND es.is_active = TRUE AND e.is_active = TRUE" if active_only else ""
        query = f"""
            SELECT
                es.*,
                e.first_name,
                e.last_name,
                e.position,
                e.work_schedule,
                e.commission_rate as employee_default_commission,
                s.price as default_price,
                s.duration_minutes as default_duration,
                COALESCE(es.custom_price, s.price) as effective_price,
                COALESCE(es.commission_rate, e.commission_rate, 0) as effective_commission,
                COALESCE(es.duration_override, s.duration_minutes) as effective_duration
            FROM employee_services es
            JOIN employees e ON e.id = es.employee_id
            JOIN services s ON s.id = es.service_id
            WHERE es.service_id = %s {active_filter} {emp_exclusion_sql_inline('e.id')}
            ORDER BY e.last_name, e.first_name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (service_id,))
            return cursor.fetchall()

    def get_effective_pricing(self, employee_id: int, service_id: int) -> Optional[Any]:
        """Pobierz efektywne cenowanie dla pary pracownik-usługa.

        Rozwiązuje łańcuch COALESCE dla ceny, prowizji i czasu trwania.
        Zwraca None jeśli pracownik nie może wykonać tej usługi.
        """
        query = """
            SELECT
                es.*,
                s.name as service_name,
                s.price as default_price,
                s.duration_minutes as default_duration,
                s.service_type,
                e.commission_rate as employee_default_commission,
                COALESCE(es.custom_price, s.price) as effective_price,
                COALESCE(es.commission_rate, e.commission_rate, 0) as effective_commission,
                COALESCE(es.duration_override, s.duration_minutes) as effective_duration
            FROM employee_services es
            JOIN services s ON s.id = es.service_id
            JOIN employees e ON e.id = es.employee_id
            WHERE es.employee_id = %s AND es.service_id = %s AND es.is_active = TRUE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, service_id))
            return cursor.fetchone()

    def can_perform(self, employee_id: int, service_id: int) -> bool:
        """Sprawdź czy pracownik może wykonać daną usługę"""
        query = """
            SELECT COUNT(*) as cnt FROM employee_services
            WHERE employee_id = %s AND service_id = %s AND is_active = TRUE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, service_id))
            return cursor.fetchone()['cnt'] > 0

    def get_services_with_dual_ratings(self, employee_id: int) -> List[dict]:
        """Pobierz przypisane usługi z oceną manualną i wyliczoną z wizyt klientów.

        Każdy wiersz zawiera:
          - es_id, service_id, service_name, service_category, service_type
          - skill_rating      — ręczna ocena 1-5 (NULL jeśli nieustawiona)
          - avg_client_rating — średnia z satisfaction_score ukończonych wizyt (NULL jeśli brak)
          - scored_visits     — liczba wizyt z oceną
        """
        query = """
            SELECT
                es.id                                                   AS es_id,
                s.id                                                    AS service_id,
                s.name                                                  AS service_name,
                s.category                                              AS service_category,
                s.service_type,
                es.skill_rating,
                ROUND(AVG(a.satisfaction_score)::numeric, 2)            AS avg_client_rating,
                COUNT(a.satisfaction_score)                             AS scored_visits
            FROM employee_services es
            JOIN services s ON s.id = es.service_id
            LEFT JOIN appointment_services aps ON aps.service_id = es.service_id
            LEFT JOIN appointments a
                ON  a.id          = aps.appointment_id
                AND a.employee_id = %(eid)s
                AND a.status      = 'completed'
                AND a.satisfaction_score IS NOT NULL
            WHERE es.employee_id = %(eid)s
              AND es.is_active   = TRUE
              AND s.is_active    = TRUE
            GROUP BY es.id, s.id, s.name, s.category, s.service_type
            ORDER BY s.service_type, s.category, s.name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {'eid': employee_id})
            rows = cursor.fetchall()
        return [
            {
                'es_id':             row['es_id'],
                'service_id':        row['service_id'],
                'service_name':      row['service_name'],
                'service_category':  row['service_category'],
                'service_type':      row['service_type'],
                'skill_rating':      row['skill_rating'],
                'avg_client_rating': float(row['avg_client_rating']) if row['avg_client_rating'] is not None else None,
                'scored_visits':     row['scored_visits'],
            }
            for row in rows
        ]

    def bulk_assign_services(self, employee_id: int, service_ids: List[int]) -> int:
        """Przypisz wiele usług do pracownika (pomija istniejące)"""
        count = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for service_id in service_ids:
                try:
                    cursor.execute(
                        "INSERT INTO employee_services (employee_id, service_id) VALUES (%s, %s)",
                        (employee_id, service_id)
                    )
                    count += 1
                except psycopg2.errors.UniqueViolation:
                    # Para już istnieje — pomijamy
                    pass
            conn.commit()
        return count
