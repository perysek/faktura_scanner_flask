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
                AND a.appointment_date BETWEEN %s AND %s
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
                COUNT(DISTINCT a.id) as appointments_count,
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
            LEFT JOIN appointments a ON a.employee_id = e.id
                AND a.status = 'completed'
                AND a.appointment_date BETWEEN %s AND %s
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE e.is_active = TRUE
            GROUP BY e.id, e.first_name, e.last_name, e.base_salary, e.employer_cost_rate
            ORDER BY revenue_generated DESC
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_service_breakdown(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Get service revenue breakdown.

        Returns list of:
            {
                'service_name': str,
                'category': str,
                'times_booked': int,
                'revenue_generated': float
            }
        """
        query = """
            SELECT
                s.name as service_name,
                s.category,
                COUNT(aps.id) as times_booked,
                COALESCE(SUM(aps.price_charged), 0) as revenue_generated
            FROM services s
            LEFT JOIN appointment_services aps ON aps.service_id = s.id
            LEFT JOIN appointments a ON a.id = aps.appointment_id
            WHERE a.status = 'completed'
                AND a.appointment_date BETWEEN %s AND %s
            GROUP BY s.id, s.name, s.category
            ORDER BY revenue_generated DESC
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_client_metrics(self, start_date: date, end_date: date) -> Dict:
        """
        Get client acquisition and retention metrics.

        Returns:
            {
                'new_clients': int,
                'returning_clients': int,
                'retention_rate': float (percentage),
                'at_risk_clients': List[Dict]
            }
        """
        # New vs. returning clients
        new_returning_query = """
            SELECT
                COUNT(DISTINCT CASE
                    WHEN c.first_visit_date >= %s THEN c.id
                END) as new_clients,
                COUNT(DISTINCT CASE
                    WHEN c.first_visit_date < %s THEN c.id
                END) as returning_clients
            FROM clients c
            INNER JOIN appointments a ON a.client_id = c.id
            WHERE a.status = 'completed'
                AND a.appointment_date BETWEEN %s AND %s
        """

        # Retention rate (90-day window)
        retention_query = """
            WITH client_visits AS (
                SELECT
                    client_id,
                    appointment_date,
                    LAG(appointment_date) OVER (PARTITION BY client_id ORDER BY appointment_date) as prev_visit
                FROM appointments
                WHERE status = 'completed'
            )
            SELECT
                COUNT(CASE WHEN (appointment_date - prev_visit) <= 90 THEN 1 END) * 100.0 /
                NULLIF(COUNT(*), 0) as retention_rate
            FROM client_visits
            WHERE prev_visit IS NOT NULL
                AND appointment_date BETWEEN %s AND %s
        """

        # At-risk clients (90+ days since last visit)
        at_risk_query = """
            SELECT
                c.id,
                c.first_name || ' ' || c.last_name as client_name,
                c.last_visit_date,
                CURRENT_DATE - c.last_visit_date as days_since_visit
            FROM clients c
            WHERE c.is_active = TRUE
                AND c.last_visit_date < CURRENT_DATE - INTERVAL '90 days'
            ORDER BY c.last_visit_date ASC
            LIMIT 20
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()

        # New/returning
        cursor.execute(new_returning_query, (start_date, start_date, start_date, end_date))
        nr_row = cursor.fetchone()

        # Retention
        cursor.execute(retention_query, (start_date, end_date))
        ret_row = cursor.fetchone()

        # At-risk
        cursor.execute(at_risk_query)
        at_risk_rows = cursor.fetchall()

        return {
            'new_clients': nr_row['new_clients'] if nr_row else 0,
            'returning_clients': nr_row['returning_clients'] if nr_row else 0,
            'retention_rate': ret_row['retention_rate'] if ret_row else 0.0,
            'at_risk_clients': [dict(row) for row in at_risk_rows]
        }

    def get_revenue_trend(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Get daily revenue trend for line chart.

        Returns list of:
            {
                'date': str (YYYY-MM-DD),
                'revenue': float,
                'appointments': int
            }
        """
        query = """
            SELECT
                a.appointment_date as date,
                COUNT(a.id) as appointments,
                COALESCE(SUM(i.net_amount), 0) as revenue
            FROM appointments a
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
                AND a.appointment_date BETWEEN %s AND %s
            GROUP BY a.appointment_date
            ORDER BY a.appointment_date
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]
