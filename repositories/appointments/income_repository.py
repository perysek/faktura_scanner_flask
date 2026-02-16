"""
Repository dla operacji na rekordach przychodu (income_records)
"""
import sqlite3
from decimal import Decimal
from typing import List, Optional
from datetime import datetime, date
from config.database import get_db_connection
from database.models import IncomeRecord


class IncomeRepository:
    """Repository do zarządzania rekordami przychodu"""

    def row_to_income_record(self, row: sqlite3.Row) -> Optional[IncomeRecord]:
        """Konwertuj Row na obiekt IncomeRecord"""
        if not row:
            return None

        return IncomeRecord(
            id=row['id'],
            appointment_id=row['appointment_id'],
            client_id=row['client_id'],
            employee_id=row['employee_id'],
            total_amount=Decimal(str(row['total_amount'])),
            discount_amount=Decimal(str(row['discount_amount'])) if row['discount_amount'] is not None else Decimal('0'),
            net_amount=Decimal(str(row['net_amount'])),
            commission_total=Decimal(str(row['commission_total'])),
            payment_method=row['payment_method'],
            payment_date=datetime.strptime(row['payment_date'], '%Y-%m-%d').date()
                if row['payment_date'] else None,
            notes=row['notes'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

    def create(self, record: IncomeRecord) -> int:
        """Utwórz rekord przychodu"""
        query = """
            INSERT INTO income_records (
                appointment_id, client_id, employee_id,
                total_amount, discount_amount, net_amount,
                commission_total, payment_method, payment_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                record.appointment_id,
                record.client_id,
                record.employee_id,
                str(record.total_amount),
                str(record.discount_amount),
                str(record.net_amount),
                str(record.commission_total),
                record.payment_method,
                record.payment_date.isoformat(),
                record.notes
            ))
            conn.commit()
            return cursor.lastrowid

    def get_by_appointment(self, appointment_id: int) -> Optional[sqlite3.Row]:
        """Pobierz rekord przychodu dla wizyty"""
        query = "SELECT * FROM income_records WHERE appointment_id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchone()

    def get_by_date_range(self, start_date: date, end_date: date,
                           employee_id: Optional[int] = None) -> List[sqlite3.Row]:
        """Pobierz rekordy przychodu w zakresie dat"""
        params = [start_date.isoformat(), end_date.isoformat()]
        employee_filter = ""

        if employee_id:
            employee_filter = "AND ir.employee_id = ?"
            params.append(employee_id)

        query = f"""
            SELECT
                ir.*,
                c.first_name || ' ' || c.last_name as client_name,
                e.first_name || ' ' || e.last_name as employee_name
            FROM income_records ir
            JOIN clients c ON c.id = ir.client_id
            JOIN employees e ON e.id = ir.employee_id
            WHERE ir.payment_date BETWEEN ? AND ? {employee_filter}
            ORDER BY ir.payment_date DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_by_employee(self, employee_id: int, year: int, month: int) -> List[sqlite3.Row]:
        """Pobierz rekordy przychodu pracownika za miesiąc"""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        query = """
            SELECT
                ir.*,
                c.first_name || ' ' || c.last_name as client_name
            FROM income_records ir
            JOIN clients c ON c.id = ir.client_id
            WHERE ir.employee_id = ? AND ir.payment_date >= ? AND ir.payment_date < ?
            ORDER BY ir.payment_date DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, start_date, end_date))
            return cursor.fetchall()

    def get_monthly_summary(self, year: int, month: int) -> dict:
        """Pobierz podsumowanie przychodów za miesiąc"""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        query = """
            SELECT
                COUNT(*) as total_appointments,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COALESCE(SUM(discount_amount), 0) as total_discounts,
                COALESCE(SUM(net_amount), 0) as total_net,
                COALESCE(SUM(commission_total), 0) as total_commissions,
                COALESCE(AVG(net_amount), 0) as avg_ticket
            FROM income_records
            WHERE payment_date >= ? AND payment_date < ?
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date, end_date))
            row = cursor.fetchone()
            return {
                'total_appointments': row['total_appointments'],
                'total_revenue': Decimal(str(row['total_revenue'])),
                'total_discounts': Decimal(str(row['total_discounts'])),
                'total_net': Decimal(str(row['total_net'])),
                'total_commissions': Decimal(str(row['total_commissions'])),
                'avg_ticket': Decimal(str(row['avg_ticket']))
            }

    def get_employee_summary(self, year: int, month: int) -> List[sqlite3.Row]:
        """Pobierz podsumowanie przychodów per pracownik za miesiąc"""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        query = """
            SELECT
                e.id as employee_id,
                e.first_name || ' ' || e.last_name as employee_name,
                COUNT(*) as appointment_count,
                COALESCE(SUM(ir.total_amount), 0) as total_revenue,
                COALESCE(SUM(ir.net_amount), 0) as net_revenue,
                COALESCE(SUM(ir.commission_total), 0) as total_commission
            FROM income_records ir
            JOIN employees e ON e.id = ir.employee_id
            WHERE ir.payment_date >= ? AND ir.payment_date < ?
            GROUP BY e.id
            ORDER BY total_revenue DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date, end_date))
            return cursor.fetchall()

    def delete_by_appointment(self, appointment_id: int) -> bool:
        """Usuń rekord przychodu dla wizyty (używane przy cofnięciu statusu 'completed')"""
        query = "DELETE FROM income_records WHERE appointment_id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            conn.commit()
            return cursor.rowcount > 0
