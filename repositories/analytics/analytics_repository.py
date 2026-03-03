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

        Gross Salary = GREATEST(base_salary, commission_total)
            — employee earns base_salary as a guarantee; if commission exceeds it, commission wins
        Total Employer Cost = gross_salary × (1 + employer_cost_rate)
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
                'gross_salary': float (GREATEST(base_salary, commission)),
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

                -- Cost calculation: employee earns base_salary guaranteed;
                -- if commission exceeds base_salary, commission replaces it (not added)
                GREATEST(e.base_salary, COALESCE(SUM(i.commission_total), 0)) as gross_salary,
                GREATEST(e.base_salary, COALESCE(SUM(i.commission_total), 0)) *
                    (1 + COALESCE(e.employer_cost_rate, 0.22)) as total_employer_cost,

                -- Profitability
                COALESCE(SUM(i.net_amount), 0) -
                    (GREATEST(e.base_salary, COALESCE(SUM(i.commission_total), 0)) *
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

        # At-risk clients (90+ days since last visit, measured from end of selected period)
        at_risk_query = """
            SELECT
                c.id,
                c.first_name || ' ' || c.last_name as client_name,
                c.last_visit_date,
                %s::date - c.last_visit_date as days_since_visit
            FROM clients c
            WHERE c.is_active = TRUE
                AND c.last_visit_date IS NOT NULL
                AND c.last_visit_date < %s::date - INTERVAL '90 days'
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

        # At-risk (reference point = end_date so it's period-aware)
        cursor.execute(at_risk_query, (end_date, end_date))
        at_risk_rows = cursor.fetchall()

        return {
            'new_clients': nr_row['new_clients'] if nr_row else 0,
            'returning_clients': nr_row['returning_clients'] if nr_row else 0,
            'retention_rate': ret_row['retention_rate'] if ret_row else 0.0,
            'at_risk_clients': [dict(row) for row in at_risk_rows]
        }

    def get_invoice_costs(self, start_date: date, end_date: date) -> Dict:
        """
        Pobierz koszty faktur zakupowych dla zakresu dat (metoda memoriałowa).

        Faktury reprezentują koszty materiałów/dostawców — używa invoice_date.

        Returns:
            {
                'total_costs': float,
                'invoice_count': int,
                'unpaid_count': int,
                'unpaid_amount': float
            }
        """
        query = """
            SELECT
                COALESCE(SUM(amount), 0)                                            AS total_costs,
                COUNT(*)                                                             AS invoice_count,
                COUNT(CASE WHEN status = 'Nieopłacona' THEN 1 END)                 AS unpaid_count,
                COALESCE(SUM(CASE WHEN status = 'Nieopłacona' THEN amount END), 0) AS unpaid_amount
            FROM invoices
            WHERE invoice_date BETWEEN %s AND %s
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        row = cursor.fetchone()

        return dict(row) if row else {
            'total_costs': 0.0,
            'invoice_count': 0,
            'unpaid_count': 0,
            'unpaid_amount': 0.0
        }

    def get_business_insights(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Generuj algorytmiczne wskazówki biznesowe na podstawie danych okresu.

        Korzysta z istniejących metod repozytorium — bez duplikowania SQL.

        Returns list of:
            {'type': 'warning'|'success'|'info'|'alert', 'title': str, 'message': str}
        """
        insights = []

        # Gather data from existing methods
        revenue_data = self.get_revenue_summary(start_date, end_date)
        employee_data = self.get_employee_performance(start_date, end_date)
        client_data = self.get_client_metrics(start_date, end_date)
        service_data = self.get_service_breakdown(start_date, end_date)
        invoice_data = self.get_invoice_costs(start_date, end_date)
        occupancy_data = self.get_occupancy_stats(start_date, end_date)
        price_data = self.get_service_price_analysis(start_date, end_date)

        revenue = float(revenue_data.get('total_revenue', 0) or 0)
        total_employee_cost = sum(
            float(e.get('total_employer_cost', 0) or 0) for e in employee_data
        )
        unpaid_count = int(invoice_data.get('unpaid_count', 0) or 0)
        unpaid_amount = float(invoice_data.get('unpaid_amount', 0) or 0)
        invoice_costs = float(invoice_data.get('total_costs', 0) or 0)
        net_profit = revenue - total_employee_cost - invoice_costs

        # 1. Employee cost ratio
        if revenue > 0:
            emp_ratio = total_employee_cost / revenue
            if emp_ratio > 0.60:
                insights.append({
                    'type': 'warning',
                    'title': 'Wysokie koszty pracownicze',
                    'message': (
                        f'Koszty pracownicze stanowią {emp_ratio * 100:.0f}% przychodów — '
                        'rozważ optymalizację struktury wynagrodzeń'
                    )
                })

        # 2. Unpaid invoices
        if unpaid_count > 0:
            insights.append({
                'type': 'alert',
                'title': 'Niezapłacone faktury',
                'message': (
                    f'Masz {unpaid_count} niezapłaconych faktur na kwotę '
                    f'{unpaid_amount:,.2f} PLN — nieuregulowane zobowiązania'
                )
            })

        # 3. Top profit employee
        if employee_data:
            top_emp = max(employee_data, key=lambda e: float(e.get('net_profit', 0) or 0))
            top_profit = float(top_emp.get('net_profit', 0) or 0)
            insights.append({
                'type': 'success',
                'title': 'Top pracownik',
                'message': (
                    f'Najwyższy zysk netto generuje {top_emp["employee_name"]}: '
                    f'{top_profit:,.2f} PLN w tym okresie'
                )
            })

        # 4. At-risk clients
        at_risk = client_data.get('at_risk_clients', [])
        at_risk_count = len(at_risk)
        if at_risk_count > 3:
            insights.append({
                'type': 'warning',
                'title': 'Klienci zagrożeni utratą',
                'message': (
                    f'{at_risk_count} klientów nie odwiedziło salonu od ponad 90 dni — '
                    'warto podjąć działania retencyjne'
                )
            })

        # 5. Profit margin
        if revenue > 0:
            margin = net_profit / revenue
            if margin > 0.25:
                insights.append({
                    'type': 'success',
                    'title': 'Dobra marża zysku',
                    'message': (
                        f'Marża zysku netto: {margin * 100:.1f}% — dobry wynik finansowy'
                    )
                })
            elif net_profit < 0:
                insights.append({
                    'type': 'alert',
                    'title': 'Ujemny zysk netto',
                    'message': (
                        f'Marża zysku netto: {margin * 100:.1f}% — '
                        'koszty przekraczają przychody'
                    )
                })

        # 6. Best service
        if service_data:
            best = service_data[0]  # Already sorted by revenue DESC
            best_revenue = float(best.get('revenue_generated', 0) or 0)
            best_count = int(best.get('times_booked', 0) or 0)
            insights.append({
                'type': 'info',
                'title': 'Najpopularniejsza usługa',
                'message': (
                    f'Usługa \'{best["service_name"]}\' wygenerowała największy przychód: '
                    f'{best_revenue:,.2f} PLN ({best_count} wizyt)'
                )
            })

        # 7. Employees with negative net profit
        negative_profit_employees = [
            e for e in employee_data
            if float(e.get('net_profit', 0) or 0) < 0
        ]
        if negative_profit_employees:
            total_loss = sum(float(e.get('net_profit', 0) or 0) for e in negative_profit_employees)
            lines = ', '.join(
                f'{e["employee_name"]} ({float(e["net_profit"]):,.2f} PLN)'
                for e in sorted(negative_profit_employees, key=lambda e: float(e.get('net_profit', 0) or 0))
            )
            insights.append({
                'type': 'alert',
                'title': f'Pracownicy z ujemnym zyskiem ({len(negative_profit_employees)}) — strata: {total_loss:,.2f} PLN',
                'message': f'Koszty przekraczają przychody: {lines}'
            })

        # 8. Low salon occupancy
        occupancy_rate = float(occupancy_data.get('occupancy_rate', 0) or 0)
        if occupancy_data.get('theoretical_capacity', 0) > 0 and occupancy_rate < 60:
            insights.append({
                'type': 'warning',
                'title': 'Niskie obłożenie salonu',
                'message': (
                    f'Obłożenie salonu wynosi {occupancy_rate:.1f}% — '
                    'salon ma wolne moce przerobowe'
                )
            })

        # 9. High cancellation rate
        cancellation_rate = float(occupancy_data.get('cancellation_rate', 0) or 0)
        cancelled_count = int(occupancy_data.get('cancelled', 0) or 0)
        if cancellation_rate > 15:
            insights.append({
                'type': 'alert',
                'title': 'Wysoki wskaźnik odwołań',
                'message': (
                    f'{cancellation_rate:.1f}% wizyt zostało odwołanych '
                    f'({cancelled_count} odwołań) — sprawdź politykę rezerwacji'
                )
            })

        # 10. Services sold with high average discount
        for svc in price_data:
            discount = float(svc.get('avg_discount_pct', 0) or 0)
            if int(svc.get('bookings', 0) or 0) > 0 and discount > 15:
                insights.append({
                    'type': 'info',
                    'title': 'Wysoki rabat na usługę',
                    'message': (
                        f'Usługa \'{svc["service_name"]}\' sprzedawana ze średnim rabatem '
                        f'{discount:.1f}% — rozważ korektę cennika'
                    )
                })

        # Fallback if no data at all
        if not insights:
            insights.append({
                'type': 'info',
                'title': 'Brak danych',
                'message': 'Brak danych do analizy w wybranym okresie'
            })

        return insights

    def get_occupancy_stats(self, start_date: date, end_date: date) -> Dict:
        """
        Oblicz wskaźniki obłożenia salonu dla zakresu dat.

        Zwraca:
            {
                'completed': int,
                'cancelled': int,
                'no_shows': int,
                'total_scheduled': int,
                'theoretical_capacity': int,
                'occupancy_rate': float,      # %
                'cancellation_rate': float,   # %
                'no_show_rate': float         # %
            }
        """
        status_query = """
            SELECT
                COUNT(CASE WHEN status = 'completed' THEN 1 END)   AS completed,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END)   AS cancelled,
                COUNT(CASE WHEN status = 'no_show'   THEN 1 END)   AS no_shows,
                COUNT(*)                                            AS total_scheduled
            FROM appointments
            WHERE appointment_date BETWEEN %s AND %s
              AND status IN ('completed', 'cancelled', 'no_show')
        """

        capacity_query = """
            SELECT
                COUNT(*)                               AS active_employees,
                COALESCE(AVG(max_appointments_per_day), 8) AS avg_capacity
            FROM employees
            WHERE is_active = TRUE
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()

        cursor.execute(status_query, (start_date, end_date))
        row = cursor.fetchone()
        completed = int(row['completed'] or 0)
        cancelled = int(row['cancelled'] or 0)
        no_shows = int(row['no_shows'] or 0)
        total_scheduled = int(row['total_scheduled'] or 0)

        cursor.execute(capacity_query)
        cap_row = cursor.fetchone()
        active_employees = int(cap_row['active_employees'] or 0)
        avg_capacity = float(cap_row['avg_capacity'] or 8)

        working_days = (end_date - start_date).days + 1
        theoretical_capacity = int(active_employees * avg_capacity * working_days)

        occupancy_rate = min(
            round(completed / theoretical_capacity * 100, 1) if theoretical_capacity > 0 else 0.0,
            100.0
        )
        cancellation_rate = round(
            cancelled / total_scheduled * 100, 1
        ) if total_scheduled > 0 else 0.0
        no_show_rate = round(
            no_shows / total_scheduled * 100, 1
        ) if total_scheduled > 0 else 0.0

        return {
            'completed': completed,
            'cancelled': cancelled,
            'no_shows': no_shows,
            'total_scheduled': total_scheduled,
            'theoretical_capacity': theoretical_capacity,
            'occupancy_rate': occupancy_rate,
            'cancellation_rate': cancellation_rate,
            'no_show_rate': no_show_rate
        }

    def get_peak_hours(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Pobierz macierz rezerwacji według godziny i dnia tygodnia.

        Zwraca listę:
            {
                'day_of_week': int (0=Nd..6=Sb),
                'hour_of_day': int,
                'appointment_count': int,
                'revenue': float
            }
        """
        query = """
            SELECT
                EXTRACT(DOW FROM a.appointment_date)::int  AS day_of_week,
                EXTRACT(HOUR FROM a.start_time)::int       AS hour_of_day,
                COUNT(*)                                    AS appointment_count,
                COALESCE(SUM(i.net_amount), 0)             AS revenue
            FROM appointments a
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
              AND a.appointment_date BETWEEN %s AND %s
              AND a.start_time IS NOT NULL
            GROUP BY day_of_week, hour_of_day
            ORDER BY day_of_week, hour_of_day
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_service_price_analysis(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Porównaj ceny katalogowe z faktycznie pobranymi w danym okresie.

        Zwraca listę:
            {
                'service_name': str,
                'category': str,
                'catalogue_price': float,
                'bookings': int,
                'avg_charged': float,
                'min_charged': float,
                'total_revenue': float,
                'avg_discount_pct': float
            }
        """
        query = """
            SELECT
                s.name                                                          AS service_name,
                s.category,
                s.price                                                         AS catalogue_price,
                COUNT(aps.id)                                                   AS bookings,
                COALESCE(AVG(aps.price_charged), 0)                            AS avg_charged,
                COALESCE(MIN(aps.price_charged), 0)                            AS min_charged,
                COALESCE(SUM(aps.price_charged), 0)                            AS total_revenue,
                ROUND(
                    (1 - COALESCE(AVG(aps.price_charged), s.price) / NULLIF(s.price, 0)) * 100
                , 1)                                                            AS avg_discount_pct
            FROM services s
            LEFT JOIN (
                SELECT aps.*
                FROM appointment_services aps
                INNER JOIN appointments a ON a.id = aps.appointment_id
                    AND a.status = 'completed'
                    AND a.appointment_date BETWEEN %s AND %s
            ) aps ON aps.service_id = s.id
            WHERE s.is_active = TRUE
            GROUP BY s.id, s.name, s.category, s.price
            ORDER BY total_revenue DESC
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

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

    def get_monthly_profit_trend(self) -> List[Dict]:
        """
        Pobierz miesięczne dane przychodów, kosztów i zysku dla ostatnich 12 miesięcy.
        Okno ruchome relative to CURRENT_DATE — niezależne od wybranego okresu.
        """
        query = """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            revenue_by_month AS (
                SELECT
                    DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                    COALESCE(SUM(i.net_amount), 0)                AS revenue
                FROM appointments a
                LEFT JOIN income_records i ON i.appointment_id = a.id
                WHERE a.status = 'completed'
                  AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', a.appointment_date)::date
            ),
            commission_by_month AS (
                SELECT
                    a.employee_id,
                    DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                    COALESCE(SUM(i.commission_total), 0)           AS monthly_commission
                FROM appointments a
                LEFT JOIN income_records i ON i.appointment_id = a.id
                WHERE a.status = 'completed'
                  AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY a.employee_id, DATE_TRUNC('month', a.appointment_date)::date
            ),
            employee_costs_by_month AS (
                SELECT
                    m.month_start,
                    COALESCE(SUM(
                        GREATEST(e.base_salary, COALESCE(cm.monthly_commission, 0))
                        * (1 + COALESCE(e.employer_cost_rate, 0.22))
                    ), 0) AS employee_costs
                FROM months m
                CROSS JOIN employees e
                LEFT JOIN commission_by_month cm
                    ON cm.employee_id = e.id AND cm.month_start = m.month_start
                WHERE e.is_active = TRUE
                GROUP BY m.month_start
            ),
            invoice_costs_by_month AS (
                SELECT
                    DATE_TRUNC('month', invoice_date)::date AS month_start,
                    COALESCE(SUM(amount), 0)                AS invoice_costs
                FROM invoices
                WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', invoice_date)::date
            )
            SELECT
                m.month_start,
                COALESCE(r.revenue, 0)                                                     AS revenue,
                COALESCE(ec.employee_costs, 0)                                             AS employee_costs,
                COALESCE(ic.invoice_costs, 0)                                              AS invoice_costs,
                COALESCE(r.revenue, 0)
                    - COALESCE(ec.employee_costs, 0)
                    - COALESCE(ic.invoice_costs, 0)                                        AS profit
            FROM months m
            LEFT JOIN revenue_by_month r         ON r.month_start  = m.month_start
            LEFT JOIN employee_costs_by_month ec ON ec.month_start = m.month_start
            LEFT JOIN invoice_costs_by_month ic  ON ic.month_start = m.month_start
            ORDER BY m.month_start
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_new_clients_monthly(self) -> List[Dict]:
        """Nowi klienci wg miesiąca (first_visit_date) — ostatnie 12 miesięcy."""
        query = """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            new_per_month AS (
                SELECT
                    DATE_TRUNC('month', first_visit_date)::date AS month_start,
                    COUNT(*) AS new_clients
                FROM clients
                WHERE first_visit_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                  AND first_visit_date IS NOT NULL
                GROUP BY DATE_TRUNC('month', first_visit_date)::date
            )
            SELECT
                m.month_start,
                COALESCE(n.new_clients, 0) AS new_clients
            FROM months m
            LEFT JOIN new_per_month n ON n.month_start = m.month_start
            ORDER BY m.month_start
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_cancellation_rate_monthly(self) -> List[Dict]:
        """Wskaźnik odwołań i nieobecności wg miesiąca — ostatnie 12 miesięcy."""
        query = """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            rates_by_month AS (
                SELECT
                    DATE_TRUNC('month', appointment_date)::date AS month_start,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
                    COUNT(*) FILTER (WHERE status = 'no_show')   AS noshow_count,
                    ROUND(
                        COUNT(*) FILTER (WHERE status = 'cancelled') * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS cancellation_pct,
                    ROUND(
                        COUNT(*) FILTER (WHERE status = 'no_show') * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS noshow_pct
                FROM appointments
                WHERE appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', appointment_date)::date
            )
            SELECT
                m.month_start,
                COALESCE(r.total, 0)             AS total,
                COALESCE(r.cancellation_pct, 0)  AS cancellation_pct,
                COALESCE(r.noshow_pct, 0)        AS noshow_pct
            FROM months m
            LEFT JOIN rates_by_month r ON r.month_start = m.month_start
            ORDER BY m.month_start
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_avg_ticket_monthly(self) -> List[Dict]:
        """Średni rachunek za wizytę wg miesiąca — ostatnie 12 miesięcy."""
        query = """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            avg_by_month AS (
                SELECT
                    DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                    ROUND(AVG(i.net_amount)::numeric, 2)          AS avg_ticket
                FROM appointments a
                JOIN income_records i ON i.appointment_id = a.id
                WHERE a.status = 'completed'
                  AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', a.appointment_date)::date
            )
            SELECT
                m.month_start,
                COALESCE(ab.avg_ticket, 0) AS avg_ticket
            FROM months m
            LEFT JOIN avg_by_month ab ON ab.month_start = m.month_start
            ORDER BY m.month_start
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_service_category_mix_monthly(self) -> List[Dict]:
        """
        Przychód wg kategorii usług i miesiąca — ostatnie 12 miesięcy.
        Zwraca wiersze (month_start, category, revenue) — pivot wykonuje JS.
        """
        query = """
            SELECT
                DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                s.category,
                COALESCE(SUM(aps.price_charged), 0)           AS revenue
            FROM appointments a
            JOIN appointment_services aps ON aps.appointment_id = a.id
            JOIN services s               ON s.id = aps.service_id
            WHERE a.status = 'completed'
              AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
            GROUP BY DATE_TRUNC('month', a.appointment_date)::date, s.category
            ORDER BY month_start, s.category
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_invoice_cost_ratio_monthly(self) -> List[Dict]:
        """
        Udział kosztów faktur w przychodach wg miesiąca — ostatnie 12 miesięcy.
        Zwraca: revenue, invoice_costs, ratio_pct.
        """
        query = """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            revenue_by_month AS (
                SELECT
                    DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                    COALESCE(SUM(i.net_amount), 0)                AS revenue
                FROM appointments a
                LEFT JOIN income_records i ON i.appointment_id = a.id
                WHERE a.status = 'completed'
                  AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', a.appointment_date)::date
            ),
            invoice_by_month AS (
                SELECT
                    DATE_TRUNC('month', invoice_date)::date AS month_start,
                    COALESCE(SUM(amount), 0)                AS invoice_costs
                FROM invoices
                WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', invoice_date)::date
            )
            SELECT
                m.month_start,
                COALESCE(r.revenue, 0)        AS revenue,
                COALESCE(ic.invoice_costs, 0) AS invoice_costs,
                ROUND(
                    COALESCE(ic.invoice_costs, 0)
                    / NULLIF(COALESCE(r.revenue, 0), 0) * 100,
                    1
                ) AS ratio_pct
            FROM months m
            LEFT JOIN revenue_by_month r  ON r.month_start  = m.month_start
            LEFT JOIN invoice_by_month ic ON ic.month_start = m.month_start
            ORDER BY m.month_start
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_employee_utilisation_monthly(self) -> List[Dict]:
        """
        Wykorzystanie pracowników wg miesiąca — ostatnie 12 miesięcy.
        Formuła: appointments / (22 dni rob. × max_appointments_per_day) × 100.
        Zwraca wiersze (month_start, employee_name, utilisation_pct).
        """
        query = """
            WITH months AS (
                SELECT generate_series(
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                    DATE_TRUNC('month', CURRENT_DATE),
                    '1 month'::interval
                )::date AS month_start
            ),
            appts_by_month AS (
                SELECT
                    DATE_TRUNC('month', appointment_date)::date AS month_start,
                    employee_id,
                    COUNT(DISTINCT id) AS appointments_count
                FROM appointments
                WHERE status = 'completed'
                  AND appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
                GROUP BY DATE_TRUNC('month', appointment_date)::date, employee_id
            )
            SELECT
                m.month_start,
                e.first_name || ' ' || e.last_name         AS employee_name,
                COALESCE(ab.appointments_count, 0)          AS appointments_count,
                COALESCE(e.max_appointments_per_day, 8)     AS max_per_day,
                ROUND(
                    COALESCE(ab.appointments_count, 0) * 100.0
                    / (22 * COALESCE(e.max_appointments_per_day, 8)),
                    1
                ) AS utilisation_pct
            FROM months m
            CROSS JOIN employees e
            LEFT JOIN appts_by_month ab
                ON ab.month_start = m.month_start AND ab.employee_id = e.id
            WHERE e.is_active = TRUE
            ORDER BY m.month_start, employee_name
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_visit_frequency_distribution(self) -> List[Dict]:
        """
        Histogram częstotliwości wizyt klientów w ostatnich 12 miesiącach.
        Zwraca: [{visit_count, client_count}] — JS grupuje 10+ do jednego kubełka.
        """
        query = """
            WITH client_visits AS (
                SELECT
                    client_id,
                    COUNT(*) AS visit_count
                FROM appointments
                WHERE status = 'completed'
                  AND appointment_date >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY client_id
            )
            SELECT
                visit_count,
                COUNT(*) AS client_count
            FROM client_visits
            GROUP BY visit_count
            ORDER BY visit_count
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
