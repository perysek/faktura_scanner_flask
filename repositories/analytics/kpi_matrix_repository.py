"""
Repozytorium macierzy wskaźników biznesowych (12 miesięcy × rok, nawigacja
rok-do-roku). Każdy z 16 wskaźników z config/kpi_indicators.py ma tu funkcję
obliczeniową zwracającą surowe składowe (licznik, mianownik) na miesiąc, aby
wartość roczna była prawdziwym przeliczeniem sum (nie naiwną średnią z 12
wartości procentowych) — zgodnie z metodologią opisaną w
BUSINESS_PROCESS_KPI_REVIEW.md §4.
"""
import calendar
from datetime import date
from typing import Dict, List, Optional, Tuple

from config.database import DatabaseConnection
from config.admin_view import emp_exclusion_sql_inline
from config.kpi_indicators import PROCESSES

Component = Tuple[float, float]  # (numerator, denominator)


def _year_bounds(year: int) -> Tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _empty_months() -> Dict[int, Component]:
    return {m: (0.0, 0.0) for m in range(1, 13)}


class KpiMatrixRepository:
    """Oblicza 16 wskaźników biznesowych dla wybranego roku + rok-1."""

    def get_available_year_range(self) -> Tuple[int, int]:
        """(min_year, max_year) na podstawie danych + roku bieżącego (nigdy przyszłość)."""
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MIN(y)::int AS min_year FROM (
                SELECT EXTRACT(YEAR FROM appointment_date) AS y FROM appointments
                UNION ALL
                SELECT EXTRACT(YEAR FROM invoice_date) FROM invoices
            ) t
        """)
        row = cursor.fetchone()
        min_year = int(row['min_year']) if row and row['min_year'] else date.today().year
        max_year = date.today().year
        return min(min_year, max_year), max_year

    def get_kpi_matrix(self, year: int) -> Dict:
        """Zwraca pełną macierz: procesy → wskaźniki → {unit, direction, target,
        y_prior, months: {1..12: value|None}, y_current}."""
        active_employees = self._active_employees()
        active_services_count = self._active_services_count()

        processes_out = []
        for proc in PROCESSES:
            indicators_out = []
            for ind in proc['indicators']:
                key = ind['key']
                if 'unavailable_note' in ind:
                    indicators_out.append({
                        **ind,
                        'months': {m: None for m in range(1, 13)},
                        'y_current': None,
                        'y_prior': None,
                    })
                    continue

                compute = self._COMPUTE[key]
                current_components = compute(self, year, active_employees, active_services_count)
                current_components = self._zero_incomplete_months(current_components, year)
                prior_components = compute(self, year - 1, active_employees, active_services_count)

                months_out = {}
                for m in range(1, 13):
                    num, den = current_components.get(m, (0.0, 0.0))
                    months_out[m] = self._ratio(key, num, den)

                y_num = sum(c[0] for c in current_components.values())
                y_den = sum(c[1] for c in current_components.values())
                y1_num = sum(c[0] for c in prior_components.values())
                y1_den = sum(c[1] for c in prior_components.values())

                indicators_out.append({
                    **ind,
                    'months': months_out,
                    'y_current': self._ratio(key, y_num, y_den),
                    'y_prior': self._ratio(key, y1_num, y1_den),
                })
            processes_out.append({'id': proc['id'], 'name': proc['name'], 'indicators': indicators_out})

        return {'year': year, 'processes': processes_out}

    # ------------------------------------------------------------------
    # Shared lookups
    # ------------------------------------------------------------------

    def _active_employees(self) -> List[Dict]:
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, COALESCE(max_appointments_per_day, 8) AS max_per_day
            FROM employees
            WHERE is_active = TRUE
              {emp_exclusion_sql_inline('id')}
        """)
        return [dict(r) for r in cursor.fetchall()]

    def _active_services_count(self) -> int:
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS n FROM services WHERE is_active = TRUE AND is_deleted = FALSE")
        row = cursor.fetchone()
        return int(row['n']) if row else 0

    @staticmethod
    def _ratio(key: str, num: float, den: float) -> Optional[float]:
        if den == 0:
            return None
        if key in ('p2_satisfaction', 'p8_ocr_confidence'):
            return round(num / den, 2)
        if key in ('p2_revenue_per_hour',):
            return round(num / (den / 60.0), 2) if den else None
        if key in ('p3_visits_per_client',):
            return round(num / den, 1)
        if key in ('p5_cost_per_visit',):
            return round(num / den, 2)
        if key in ('p5_utilisation',):
            # num is already a sum of per-employee percentages; den is employee
            # count — averaging, not a share-of-total ratio, so no *100 here.
            return round(num / den, 1)
        return round(num / den * 100, 1)

    @staticmethod
    def _zero_incomplete_months(components: Dict[int, Component], year: int) -> Dict[int, Component]:
        """Strictly-future months must not contribute a synthetic zero to the
        current year's total. Indicators like occupancy, price-update coverage
        and team utilisation derive their denominator from the calendar (days
        in month / active headcount) rather than from real event rows, so an
        unstarted month would otherwise silently drag the YTD ratio down —
        e.g. viewing 2026 in July would count Aug-Dec as "0% occupancy"
        instead of "no data yet". Event-based indicators are unaffected (their
        denominator is already naturally 0 for months with no rows).
        The in-progress current month is left untouched here — indicators
        whose denominator needs day-level proration (occupancy) handle that
        themselves in their own compute function."""
        today = date.today()
        if year != today.year:
            return components
        out = dict(components)
        for m in range(today.month + 1, 13):
            out[m] = (0.0, 0.0)
        return out

    def _bucket(self, query: str, params: tuple, num_col: str, den_col: str) -> Dict[int, Component]:
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        out = _empty_months()
        for row in cursor.fetchall():
            m = int(row['month'])
            if 1 <= m <= 12:
                out[m] = (float(row[num_col] or 0), float(row[den_col] or 0))
        return out

    # ------------------------------------------------------------------
    # P1 — Rezerwacja i realizacja wizyt
    # ------------------------------------------------------------------

    def _p1_completion_rate(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM appointment_date)::int AS month,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                   COUNT(*) AS total
            FROM appointments
            WHERE appointment_date BETWEEN %s AND %s
              AND status IN ('completed', 'cancelled', 'no_show')
              {emp_exclusion_sql_inline('employee_id')}
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'completed', 'total')

    def _p1_occupancy(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM appointment_date)::int AS month,
                   COUNT(*) FILTER (WHERE status = 'completed') AS completed
            FROM appointments
            WHERE appointment_date BETWEEN %s AND %s
              AND status = 'completed'
              {emp_exclusion_sql_inline('employee_id')}
            GROUP BY 1
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start, end))
        completed_by_month = {int(r['month']): int(r['completed']) for r in cursor.fetchall()}

        active_count = len(employees)
        avg_capacity = (sum(e['max_per_day'] for e in employees) / active_count) if active_count else 8.0

        today = date.today()
        out = _empty_months()
        for m in range(1, 13):
            days_in_month = calendar.monthrange(year, m)[1]
            if year == today.year and m == today.month:
                # In-progress month: capacity so far this month, not the full
                # month — otherwise day 5 of a 31-day month always reads as a
                # deflated ~16% occupancy no matter how fully booked it is.
                # (Strictly future months are zeroed afterwards by
                # _zero_incomplete_months, so they never reach this branch's
                # "else" with a misleadingly full-month denominator.)
                days_for_capacity = min(today.day, days_in_month)
            else:
                days_for_capacity = days_in_month
            capacity = active_count * avg_capacity * days_for_capacity
            out[m] = (float(completed_by_month.get(m, 0)), float(capacity))
        return out

    # ------------------------------------------------------------------
    # P2 — Świadczenie usług i jakość obsługi
    # ------------------------------------------------------------------

    def _p2_satisfaction(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM appointment_date)::int AS month,
                   SUM(satisfaction_score) AS score_sum,
                   COUNT(satisfaction_score) AS score_count
            FROM appointments
            WHERE status = 'completed'
              AND satisfaction_score IS NOT NULL
              AND appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('employee_id')}
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'score_sum', 'score_count')

    def _p2_revenue_per_hour(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM a.appointment_date)::int AS month,
                   SUM(aps.price_charged) AS revenue_sum,
                   SUM(s.duration_minutes) AS duration_sum
            FROM appointment_services aps
            JOIN appointments a ON a.id = aps.appointment_id AND a.status = 'completed'
            JOIN services s ON s.id = aps.service_id
            WHERE a.appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('a.employee_id')}
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'revenue_sum', 'duration_sum')

    # ------------------------------------------------------------------
    # P3 — Zarządzanie relacjami z klientem i retencja
    # ------------------------------------------------------------------

    def _p3_retention(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            WITH visits AS (
                SELECT client_id, appointment_date,
                       LAG(appointment_date) OVER (PARTITION BY client_id ORDER BY appointment_date) AS prev_visit
                FROM appointments
                WHERE status = 'completed'
                  {emp_exclusion_sql_inline('employee_id')}
            )
            SELECT EXTRACT(MONTH FROM appointment_date)::int AS month,
                   COUNT(*) FILTER (WHERE appointment_date - prev_visit <= 90) AS retained,
                   COUNT(*) AS total
            FROM visits
            WHERE prev_visit IS NOT NULL
              AND appointment_date BETWEEN %s AND %s
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'retained', 'total')

    def _p3_visits_per_client(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM appointment_date)::int AS month,
                   COUNT(*) AS visits,
                   COUNT(DISTINCT client_id) AS clients
            FROM appointments
            WHERE status = 'completed'
              AND appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('employee_id')}
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'visits', 'clients')

    # ------------------------------------------------------------------
    # P4 — Zarządzanie cennikiem i ofertą usług
    # ------------------------------------------------------------------

    def _p4_price_update_coverage(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = """
            SELECT EXTRACT(MONTH FROM effective_from)::int AS month,
                   COUNT(DISTINCT service_id) AS updated
            FROM service_price_history
            WHERE effective_from BETWEEN %s AND %s
            GROUP BY 1
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start, end))
        updated_by_month = {int(r['month']): int(r['updated']) for r in cursor.fetchall()}
        out = _empty_months()
        for m in range(1, 13):
            out[m] = (float(updated_by_month.get(m, 0)), float(services_count))
        return out

    def _p4_price_realisation(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM a.appointment_date)::int AS month,
                   SUM(aps.price_charged) AS charged_sum,
                   SUM(s.price) AS catalogue_sum
            FROM appointment_services aps
            JOIN appointments a ON a.id = aps.appointment_id AND a.status = 'completed'
            JOIN services s ON s.id = aps.service_id
            WHERE a.appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('a.employee_id')}
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'charged_sum', 'catalogue_sum')

    # ------------------------------------------------------------------
    # P5 — Zarządzanie zasobami ludzkimi
    # ------------------------------------------------------------------

    def _p5_utilisation(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM appointment_date)::int AS month,
                   employee_id,
                   COUNT(*) AS cnt
            FROM appointments
            WHERE status = 'completed'
              AND appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('employee_id')}
            GROUP BY 1, 2
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start, end))
        counts = {}  # (month, employee_id) -> cnt
        for r in cursor.fetchall():
            counts[(int(r['month']), r['employee_id'])] = int(r['cnt'])

        max_per_day = {e['id']: e['max_per_day'] for e in employees}
        out = _empty_months()
        if not employees:
            return out
        for m in range(1, 13):
            util_sum = 0.0
            for emp_id, cap in max_per_day.items():
                cnt = counts.get((m, emp_id), 0)
                util_sum += (cnt * 100.0) / (22 * cap) if cap else 0.0
            # avg utilisation across employees, expressed as num/den = avg/1 so
            # _ratio()'s generic *100 path is bypassed by treating den as employee count
            out[m] = (util_sum, float(len(employees)))
        return out

    def _p5_cost_per_visit(self, year, employees, services_count) -> Dict[int, Component]:
        financials = self._monthly_financials(year)
        out = _empty_months()
        for m in range(1, 13):
            f = financials.get(m, {'employee_costs': 0.0, 'completed_count': 0})
            out[m] = (float(f['employee_costs']), float(f['completed_count']))
        return out

    # ------------------------------------------------------------------
    # P6 — Komunikacja z klientem — przypomnienia SMS
    # ------------------------------------------------------------------

    def _p6_noshow_despite_reminder(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = f"""
            SELECT EXTRACT(MONTH FROM a.appointment_date)::int AS month,
                   COUNT(*) FILTER (WHERE a.status = 'no_show') AS no_shows,
                   COUNT(*) AS total
            FROM appointments a
            WHERE a.appointment_date BETWEEN %s AND %s
              AND a.status IN ('completed', 'no_show')
              AND EXISTS (
                  SELECT 1 FROM sms_reminders r
                  WHERE r.appointment_id = a.id
                    AND r.status IN ('sent', 'delivered')
                    AND r.message_type_key LIKE 'reminder%%'
              )
              {emp_exclusion_sql_inline('a.employee_id')}
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'no_shows', 'total')

    def _p6_sms_delivery_rate(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = """
            SELECT EXTRACT(MONTH FROM sent_at)::int AS month,
                   COUNT(*) FILTER (WHERE status IN ('sent', 'delivered')) AS success,
                   COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM sms_reminders
            WHERE sent_at::date BETWEEN %s AND %s
            GROUP BY 1
        """
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start, end))
        out = _empty_months()
        for r in cursor.fetchall():
            m = int(r['month'])
            success = float(r['success'] or 0)
            failed = float(r['failed'] or 0)
            out[m] = (success, success + failed)
        return out

    # ------------------------------------------------------------------
    # P7 — Zarządzanie finansami i rentownością
    # ------------------------------------------------------------------

    def _monthly_financials(self, year: int) -> Dict[int, Dict]:
        """Współdzielone przez P5/P7: revenue, employee_costs, invoice_costs,
        completed_count na miesiąc — jedno przejście po danych, reużywane
        przez kilka wskaźników zamiast powielania zapytań."""
        if hasattr(self, '_financials_cache') and self._financials_cache.get('year') == year:
            return self._financials_cache['data']

        start, end = _year_bounds(year)
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT EXTRACT(MONTH FROM a.appointment_date)::int AS month,
                   COUNT(*) FILTER (WHERE a.status = 'completed') AS completed_count,
                   COALESCE(SUM(i.net_amount), 0) AS revenue
            FROM appointments a
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
              AND a.appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('a.employee_id')}
            GROUP BY 1
        """, (start, end))
        revenue_by_month = {int(r['month']): r for r in cursor.fetchall()}

        cursor.execute(f"""
            SELECT a.employee_id,
                   EXTRACT(MONTH FROM a.appointment_date)::int AS month,
                   COALESCE(SUM(i.commission_total), 0) AS monthly_commission
            FROM appointments a
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
              AND a.appointment_date BETWEEN %s AND %s
              {emp_exclusion_sql_inline('a.employee_id')}
            GROUP BY 1, 2
        """, (start, end))
        commission = {}
        for r in cursor.fetchall():
            commission[(r['employee_id'], int(r['month']))] = float(r['monthly_commission'] or 0)

        cursor.execute(f"""
            SELECT id, base_salary, COALESCE(employer_cost_rate, 0.22) AS cost_rate
            FROM employees
            WHERE is_active = TRUE
              {emp_exclusion_sql_inline('id')}
        """)
        active_emps = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT EXTRACT(MONTH FROM invoice_date)::int AS month,
                   COALESCE(SUM(amount), 0) AS invoice_costs
            FROM invoices
            WHERE invoice_date BETWEEN %s AND %s AND is_deleted = FALSE
            GROUP BY 1
        """, (start, end))
        invoice_by_month = {int(r['month']): float(r['invoice_costs'] or 0) for r in cursor.fetchall()}

        out = {}
        for m in range(1, 13):
            rev_row = revenue_by_month.get(m)
            revenue = float(rev_row['revenue']) if rev_row else 0.0
            completed_count = int(rev_row['completed_count']) if rev_row else 0
            employee_costs = 0.0
            for e in active_emps:
                gross = max(float(e['base_salary'] or 0), commission.get((e['id'], m), 0.0))
                employee_costs += gross * (1 + float(e['cost_rate']))
            invoice_costs = invoice_by_month.get(m, 0.0)
            out[m] = {
                'revenue': revenue,
                'employee_costs': employee_costs,
                'invoice_costs': invoice_costs,
                'completed_count': completed_count,
            }

        self._financials_cache = {'year': year, 'data': out}
        return out

    def _p7_net_margin(self, year, employees, services_count) -> Dict[int, Component]:
        financials = self._monthly_financials(year)
        out = _empty_months()
        for m in range(1, 13):
            f = financials.get(m, {})
            revenue = f.get('revenue', 0.0)
            net_profit = revenue - f.get('employee_costs', 0.0) - f.get('invoice_costs', 0.0)
            out[m] = (float(net_profit), float(revenue))
        return out

    def _p7_cost_ratio(self, year, employees, services_count) -> Dict[int, Component]:
        financials = self._monthly_financials(year)
        out = _empty_months()
        for m in range(1, 13):
            f = financials.get(m, {})
            total_costs = f.get('employee_costs', 0.0) + f.get('invoice_costs', 0.0)
            out[m] = (float(total_costs), float(f.get('revenue', 0.0)))
        return out

    # ------------------------------------------------------------------
    # P8 — Zaopatrzenie i zarządzanie dostawcami
    # ------------------------------------------------------------------

    def _p8_invoice_settlement(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = """
            SELECT EXTRACT(MONTH FROM invoice_date)::int AS month,
                   COUNT(*) FILTER (WHERE status = 'Opłacona') AS paid,
                   COUNT(*) AS total
            FROM invoices
            WHERE invoice_date BETWEEN %s AND %s AND is_deleted = FALSE
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'paid', 'total')

    def _p8_ocr_confidence(self, year, employees, services_count) -> Dict[int, Component]:
        start, end = _year_bounds(year)
        query = """
            SELECT EXTRACT(MONTH FROM invoice_date)::int AS month,
                   SUM(ocr_confidence) AS conf_sum,
                   COUNT(ocr_confidence) AS conf_count
            FROM invoices
            WHERE invoice_date BETWEEN %s AND %s AND is_deleted = FALSE
            GROUP BY 1
        """
        return self._bucket(query, (start, end), 'conf_sum', 'conf_count')

    # ------------------------------------------------------------------
    # Dispatch table
    # ------------------------------------------------------------------

    _COMPUTE = {
        'p1_completion_rate': _p1_completion_rate,
        'p1_occupancy': _p1_occupancy,
        'p2_satisfaction': _p2_satisfaction,
        'p2_revenue_per_hour': _p2_revenue_per_hour,
        'p3_retention': _p3_retention,
        'p3_visits_per_client': _p3_visits_per_client,
        'p4_price_update_coverage': _p4_price_update_coverage,
        'p4_price_realisation': _p4_price_realisation,
        'p5_utilisation': _p5_utilisation,
        'p5_cost_per_visit': _p5_cost_per_visit,
        'p6_noshow_despite_reminder': _p6_noshow_despite_reminder,
        'p6_sms_delivery_rate': _p6_sms_delivery_rate,
        'p7_net_margin': _p7_net_margin,
        'p7_cost_ratio': _p7_cost_ratio,
        'p8_invoice_settlement': _p8_invoice_settlement,
        'p8_ocr_confidence': _p8_ocr_confidence,
    }
