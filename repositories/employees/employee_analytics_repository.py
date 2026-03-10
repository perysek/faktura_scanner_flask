"""
Per-employee analytics repository — 7 metric methods for the employee view.
Uses DatabaseConnection.get_connection() directly (same pattern as analytics_repository.py).
"""
import json
from typing import Dict, List

from config.database import DatabaseConnection


class EmployeeAnalyticsRepository:
    """Analytics queries scoped to a single employee."""

    def __init__(self, employee_id: int):
        self.employee_id = employee_id

    def _conn(self):
        return DatabaseConnection.get_connection()

    # ------------------------------------------------------------------
    # 1. Summary KPIs
    # ------------------------------------------------------------------
    def get_summary(self, months: int = 12) -> Dict:
        """
        Total revenue, employer cost, net profit, avg ticket, total appointments
        for the last N months.

        Cost formula (Polish employment model):
            gross_salary = GREATEST(base_salary, total_commission)
            employer_cost = gross_salary * (1 + employer_cost_rate)
            net_profit = total_revenue - employer_cost
        """
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                e.base_salary,
                COALESCE(e.employer_cost_rate, 0.22) AS cost_rate,
                COUNT(DISTINCT a.id) FILTER (WHERE a.status = 'completed') AS total_appointments,
                COALESCE(SUM(i.net_amount), 0) AS total_revenue,
                COALESCE(SUM(i.commission_total), 0) AS total_commission,
                COALESCE(AVG(i.net_amount), 0) AS avg_ticket
            FROM employees e
            LEFT JOIN appointments a
                ON a.employee_id = e.id
                AND a.appointment_date >= CURRENT_DATE - (%(months)s || ' months')::interval
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE e.id = %(eid)s
            GROUP BY e.id, e.base_salary, e.employer_cost_rate
        """, {'eid': self.employee_id, 'months': months})
        row = cursor.fetchone()
        if not row:
            return {
                'total_appointments': 0,
                'total_revenue': 0.0,
                'employer_cost': 0.0,
                'net_profit': 0.0,
                'avg_ticket': 0.0,
            }
        base_salary = float(row['base_salary'] or 0)
        cost_rate = float(row['cost_rate'])
        total_commission = float(row['total_commission'])
        total_revenue = float(row['total_revenue'])
        gross_salary = max(base_salary, total_commission)
        employer_cost = gross_salary * (1 + cost_rate)
        net_profit = total_revenue - employer_cost
        return {
            'total_appointments': row['total_appointments'],
            'total_revenue': round(total_revenue, 2),
            'employer_cost': round(employer_cost, 2),
            'net_profit': round(net_profit, 2),
            'avg_ticket': round(float(row['avg_ticket']), 2),
        }

    # ------------------------------------------------------------------
    # 2. Monthly revenue trend
    # ------------------------------------------------------------------
    def get_revenue_trend(self, months: int = 12) -> List[Dict]:
        """
        Monthly {'month', 'revenue', 'commission', 'appointments'} for last N months.
        Uses generate_series to fill months with no activity as zeros.
        """
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - (%(months)s || ' months')::interval),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            )
            SELECT
                TO_CHAR(m.month_start, 'YYYY-MM') AS month,
                TO_CHAR(m.month_start, 'Mon YYYY') AS month_label,
                COALESCE(SUM(i.net_amount), 0) AS revenue,
                COALESCE(SUM(i.commission_total), 0) AS commission,
                COUNT(a.id) FILTER (WHERE a.status = 'completed') AS appointments
            FROM months m
            LEFT JOIN appointments a
                ON a.employee_id = %(eid)s
                AND DATE_TRUNC('month', a.appointment_date) = m.month_start
            LEFT JOIN income_records i ON i.appointment_id = a.id
            GROUP BY m.month_start
            ORDER BY m.month_start
        """, {'eid': self.employee_id, 'months': months})
        rows = cursor.fetchall()
        return [
            {
                'month': r['month'],
                'month_label': r['month_label'],
                'revenue': round(float(r['revenue']), 2),
                'commission': round(float(r['commission']), 2),
                'appointments': r['appointments'],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 3. Services mix
    # ------------------------------------------------------------------
    def get_services_mix(self) -> List[Dict]:
        """Top 10 services by appointment count: {'service_name', 'appointment_count', 'revenue'}"""
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                s.name AS service_name,
                COUNT(aps.id) AS appointment_count,
                COALESCE(SUM(aps.price_charged), 0) AS revenue
            FROM appointment_services aps
            JOIN services s ON s.id = aps.service_id
            JOIN appointments a ON a.id = aps.appointment_id
            WHERE a.employee_id = %s AND a.status = 'completed'
            GROUP BY s.id, s.name
            ORDER BY appointment_count DESC
            LIMIT 10
        """, (self.employee_id,))
        return [
            {
                'service_name': r['service_name'],
                'appointment_count': r['appointment_count'],
                'revenue': round(float(r['revenue']), 2),
            }
            for r in cursor.fetchall()
        ]

    # ------------------------------------------------------------------
    # 4. Peak hours heatmap
    # ------------------------------------------------------------------
    def get_peak_hours(self) -> List[Dict]:
        """{'day_of_week' (1=Mon..7=Sun), 'hour_of_day' (0-23), 'appointment_count'}"""
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                EXTRACT(ISODOW FROM appointment_date)::int AS day_of_week,
                EXTRACT(HOUR FROM start_time)::int AS hour_of_day,
                COUNT(*) AS appointment_count
            FROM appointments
            WHERE employee_id = %s
              AND status = 'completed'
              AND start_time IS NOT NULL
            GROUP BY day_of_week, hour_of_day
            ORDER BY day_of_week, hour_of_day
        """, (self.employee_id,))
        return [dict(r) for r in cursor.fetchall()]

    # ------------------------------------------------------------------
    # 5. New vs returning clients split
    # ------------------------------------------------------------------
    def get_client_split(self, months: int = 12) -> List[Dict]:
        """Monthly {'month', 'new_clients', 'returning_clients'} using first-appointment CTE."""
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - (%(months)s || ' months')::interval),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            first_visits AS (
                SELECT client_id, MIN(appointment_date) AS first_visit
                FROM appointments
                WHERE status = 'completed'
                GROUP BY client_id
            ),
            monthly_clients AS (
                SELECT
                    DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                    a.client_id,
                    fv.first_visit
                FROM appointments a
                JOIN first_visits fv ON fv.client_id = a.client_id
                WHERE a.employee_id = %(eid)s
                  AND a.status = 'completed'
                  AND a.appointment_date >= CURRENT_DATE - (%(months)s || ' months')::interval
            )
            SELECT
                TO_CHAR(m.month_start, 'YYYY-MM') AS month,
                TO_CHAR(m.month_start, 'Mon YYYY') AS month_label,
                COUNT(DISTINCT mc.client_id) FILTER (
                    WHERE mc.first_visit >= m.month_start
                      AND mc.first_visit < m.month_start + INTERVAL '1 month'
                ) AS new_clients,
                COUNT(DISTINCT mc.client_id) FILTER (
                    WHERE mc.first_visit < m.month_start
                ) AS returning_clients
            FROM months m
            LEFT JOIN monthly_clients mc ON mc.month_start = m.month_start
            GROUP BY m.month_start
            ORDER BY m.month_start
        """, {'eid': self.employee_id, 'months': months})
        return [
            {
                'month': r['month'],
                'month_label': r['month_label'],
                'new_clients': r['new_clients'] or 0,
                'returning_clients': r['returning_clients'] or 0,
            }
            for r in cursor.fetchall()
        ]

    # ------------------------------------------------------------------
    # 6. Skills radar
    # ------------------------------------------------------------------
    def get_skills_radar(self) -> List[Dict]:
        """
        Parse skills JSON from employee record in Python.
        Returns [{'skill', 'rating'}] sorted DESC by rating.
        Skills are stored as JSON object: {"skill_name": rating, ...}
        """
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("SELECT skills FROM employees WHERE id = %s", (self.employee_id,))
        row = cursor.fetchone()
        if not row or not row['skills']:
            return []
        try:
            skills_data = row['skills']
            if isinstance(skills_data, str):
                skills_data = json.loads(skills_data)
            if isinstance(skills_data, dict):
                items = [{'skill': k, 'rating': int(v)} for k, v in skills_data.items()]
            elif isinstance(skills_data, list):
                items = skills_data
            else:
                return []
            return sorted(items, key=lambda x: x.get('rating', 0), reverse=True)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    # ------------------------------------------------------------------
    # 7. Monthly commission trend
    # ------------------------------------------------------------------
    def get_commission_trend(self, months: int = 12) -> List[Dict]:
        """
        Monthly {'month', 'base_salary', 'commission_earned', 'gross_salary'}.
        gross_salary = GREATEST(base_salary, commission_earned).
        Uses generate_series to fill zero months.
        """
        conn = self._conn()
        cursor = conn.cursor()
        cursor.execute("""
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - (%(months)s || ' months')::interval),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            monthly_commission AS (
                SELECT
                    DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                    COALESCE(SUM(i.commission_total), 0) AS commission_earned
                FROM appointments a
                LEFT JOIN income_records i ON i.appointment_id = a.id
                WHERE a.employee_id = %(eid)s
                  AND a.status = 'completed'
                GROUP BY DATE_TRUNC('month', a.appointment_date)::date
            )
            SELECT
                TO_CHAR(m.month_start, 'YYYY-MM') AS month,
                TO_CHAR(m.month_start, 'Mon YYYY') AS month_label,
                e.base_salary,
                COALESCE(mc.commission_earned, 0) AS commission_earned,
                GREATEST(e.base_salary, COALESCE(mc.commission_earned, 0)) AS gross_salary
            FROM months m
            CROSS JOIN employees e
            LEFT JOIN monthly_commission mc ON mc.month_start = m.month_start
            WHERE e.id = %(eid)s
            ORDER BY m.month_start
        """, {'eid': self.employee_id, 'months': months})
        return [
            {
                'month': r['month'],
                'month_label': r['month_label'],
                'base_salary': round(float(r['base_salary'] or 0), 2),
                'commission_earned': round(float(r['commission_earned']), 2),
                'gross_salary': round(float(r['gross_salary']), 2),
            }
            for r in cursor.fetchall()
        ]
