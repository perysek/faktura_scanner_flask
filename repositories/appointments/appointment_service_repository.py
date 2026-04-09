"""
Repository dla operacji na usługach przypisanych do wizyt (appointment_services)
"""
from decimal import Decimal
from typing import Any, List, Optional
from datetime import datetime
from config.database import get_db_connection, safe_commit
from database.models import AppointmentService
from repositories.db_utils import parse_dt


class AppointmentServiceRepository:
    """Repository do zarządzania usługami w ramach wizyt (główne + mikrousługi)"""

    def row_to_appointment_service(self, row: Any) -> Optional[AppointmentService]:
        """Konwertuj Row na obiekt AppointmentService"""
        if not row:
            return None

        return AppointmentService(
            id=row['id'],
            appointment_id=row['appointment_id'],
            service_id=row['service_id'],
            price_charged=Decimal(str(row['price_charged'])),
            duration_minutes=row['duration_minutes'],
            commission_rate=Decimal(str(row['commission_rate'])) if row['commission_rate'] is not None else Decimal('0'),
            commission_amount=Decimal(str(row['commission_amount'])) if row['commission_amount'] is not None else Decimal('0'),
            is_addon=bool(row['is_addon']),
            added_at=parse_dt(row['added_at'])
        )

    def add_service(self, appt_svc: AppointmentService) -> int:
        """Dodaj usługę do wizyty (główna lub dodatek)"""
        query = """
            INSERT INTO appointment_services (
                appointment_id, service_id, price_charged, duration_minutes,
                commission_rate, commission_amount, is_addon, added_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                appt_svc.appointment_id,
                appt_svc.service_id,
                str(appt_svc.price_charged),
                appt_svc.duration_minutes,
                str(appt_svc.commission_rate),
                str(appt_svc.commission_amount),
                bool(appt_svc.is_addon),
            ))
            result_id = cursor.fetchone()["id"]
            safe_commit(conn)
            return result_id

    def add_addon_service(self, appt_svc: AppointmentService) -> int:
        """Dodaj mikrousługę do wizyty (w trakcie — status=in_progress)"""
        query = """
            INSERT INTO appointment_services (
                appointment_id, service_id, price_charged, duration_minutes,
                commission_rate, commission_amount, is_addon, added_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                appt_svc.appointment_id,
                appt_svc.service_id,
                str(appt_svc.price_charged),
                appt_svc.duration_minutes,
                str(appt_svc.commission_rate),
                str(appt_svc.commission_amount),
                True,  # add_addon_service is always is_addon=True
            ))
            result_id = cursor.fetchone()["id"]
            safe_commit(conn)
            return result_id

    def get_all_for_appointment(self, appointment_id: int) -> List[Any]:
        """Pobierz wszystkie usługi (główne + mikrousługi) dla wizyty"""
        query = """
            SELECT
                aps.*,
                s.name as service_name,
                s.category as service_category,
                s.service_type
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id = %s
            ORDER BY aps.is_addon, aps.id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchall()

    def get_all_for_appointments_batch(self, appointment_ids: List[int]) -> dict:
        """Pobierz usługi dla wielu wizyt jednym zapytaniem. Zwraca dict {appointment_id: [services]}"""
        if not appointment_ids:
            return {}
        placeholders = ','.join(['%s'] * len(appointment_ids))
        query = f"""
            SELECT
                aps.*,
                s.name as service_name,
                s.category as service_category,
                s.service_type
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id IN ({placeholders})
            ORDER BY aps.appointment_id, aps.is_addon, aps.id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(appointment_ids))
            rows = cursor.fetchall()

        result = {aid: [] for aid in appointment_ids}
        for row in rows:
            result[row['appointment_id']].append(dict(row))
        return result

    def get_main_services(self, appointment_id: int) -> List[Any]:
        """Pobierz tylko usługi główne dla wizyty"""
        query = """
            SELECT aps.*, s.name as service_name, s.category as service_category
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id = %s AND aps.is_addon = FALSE
            ORDER BY aps.id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchall()

    def get_addons(self, appointment_id: int) -> List[Any]:
        """Pobierz tylko mikrousługi dodane w trakcie wizyty"""
        query = """
            SELECT aps.*, s.name as service_name, s.category as service_category
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id = %s AND aps.is_addon = TRUE
            ORDER BY aps.added_at
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchall()

    def get_appointment_totals(self, appointment_id: int) -> dict:
        """Oblicz sumy dla wizyty (główne + mikrousługi)"""
        query = """
            SELECT
                COALESCE(SUM(price_charged), 0) as total_price,
                COALESCE(SUM(commission_amount), 0) as total_commission,
                COALESCE(SUM(CASE WHEN is_addon = FALSE THEN price_charged ELSE 0 END), 0) as main_total,
                COALESCE(SUM(CASE WHEN is_addon = TRUE THEN price_charged ELSE 0 END), 0) as addon_total,
                COALESCE(SUM(CASE WHEN is_addon = FALSE THEN duration_minutes ELSE 0 END), 0) as main_duration,
                COUNT(*) as service_count,
                SUM(CASE WHEN is_addon = TRUE THEN 1 ELSE 0 END) as addon_count
            FROM appointment_services
            WHERE appointment_id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            row = cursor.fetchone()
            return {
                'total_price': Decimal(str(row['total_price'])),
                'total_commission': Decimal(str(row['total_commission'])),
                'main_total': Decimal(str(row['main_total'])),
                'addon_total': Decimal(str(row['addon_total'])),
                'main_duration': row['main_duration'],
                'service_count': row['service_count'],
                'addon_count': row['addon_count']
            }

    def is_addon_already_added(self, appointment_id: int, service_id: int) -> bool:
        """Sprawdź czy mikrousługa została już dodana do wizyty"""
        query = """
            SELECT COUNT(*) as cnt FROM appointment_services
            WHERE appointment_id = %s AND service_id = %s AND is_addon = TRUE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id, service_id))
            return cursor.fetchone()['cnt'] > 0

    def update_service(self, appt_service_id: int, price_charged: Decimal,
                       duration_minutes: int, commission_rate: Decimal,
                       commission_amount: Decimal, is_addon: bool) -> bool:
        """Zaktualizuj istniejącą usługę wizyty (diff strategy — bez zmiany added_at)"""
        query = """
            UPDATE appointment_services
            SET price_charged = %s, duration_minutes = %s,
                commission_rate = %s, commission_amount = %s, is_addon = %s
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                str(price_charged),
                duration_minutes,
                str(commission_rate),
                str(commission_amount),
                bool(is_addon),
                appt_service_id,
            ))
            safe_commit(conn)
            return cursor.rowcount > 0

    def delete(self, appt_service_id: int) -> bool:
        """Usuń usługę z wizyty"""
        query = "DELETE FROM appointment_services WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appt_service_id,))
            safe_commit(conn)
            return cursor.rowcount > 0

    def delete_all_for_appointment(self, appointment_id: int) -> bool:
        """Usuń wszystkie usługi przypisane do wizyty"""
        query = "DELETE FROM appointment_services WHERE appointment_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            safe_commit(conn)
            return True
