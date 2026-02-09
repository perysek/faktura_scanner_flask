"""
Analytics repository for dashboard metrics
"""
from datetime import date, timedelta
from typing import Tuple, Dict, List
from dateutil.relativedelta import relativedelta
from config.database import DatabaseConnection


class AnalyticsRepository:
    """Repository for analytics queries with time period support"""

    def get_date_ranges(
        self,
        period: str,
        reference_date: date = None
    ) -> Tuple[date, date, date, date]:
        """
        Calculate date ranges for current and comparison periods.

        Args:
            period: 'current_month' | 'last_month' | 'current_year' | 'custom'
            reference_date: Reference date for calculations (defaults to today)

        Returns:
            (current_start, current_end, previous_start, previous_end)
        """
        ref = reference_date or date.today()

        if period == 'current_month':
            current_start = ref.replace(day=1)
            current_end = (current_start + relativedelta(months=1)) - timedelta(days=1)
            previous_start = current_start - relativedelta(months=1)
            previous_end = current_start - timedelta(days=1)

        elif period == 'last_month':
            current_start = (ref.replace(day=1) - relativedelta(months=1))
            current_end = ref.replace(day=1) - timedelta(days=1)
            previous_start = current_start - relativedelta(months=1)
            previous_end = current_start - timedelta(days=1)

        elif period == 'current_year':
            current_start = ref.replace(month=1, day=1)
            current_end = ref
            previous_start = current_start - relativedelta(years=1)
            previous_end = ref - relativedelta(years=1)

        else:
            raise ValueError(f"Unsupported period: {period}")

        return (current_start, current_end, previous_start, previous_end)

    def get_revenue_summary(self, start_date: date, end_date: date) -> Dict:
        """
        Get revenue summary for date range.

        Returns:
            {
                'total_appointments': int,
                'unique_clients': int,
                'total_revenue': float,
                'avg_ticket': float,
                'total_commissions': float
            }
        """
        query = """
            SELECT
                COUNT(DISTINCT a.id) as total_appointments,
                COUNT(DISTINCT a.client_id) as unique_clients,
                COALESCE(SUM(i.net_amount), 0) as total_revenue,
                COALESCE(AVG(i.net_amount), 0) as avg_ticket,
                COALESCE(SUM(i.commission_total), 0) as total_commissions
            FROM appointments a
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
                AND a.appointment_date BETWEEN ? AND ?
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        row = cursor.fetchone()

        return dict(row) if row else {
            'total_appointments': 0,
            'unique_clients': 0,
            'total_revenue': 0.0,
            'avg_ticket': 0.0,
            'total_commissions': 0.0
        }

    def get_employee_performance(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Get employee performance metrics with Polish employment cost model.

        Total Employer Cost = (base_salary + commission) × (1 + employer_cost_rate)
        Net Profit = revenue_generated - total_employer_cost

        Returns list of:
            {
                'id': int,
                'employee_name': str,
                'base_salary': float,
                'cost_rate': float (default 0.22 = 22%),
                'appointments_count': int,
                'revenue_generated': float,
                'commission_earned': float,
                'gross_salary': float (base + commission),
                'total_employer_cost': float (gross × 1.22),
                'net_profit': float (revenue - cost)
            }
        """
        query = """
            SELECT
                e.id,
                e.first_name || ' ' || e.last_name as employee_name,
                e.base_salary,
                COALESCE(e.employer_cost_rate, 0.22) as cost_rate,
                COUNT(a.id) as appointments_count,
                COALESCE(SUM(i.net_amount), 0) as revenue_generated,
                COALESCE(SUM(i.commission_total), 0) as commission_earned,

                -- Cost calculation
                (e.base_salary + COALESCE(SUM(i.commission_total), 0)) as gross_salary,
                (e.base_salary + COALESCE(SUM(i.commission_total), 0)) *
                    (1 + COALESCE(e.employer_cost_rate, 0.22)) as total_employer_cost,

                -- Profitability
                COALESCE(SUM(i.net_amount), 0) -
                    ((e.base_salary + COALESCE(SUM(i.commission_total), 0)) *
                     (1 + COALESCE(e.employer_cost_rate, 0.22))) as net_profit
            FROM employees e
            LEFT JOIN appointments a ON a.employee_id = e.id AND a.status = 'completed'
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE e.is_active = 1
                AND (a.appointment_date BETWEEN ? AND ? OR a.appointment_date IS NULL)
            GROUP BY e.id, e.first_name, e.last_name, e.base_salary, e.employer_cost_rate
            ORDER BY revenue_generated DESC
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]
