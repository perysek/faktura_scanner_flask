"""
Repository dla operacji na usługach przypisanych do wizyt (appointment_services)
"""
import sqlite3
from decimal import Decimal
from typing import List, Optional
from datetime import datetime
from config.database import get_db_connection
from database.models import AppointmentService


class AppointmentServiceRepository:
    """Repository do zarządzania usługami w ramach wizyt (główne + mikrousługi)"""

    def row_to_appointment_service(self, row: sqlite3.Row) -> Optional[AppointmentService]:
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
            added_at=datetime.fromisoformat(row['added_at']) if row['added_at'] else None
        )

    def add_service(self, appt_svc: AppointmentService) -> int:
        """Dodaj usługę główną do wizyty (przy rezerwacji)"""
        query = """
            INSERT INTO appointment_services (
                appointment_id, service_id, price_charged, duration_minutes,
                commission_rate, commission_amount, is_addon, added_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                appt_svc.appointment_id,
                appt_svc.service_id,
                str(appt_svc.price_charged),
                appt_svc.duration_minutes,
                str(appt_svc.commission_rate),
                str(appt_svc.commission_amount)
            ))
            conn.commit()
            return cursor.lastrowid

    def add_addon_service(self, appt_svc: AppointmentService) -> int:
        """Dodaj mikrousługę do wizyty (w trakcie — status=in_progress)"""
        query = """
            INSERT INTO appointment_services (
                appointment_id, service_id, price_charged, duration_minutes,
                commission_rate, commission_amount, is_addon, added_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                appt_svc.appointment_id,
                appt_svc.service_id,
                str(appt_svc.price_charged),
                appt_svc.duration_minutes,
                str(appt_svc.commission_rate),
                str(appt_svc.commission_amount)
            ))
            conn.commit()
            return cursor.lastrowid

    def get_all_for_appointment(self, appointment_id: int) -> List[sqlite3.Row]:
        """Pobierz wszystkie usługi (główne + mikrousługi) dla wizyty"""
        query = """
            SELECT
                aps.*,
                s.name as service_name,
                s.category as service_category,
                s.service_type
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id = ?
            ORDER BY aps.is_addon, aps.id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchall()

    def get_main_services(self, appointment_id: int) -> List[sqlite3.Row]:
        """Pobierz tylko usługi główne dla wizyty"""
        query = """
            SELECT aps.*, s.name as service_name, s.category as service_category
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id = ? AND aps.is_addon = 0
            ORDER BY aps.id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchall()

    def get_addons(self, appointment_id: int) -> List[sqlite3.Row]:
        """Pobierz tylko mikrousługi dodane w trakcie wizyty"""
        query = """
            SELECT aps.*, s.name as service_name, s.category as service_category
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            WHERE aps.appointment_id = ? AND aps.is_addon = 1
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
                COALESCE(SUM(CASE WHEN is_addon = 0 THEN price_charged ELSE 0 END), 0) as main_total,
                COALESCE(SUM(CASE WHEN is_addon = 1 THEN price_charged ELSE 0 END), 0) as addon_total,
                COALESCE(SUM(CASE WHEN is_addon = 0 THEN duration_minutes ELSE 0 END), 0) as main_duration,
                COUNT(*) as service_count,
                SUM(CASE WHEN is_addon = 1 THEN 1 ELSE 0 END) as addon_count
            FROM appointment_services
            WHERE appointment_id = ?
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
            WHERE appointment_id = ? AND service_id = ? AND is_addon = 1
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id, service_id))
            return cursor.fetchone()['cnt'] > 0

    def delete(self, appt_service_id: int) -> bool:
        """Usuń usługę z wizyty"""
        query = "DELETE FROM appointment_services WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appt_service_id,))
            conn.commit()
            return cursor.rowcount > 0
