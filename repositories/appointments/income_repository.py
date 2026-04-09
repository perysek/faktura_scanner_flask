"""
Repository dla operacji na rekordach przychodu (income_records)
"""
from decimal import Decimal
from typing import Any, List, Optional
from datetime import datetime, date
from config.database import get_db_connection, safe_commit
from database.models import IncomeRecord
from repositories.db_utils import parse_dt, parse_date


class IncomeRepository:
    """Repository do zarządzania rekordami przychodu"""

    _COLUMNS = (
        'id, appointment_id, client_id, employee_id, '
        'total_amount, discount_amount, net_amount, commission_total, '
        'payment_method, payment_date, notes, created_at'
    )

    def row_to_income_record(self, row: Any) -> Optional[IncomeRecord]:
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
            payment_date=parse_date(row['payment_date']),
            notes=row['notes'],
            created_at=parse_dt(row['created_at'])
        )

    def create(self, record: IncomeRecord) -> int:
        """Utwórz rekord przychodu"""
        query = """
            INSERT INTO income_records (
                appointment_id, client_id, employee_id,
                total_amount, discount_amount, net_amount,
                commission_total, payment_method, payment_date, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
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
            result_id = cursor.fetchone()["id"]
            safe_commit(conn)
            return result_id

    def get_by_appointment(self, appointment_id: int) -> Optional[Any]:
        """Pobierz rekord przychodu dla wizyty"""
        query = f"SELECT {self._COLUMNS} FROM income_records WHERE appointment_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchone()

    def get_by_date_range(self, start_date: date, end_date: date,
                           employee_id: Optional[int] = None) -> List[Any]:
        """Pobierz rekordy przychodu w zakresie dat"""
        params = [start_date.isoformat(), end_date.isoformat()]
        employee_filter = ""

        if employee_id:
            employee_filter = "AND ir.employee_id = %s"
            params.append(employee_id)

        query = f"""
            SELECT
                ir.id, ir.appointment_id, ir.client_id, ir.employee_id,
                ir.total_amount, ir.discount_amount, ir.net_amount, ir.commission_total,
                ir.payment_method, ir.payment_date, ir.notes, ir.created_at,
                c.first_name || ' ' || c.last_name as client_name,
                e.first_name || ' ' || e.last_name as employee_name
            FROM income_records ir
            JOIN clients c ON c.id = ir.client_id
            JOIN employees e ON e.id = ir.employee_id
            WHERE ir.payment_date BETWEEN %s AND %s {employee_filter}
            ORDER BY ir.payment_date DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_by_employee(self, employee_id: int, year: int, month: int) -> List[Any]:
        """Pobierz rekordy przychodu pracownika za miesiąc"""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        query = """
            SELECT
                ir.id, ir.appointment_id, ir.client_id, ir.employee_id,
                ir.total_amount, ir.discount_amount, ir.net_amount, ir.commission_total,
                ir.payment_method, ir.payment_date, ir.notes, ir.created_at,
                c.first_name || ' ' || c.last_name as client_name
            FROM income_records ir
            JOIN clients c ON c.id = ir.client_id
            WHERE ir.employee_id = %s AND ir.payment_date >= %s AND ir.payment_date < %s
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
            WHERE payment_date >= %s AND payment_date < %s
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

    def get_employee_summary(self, year: int, month: int) -> List[Any]:
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
            WHERE ir.payment_date >= %s AND ir.payment_date < %s
            GROUP BY e.id
            ORDER BY total_revenue DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (start_date, end_date))
            return cursor.fetchall()

    def update(self, appointment_id: int, total_amount: Decimal,
               net_amount: Decimal, commission_total: Decimal,
               client_id: Optional[int] = None,
               employee_id: Optional[int] = None,
               payment_method: Optional[str] = None) -> bool:
        """Zaktualizuj istniejący rekord przychodu (TASK#4/5)"""
        parts = [
            "total_amount = %s",
            "net_amount = %s",
            "commission_total = %s",
        ]
        params = [str(total_amount), str(net_amount), str(commission_total)]

        if client_id is not None:
            parts.append("client_id = %s")
            params.append(client_id)
        if employee_id is not None:
            parts.append("employee_id = %s")
            params.append(employee_id)
        if payment_method is not None:
            parts.append("payment_method = %s")
            params.append(payment_method)

        params.append(appointment_id)
        query = f"UPDATE income_records SET {', '.join(parts)} WHERE appointment_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            safe_commit(conn)
            return cursor.rowcount > 0

    def delete_by_appointment(self, appointment_id: int) -> bool:
        """Usuń rekord przychodu dla wizyty (używane przy cofnięciu statusu 'completed')"""
        query = "DELETE FROM income_records WHERE appointment_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            safe_commit(conn)
            return cursor.rowcount > 0
