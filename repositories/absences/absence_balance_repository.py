"""
Repository do obliczania bilansu nieobecności (tylko odczyt).

Oblicza sumę wykorzystanych dni/godzin z tabeli employee_absences
oraz sumę delta_value z absence_balance_adjustments.
"""
from datetime import date
from typing import List

from config.database import get_db_connection
from config.admin_view import emp_exclusion_sql_inline


class AbsenceBalanceRepository:
    """Read-only repository do obliczania bilansu nieobecności."""

    def compute_used(self, employee_id: int, category_id: int,
                     period_start: date, full_day: bool) -> float:
        """
        Sumuje wykorzystane dni (full_day=True) lub godziny (full_day=False)
        dla zatwierdzonych, nie-usuniętych nieobecności od period_start.
        """
        if full_day:
            value_expr = "SUM(ea.date_to - ea.date_from + 1)"
        else:
            value_expr = (
                "SUM(EXTRACT(EPOCH FROM (ea.time_to - ea.time_from)) / 3600.0)"
            )

        query = f"""
            SELECT COALESCE({value_expr}, 0.0) AS total
            FROM employee_absences ea
            WHERE ea.employee_id = %s
              AND ea.category_id = %s
              AND ea.status = 'approved'
              AND ea.is_deleted = FALSE
              AND ea.date_from >= %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, category_id, period_start))
            row = cursor.fetchone()
            return float(row['total'] or 0.0)

    def compute_adjustments(self, employee_id: int, category_id: int) -> float:
        """
        Sumuje delta_value ze wszystkich nie-usuniętych korekt.
        Bez filtra okresu — korekty zawsze kumulatywne.
        """
        query = """
            SELECT COALESCE(SUM(delta_value), 0.0) AS total
            FROM absence_balance_adjustments
            WHERE employee_id = %s
              AND category_id = %s
              AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, category_id))
            row = cursor.fetchone()
            return float(row['total'] or 0.0)

    def bulk_summary_for_list(self) -> List[dict]:
        """
        Jedno zapytanie: dla każdego aktywnego pracownika zwraca dane
        dotyczące pierwszej śledzonej kategorii (najniższe category_id).

        Używane do kolumny 'Bilans urlopu' na liście pracowników.
        Zwraca listę słowników:
          {employee_id, category_id, category_name, full_day, used, limit,
           warning_threshold_pct, pct, status}
        """
        query = f"""
            WITH tracked AS (
                SELECT ac.id AS category_id,
                       ac.name AS category_name,
                       ac.absence_full_day,
                       ac.count_period,
                       ac.resets_at,
                       ac.rolling_days,
                       ac.warning_threshold_pct,
                       ac.default_max_value
                FROM absence_categories ac
                WHERE ac.is_tracked = TRUE AND ac.is_deleted = FALSE
                ORDER BY ac.id
            ),
            employees_active AS (
                SELECT e.id AS employee_id
                FROM employees e
                WHERE e.is_active = TRUE
                  {emp_exclusion_sql_inline('e.id')}
            ),
            -- pick the first tracked category (lowest id) per employee
            primary_cat AS (
                SELECT ea_emp.employee_id, t.category_id,
                       t.category_name, t.absence_full_day,
                       t.count_period, t.resets_at, t.rolling_days,
                       t.warning_threshold_pct, t.default_max_value,
                       ROW_NUMBER() OVER (PARTITION BY ea_emp.employee_id
                                          ORDER BY t.category_id) AS rn
                FROM employees_active ea_emp
                CROSS JOIN tracked t
            ),
            primary_only AS (
                SELECT * FROM primary_cat WHERE rn = 1
            ),
            -- effective limit (employee override > category default)
            eff_limit AS (
                SELECT po.employee_id, po.category_id,
                       COALESCE(eal.max_value, po.default_max_value) AS eff_max,
                       po.category_name, po.absence_full_day,
                       po.count_period, po.resets_at, po.rolling_days,
                       po.warning_threshold_pct
                FROM primary_only po
                LEFT JOIN employee_absence_limits eal
                       ON eal.employee_id = po.employee_id
                      AND eal.category_id = po.category_id
                      AND eal.is_deleted = FALSE
            ),
            -- adjustments sum
            adj AS (
                SELECT employee_id, category_id,
                       COALESCE(SUM(delta_value), 0.0) AS adj_total
                FROM absence_balance_adjustments
                WHERE is_deleted = FALSE
                GROUP BY employee_id, category_id
            )
            SELECT el.employee_id,
                   el.category_id,
                   el.category_name,
                   el.absence_full_day AS full_day,
                   el.eff_max AS lim,
                   el.warning_threshold_pct,
                   COALESCE(adj.adj_total, 0.0) AS adj_total
            FROM eff_limit el
            LEFT JOIN adj ON adj.employee_id = el.employee_id
                         AND adj.category_id = el.category_id
            ORDER BY el.employee_id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]
