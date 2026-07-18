"""
Repository dla operacji na wizytach (appointments)
"""
import uuid
from decimal import Decimal
from typing import Any, List, Optional
from datetime import datetime, date, time
from config.database import get_db_connection, safe_commit
from config.admin_view import emp_exclusion_sql
from config.appointment_statuses import AppointmentStatus
from database.models import Appointment
from repositories.db_utils import parse_dt, parse_date, parse_time


class AppointmentRepository:
    """Repository do zarządzania wizytami w salonie"""

    def row_to_appointment(self, row: Any) -> Optional[Appointment]:
        """Konwertuj Row na obiekt Appointment"""
        if not row:
            return None

        return Appointment(
            id=row['id'],
            client_id=row['client_id'],
            employee_id=row['employee_id'],
            status=row['status'],
            appointment_date=parse_date(row['appointment_date']),
            start_time=parse_time(row['start_time']),
            end_time=parse_time(row['end_time']),
            total_price=Decimal(str(row['total_price'])) if row['total_price'] is not None else Decimal('0'),
            total_duration=row['total_duration'] or 0,
            discount_amount=Decimal(str(row['discount_amount'])) if row['discount_amount'] is not None else Decimal('0'),
            notes=row['notes'],
            cancellation_reason=row['cancellation_reason'],
            cancelled_at=parse_dt(row['cancelled_at']),
            satisfaction_score=row['satisfaction_score'] if 'satisfaction_score' in row.keys() else None,
            created_by=row['created_by'],
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at'])
        )

    def create(self, appt: Appointment) -> int:
        """Utwórz nową wizytę"""
        query = """
            INSERT INTO appointments (
                client_id, employee_id, status, appointment_date,
                start_time, end_time, total_price, total_duration,
                discount_amount, notes, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                appt.client_id,
                appt.employee_id,
                appt.status,
                appt.appointment_date.isoformat(),
                appt.start_time.strftime('%H:%M:%S'),
                appt.end_time.strftime('%H:%M:%S'),
                str(appt.total_price),
                appt.total_duration,
                str(appt.discount_amount),
                appt.notes,
                appt.created_by
            ))
            result_id = cursor.fetchone()["id"]
            safe_commit(conn)
            return result_id

    def get_by_id(self, appointment_id: int) -> Optional[Any]:
        """Pobierz wizytę po ID"""
        query = "SELECT * FROM appointments WHERE id = %s AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchone()

    def get_by_id_with_details(self, appointment_id: int) -> Optional[Any]:
        """Pobierz wizytę z danymi klienta i pracownika"""
        query = """
            SELECT
                a.*,
                c.first_name || ' ' || c.last_name as client_name,
                c.phone as client_phone,
                e.first_name || ' ' || e.last_name as employee_name,
                e.position as employee_position
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            JOIN employees e ON e.id = a.employee_id
            WHERE a.id = %s AND a.is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            return cursor.fetchone()

    def get_by_date_range(self, start_date: date, end_date: date,
                           employee_id: Optional[int] = None,
                           status: Optional[str] = None) -> List[Any]:
        """Pobierz wizyty w zakresie dat"""
        params = [start_date.isoformat(), end_date.isoformat()]
        filters = ["a.is_deleted = FALSE", "a.appointment_date BETWEEN %s AND %s"]

        if employee_id:
            filters.append("a.employee_id = %s")
            params.append(employee_id)
        if status:
            filters.append("a.status = %s")
            params.append(status)

        # Widok administratora: hide superuser-linked employees unless admin view is ON.
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        where_clause = " AND ".join(filters)
        query = f"""
            SELECT
                a.*,
                c.first_name || ' ' || c.last_name as client_name,
                e.first_name || ' ' || e.last_name as employee_name,
                STRING_AGG(
                    CASE WHEN aps.is_addon = FALSE THEN s.name ELSE NULL END, ', '
                ) as service_name,
                STRING_AGG(
                    CASE WHEN aps.is_addon = TRUE THEN s.name ELSE NULL END, ', '
                ) as addon_services
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
            LEFT JOIN services s ON s.id = aps.service_id
            WHERE {where_clause} {excl_sql}
            GROUP BY a.id, c.first_name, c.last_name, e.first_name, e.last_name
            ORDER BY a.appointment_date DESC, a.start_time DESC
        """
        params.extend(excl_params)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    # Whitelist of columns the table editor may sort by → safe SQL expression.
    # Keys are the frontend `data-col` values; never interpolate raw user input.
    _TABLE_SORT_EXPR = {
        'id': 'a.id',
        'appointment_date': 'a.appointment_date',
        'start_time': 'a.start_time',
        'client_name': "(c.first_name || ' ' || c.last_name)",
        'employee_name': "(e.first_name || ' ' || e.last_name)",
        'status': 'a.status',
        'total_price': 'a.total_price',
        'satisfaction_score': 'a.satisfaction_score',
    }
    # Per-column substring filters that map to a single scalar expression.
    # `status` and `service_name` are handled specially (label mapping / aggregate).
    _TABLE_FILTER_EXPR = {
        'id': 'CAST(a.id AS TEXT)',
        'appointment_date': 'CAST(a.appointment_date AS TEXT)',
        'start_time': 'CAST(a.start_time AS TEXT)',
        'client_name': "(c.first_name || ' ' || c.last_name)",
        'employee_name': "(e.first_name || ' ' || e.last_name)",
        'notes': "COALESCE(a.notes, '')",
    }

    def get_latest(self, limit: int = 100, offset: int = 0,
                   employee_id: Optional[int] = None,
                   status: Optional[str] = None,
                   sort_col: Optional[str] = None,
                   sort_dir: str = 'desc',
                   filters: Optional[dict] = None) -> List[Any]:
        """Pobierz wizyty do edytowalnej tabeli — z paginacją, sortowaniem i filtrami.

        Sortowanie i filtrowanie po kolumnach są realizowane PO STRONIE SERWERA, na
        całym zbiorze danych, a dopiero potem stosowana jest paginacja (LIMIT/OFFSET).
        Dzięki temu kolejne strony to wycinki tego samego, w pełni posortowanego i
        przefiltrowanego wyniku — kliknięcie sortowania lub wpisanie filtra zwraca
        „dokładnie te wiersze, które byłyby widoczne, gdyby całą bazę posortowano i
        przefiltrowano", a nie tylko już załadowaną stronę.

        Args:
            sort_col: nazwa kolumny z ``_TABLE_SORT_EXPR`` (spoza whitelisty → ignorowana,
                użyta domyślna kolejność malejąco po dacie i godzinie).
            sort_dir: 'asc' albo 'desc'.
            filters: dict ``{kolumna: podciąg}`` — dozwolone klucze to klucze
                ``_TABLE_FILTER_EXPR`` plus ``status`` i ``service_name``.

        Każdy wiersz zawiera dodatkowo ``total_count`` — łączną liczbę wizyt pasujących
        do filtrów (przez ``COUNT(*) OVER()``), żeby UI mógł pokazać „N / total".
        Domyślne wywołanie (bez sort_col/filters) zachowuje dotychczasowe zachowanie.
        """
        params: list = []
        where = ["a.is_deleted = FALSE"]

        if employee_id:
            where.append("a.employee_id = %s")
            params.append(employee_id)
        if status:
            where.append("a.status = %s")
            params.append(status)

        # ── per-column filters (server-side, across the whole dataset) ──────────
        filters = filters or {}
        for col, expr in self._TABLE_FILTER_EXPR.items():
            val = filters.get(col)
            if val:
                where.append(f"{expr} ILIKE %s")
                params.append(f"%{val}%")

        # status: match raw value OR the Polish label (mirrors the client filter)
        if filters.get('status'):
            sval = f"%{filters['status']}%"
            where.append(
                "(a.status ILIKE %s OR CASE a.status "
                "WHEN 'scheduled' THEN 'zaplanowana' "
                "WHEN 'confirmed' THEN 'potwierdzona' "
                "WHEN 'in_progress' THEN 'w trakcie' "
                "WHEN 'completed' THEN 'zakonczona' "
                "WHEN 'cancelled' THEN 'anulowana' "
                "WHEN 'no_show' THEN 'nieobecnosc' "
                "ELSE a.status END ILIKE %s)"
            )
            params.extend([sval, sval])

        # service_name is an aggregate (STRING_AGG) — filter via EXISTS, matching any
        # main-or-addon service name (same as the client which joins all services).
        if filters.get('service_name'):
            where.append(
                "EXISTS (SELECT 1 FROM appointment_services aps2 "
                "JOIN services s2 ON s2.id = aps2.service_id "
                "WHERE aps2.appointment_id = a.id AND s2.name ILIKE %s)"
            )
            params.append(f"%{filters['service_name']}%")

        # Widok administratora: exclusion rides inside the WHERE, so its params are
        # bound before the trailing LIMIT/OFFSET params extended just below.
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        where_clause = "WHERE " + " AND ".join(where) + excl_sql
        params.extend(excl_params)

        # ── deterministic ORDER BY (id tiebreaker → stable offset pagination) ───
        direction = 'ASC' if str(sort_dir).lower() == 'asc' else 'DESC'
        if not sort_col:
            order_by = "ORDER BY a.appointment_date DESC, a.start_time DESC, a.id DESC"
        elif sort_col == 'appointment_date':
            order_by = (f"ORDER BY a.appointment_date {direction}, "
                        f"a.start_time {direction}, a.id DESC")
        elif sort_col in self._TABLE_SORT_EXPR:
            order_by = (f"ORDER BY {self._TABLE_SORT_EXPR[sort_col]} {direction} "
                        f"NULLS LAST, a.id DESC")
        else:
            order_by = "ORDER BY a.appointment_date DESC, a.start_time DESC, a.id DESC"

        params.extend([limit, offset])
        query = f"""
            SELECT
                a.*,
                c.first_name || ' ' || c.last_name as client_name,
                e.first_name || ' ' || e.last_name as employee_name,
                STRING_AGG(
                    CASE WHEN aps.is_addon = FALSE THEN s.name ELSE NULL END, ', '
                ) as service_name,
                STRING_AGG(
                    CASE WHEN aps.is_addon = TRUE THEN s.name ELSE NULL END, ', '
                ) as addon_services,
                COUNT(*) OVER() AS total_count
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
            LEFT JOIN services s ON s.id = aps.service_id
            {where_clause}
            GROUP BY a.id, c.first_name, c.last_name, e.first_name, e.last_name
            {order_by}
            LIMIT %s OFFSET %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_daily_schedule(self, employee_id: int, schedule_date: date) -> List[Any]:
        """Pobierz harmonogram dnia pracownika z nazwami usług"""
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        query = f"""
            SELECT
                a.*,
                c.first_name || ' ' || c.last_name as client_name,
                c.phone as client_phone,
                e.first_name || ' ' || e.last_name as employee_name,
                STRING_AGG(s.name, ', ') as service_name
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
            LEFT JOIN services s ON s.id = aps.service_id
            WHERE a.employee_id = %s AND a.appointment_date = %s
            AND a.status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
            AND a.is_deleted = FALSE {excl_sql}
            GROUP BY a.id, c.first_name, c.last_name, c.phone, e.first_name, e.last_name
            ORDER BY a.start_time
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, schedule_date.isoformat(), *excl_params))
            return cursor.fetchall()

    def get_multi_employee_schedule(self, schedule_date: date,
                                      employee_ids: Optional[List[int]] = None) -> dict:
        """
        Pobierz harmonogram dnia dla wielu pracowników jednocześnie.

        Args:
            schedule_date: Data harmonogramu
            employee_ids: Lista ID pracowników (opcjonalne - jeśli None, pobierze wszystkich z wizytami tego dnia)

        Returns:
            dict: {
                'employees': [{'id': int, 'full_name': str, 'position': str}, ...],
                'schedules': {employee_id: [appointments...], ...}
            }
        """
        # Widok administratora: drop superuser-linked employees from the day's
        # employee column set (and from the appointments pulled below) unless ON.
        emp_excl_sql, emp_excl_params = emp_exclusion_sql('e.id')
        appt_excl_sql, appt_excl_params = emp_exclusion_sql('a.employee_id')
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Jeśli nie podano employee_ids, znajdź wszystkich pracowników z wizytami tego dnia
            if employee_ids is None:
                query_employees = f"""
                    SELECT DISTINCT
                        e.id,
                        e.first_name || ' ' || e.last_name as full_name,
                        e.position
                    FROM employees e
                    JOIN appointments a ON a.employee_id = e.id
                    WHERE a.appointment_date = %s
                    AND a.status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
                    AND a.is_deleted = FALSE
                    AND e.is_active = TRUE {emp_excl_sql}
                    ORDER BY full_name
                """
                cursor.execute(query_employees, (schedule_date.isoformat(), *emp_excl_params))
            else:
                # Użyj podanych employee_ids
                placeholders = ','.join('%s' * len(employee_ids))
                query_employees = f"""
                    SELECT
                        e.id,
                        e.first_name || ' ' || e.last_name as full_name,
                        e.position
                    FROM employees e
                    WHERE e.id IN ({placeholders})
                    AND e.is_active = TRUE {emp_excl_sql}
                    ORDER BY e.first_name, e.last_name
                """
                cursor.execute(query_employees, [*employee_ids, *emp_excl_params])

            employees = [dict(row) for row in cursor.fetchall()]

            # Bulk fetch all appointments for found employees in one query
            schedules: dict = {emp['id']: [] for emp in employees}

            if employees:
                emp_ids = [emp['id'] for emp in employees]
                placeholders = ','.join(['%s'] * len(emp_ids))
                query_all_appointments = f"""
                    SELECT
                        a.*,
                        c.first_name || ' ' || c.last_name AS client_name,
                        c.phone AS client_phone,
                        e.first_name || ' ' || e.last_name AS employee_name,
                        STRING_AGG(s.name, ', ' ORDER BY s.name) AS service_name,
                        STRING_AGG(
                            CASE WHEN aps.is_addon = TRUE THEN s.name ELSE NULL END,
                            ', ' ORDER BY s.name
                        ) AS addon_services
                    FROM appointments a
                    JOIN clients c ON c.id = a.client_id
                    JOIN employees e ON e.id = a.employee_id
                    LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
                    LEFT JOIN services s ON s.id = aps.service_id
                    WHERE a.employee_id IN ({placeholders})
                      AND a.appointment_date = %s
                      AND a.is_deleted = FALSE {appt_excl_sql}
                    GROUP BY a.id, c.first_name, c.last_name, c.phone, e.first_name, e.last_name
                    ORDER BY a.employee_id, a.start_time
                """
                params = emp_ids + [schedule_date.isoformat()] + appt_excl_params
                cursor.execute(query_all_appointments, params)
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    emp_id = row_dict['employee_id']
                    if emp_id in schedules:
                        schedules[emp_id].append(row_dict)

            return {
                'employees': employees,
                'schedules': schedules
            }

    def check_conflicts(self, employee_id: int, appt_date: date,
                         start_time: time, end_time: time,
                         exclude_appointment_id: Optional[int] = None) -> List[Any]:
        """Sprawdź konflikty czasowe w harmonogramie pracownika.

        Zwraca listę kolidujących wizyt (pusta = brak konfliktu).
        """
        params = [employee_id, appt_date.isoformat(),
                  start_time.strftime('%H:%M:%S'), end_time.strftime('%H:%M:%S')]
        exclude_filter = ""

        if exclude_appointment_id:
            exclude_filter = "AND a.id != %s"
            params.append(exclude_appointment_id)

        query = f"""
            SELECT a.* FROM appointments a
            WHERE a.employee_id = %s AND a.appointment_date = %s
            AND a.start_time < %s AND a.end_time > %s
            AND a.status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
            AND a.is_deleted = FALSE
            {exclude_filter}
        """
        # Note: params order for conflict detection:
        # start_time < proposed_end AND end_time > proposed_start
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Fix param order: WHERE start_time < end_time AND end_time > start_time
            cursor.execute(query, (
                employee_id,
                appt_date.isoformat(),
                end_time.strftime('%H:%M:%S'),    # existing.start_time < proposed.end_time
                start_time.strftime('%H:%M:%S'),   # existing.end_time > proposed.start_time
                *([exclude_appointment_id] if exclude_appointment_id else [])
            ))
            return cursor.fetchall()

    def check_client_conflicts(self, client_id: int, appt_date: date,
                                start_time: time, end_time: time,
                                exclude_appointment_id: Optional[int] = None) -> List[Any]:
        """
        Sprawdź konflikty czasowe w harmonogramie klienta.

        Wykrywa sytuację gdy klient ma już zaplanowaną wizytę (z dowolnym pracownikiem)
        w nakładającym się czasie.

        Args:
            client_id: ID klienta
            appt_date: Data wizyty
            start_time: Godzina rozpoczęcia
            end_time: Godzina zakończenia
            exclude_appointment_id: ID wizyty do wykluczenia (przy edycji)

        Returns:
            Lista kolidujących wizyt (pusta = brak konfliktu)
        """
        params = [client_id, appt_date.isoformat(),
                  start_time.strftime('%H:%M:%S'), end_time.strftime('%H:%M:%S')]
        exclude_filter = ""

        if exclude_appointment_id:
            exclude_filter = "AND a.id != %s"
            params.append(exclude_appointment_id)

        query = f"""
            SELECT
                a.*,
                e.first_name || ' ' || e.last_name as employee_name
            FROM appointments a
            LEFT JOIN employees e ON e.id = a.employee_id
            WHERE a.client_id = %s AND a.appointment_date = %s
            AND a.start_time < %s AND a.end_time > %s
            AND a.status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
            AND a.is_deleted = FALSE
            {exclude_filter}
        """
        # Logika konfliktu: existing.start_time < proposed.end_time AND existing.end_time > proposed.start_time
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                client_id,
                appt_date.isoformat(),
                end_time.strftime('%H:%M:%S'),    # existing.start_time < proposed.end_time
                start_time.strftime('%H:%M:%S'),   # existing.end_time > proposed.start_time
                *([exclude_appointment_id] if exclude_appointment_id else [])
            ))
            return cursor.fetchall()

    def get_appointments_in_range(self, employee_id: int,
                                   date_from: date, date_to: date) -> List[Any]:
        """Fetch all active appointments for an employee in a date range.

        Returns only appointment_date, start_time, end_time — enough for
        bulk in-memory conflict checking (avoids per-slot DB queries).
        """
        query = f"""
            SELECT appointment_date, start_time, end_time
            FROM appointments
            WHERE employee_id = %s
              AND appointment_date BETWEEN %s AND %s
              AND status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
              AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, date_from.isoformat(), date_to.isoformat()))
            return cursor.fetchall()

    def reset_confirmation(self, appointment_id: int) -> bool:
        """Wyczyść odpowiedź klienta (SMS link) — używane gdy pracownik ręcznie zmienia status."""
        query = """
            UPDATE appointments
            SET confirmation_status = NULL, confirmation_updated_at = NULL
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            safe_commit(conn)
            return cursor.rowcount > 0

    def update_status(self, appointment_id: int, new_status: str,
                       cancellation_reason: Optional[str] = None) -> bool:
        """Zaktualizuj status wizyty"""
        if new_status == AppointmentStatus.CANCELLED:
            query = """
                UPDATE appointments
                SET status = %s, cancellation_reason = %s, cancelled_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    confirmation_status = NULL, confirmation_updated_at = NULL
                WHERE id = %s
            """
            params = (new_status, cancellation_reason, appointment_id)
        else:
            query = """
                UPDATE appointments
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
            params = (new_status, appointment_id)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            safe_commit(conn)
            return cursor.rowcount > 0

    def update_satisfaction_score(self, appointment_id: int, score: int) -> bool:
        """Ustaw ocenę satysfakcji (1–5) tylko dla zakończonych wizyt. Zwraca True jeśli zaktualizowano."""
        query = f"""
            UPDATE appointments
            SET satisfaction_score = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = '{AppointmentStatus.COMPLETED}'
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (score, appointment_id))
            safe_commit(conn)
            return cursor.fetchone() is not None

    def update_total_price(self, appointment_id: int, new_total: Decimal) -> bool:
        """Zaktualizuj łączną cenę wizyty (po dodaniu mikrousługi)"""
        query = """
            UPDATE appointments
            SET total_price = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (str(new_total), appointment_id))
            safe_commit(conn)
            return cursor.rowcount > 0

    def update(self, appointment_id: int, appt: Appointment) -> bool:
        """Zaktualizuj wizytę"""
        query = """
            UPDATE appointments
            SET client_id = %s, employee_id = %s, appointment_date = %s,
                start_time = %s, end_time = %s, status = %s,
                total_price = %s, total_duration = %s, discount_amount = %s,
                satisfaction_score = %s, notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                appt.client_id,
                appt.employee_id,
                appt.appointment_date.isoformat(),
                appt.start_time.strftime('%H:%M:%S'),
                appt.end_time.strftime('%H:%M:%S'),
                appt.status,
                str(appt.total_price),
                appt.total_duration,
                str(appt.discount_amount) if appt.discount_amount else '0',
                appt.satisfaction_score,
                appt.notes,
                appointment_id
            ))
            safe_commit(conn)
            return cursor.rowcount > 0

    def delete(self, appointment_id: int) -> bool:
        """Soft-delete wizyte (oznacz jako usunietą)"""
        query = "UPDATE appointments SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP WHERE id = %s AND is_deleted = FALSE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            safe_commit(conn)
            return cursor.rowcount > 0

    def restore(self, appointment_id: int) -> bool:
        """Przywroc soft-deleted wizyte"""
        query = "UPDATE appointments SET is_deleted = FALSE, deleted_at = NULL WHERE id = %s AND is_deleted = TRUE"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            safe_commit(conn)
            return cursor.rowcount > 0

    def get_client_appointments(self, client_id: int, limit: int = 20) -> List[Any]:
        """Pobierz wizyty klienta"""
        # Widok administratora: the client's visit history omits owner appointments
        # unless ON. Exclusion params sit before LIMIT (WHERE precedes LIMIT).
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        query = f"""
            SELECT
                a.*,
                e.first_name || ' ' || e.last_name as employee_name
            FROM appointments a
            JOIN employees e ON e.id = a.employee_id
            WHERE a.client_id = %s AND a.is_deleted = FALSE {excl_sql}
            ORDER BY a.appointment_date DESC, a.start_time DESC
            LIMIT %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id, *excl_params, limit))
            return cursor.fetchall()

    def count_by_date(self, schedule_date: date, employee_id: Optional[int] = None) -> int:
        """Policz wizyty na dany dzień"""
        params = [schedule_date.isoformat()]
        employee_filter = ""
        if employee_id:
            employee_filter = "AND employee_id = %s"
            params.append(employee_id)

        query = f"""
            SELECT COUNT(*) as cnt FROM appointments
            WHERE appointment_date = %s AND status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
            AND is_deleted = FALSE
            {employee_filter}
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchone()['cnt']

    def find_conflicting_appointments(
        self,
        employee_id: int,
        appointment_date: date,
        start_time: time,
        end_time: time,
        exclude_appointment_id: Optional[int] = None
    ) -> List[Any]:
        """
        Znajdź wizyty które kolidują z podanym przedziałem czasowym.
        Wizyta koliduje gdy przedziały się nakładają.

        Logika: Dwa przedziały [A_start, A_end) i [B_start, B_end) nakładają się gdy:
        A_start < B_end AND A_end > B_start
        """
        # Convert time to string format for SQLite (HH:MM:SS)
        start_str = start_time.strftime('%H:%M:%S')
        end_str = end_time.strftime('%H:%M:%S')

        params = [
            employee_id,
            appointment_date.isoformat(),
            end_str,      # new_end for: existing_start < new_end
            start_str     # new_start for: existing_end > new_start
        ]

        exclude_filter = ""
        if exclude_appointment_id:
            exclude_filter = "AND a.id != %s"
            params.append(exclude_appointment_id)

        query = f"""
            SELECT
                a.id, a.start_time, a.end_time, a.client_id,
                c.first_name || ' ' || c.last_name as client_name
            FROM appointments a
            LEFT JOIN clients c ON c.id = a.client_id
            WHERE
                a.employee_id = %s
                AND a.appointment_date = %s
                AND a.status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
                AND a.is_deleted = FALSE
                AND a.start_time < %s
                AND a.end_time > %s
                {exclude_filter}
            ORDER BY a.start_time
        """

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_adjacent_appointments(self, appointment_id: int, mode: str = 'all') -> dict:
        """
        Zwraca ID poprzedniej i następnej wizyty.
        mode='all'  – globalna kolejność wg (appointment_date, start_time)
        mode='day'  – tylko wizyty z tego samego dnia, wg start_time
        """
        def row_to_dict(r):
            if not r:
                return None
            return {
                'id': r['id'],
                'appointment_date': str(r['appointment_date']),
                'start_time': str(r['start_time'])[:5],
                'client_name': r['client_name']
            }

        # Widok administratora: prev/next navigation must SKIP hidden-employee
        # appointments (the by-id anchor lookup below stays unfiltered so the
        # current record can always be located).
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT appointment_date, start_time FROM appointments WHERE id = %s AND is_deleted = FALSE",
                (appointment_id,)
            )
            current = cursor.fetchone()
            if not current:
                return {'prev': None, 'next': None}

            cur_date = current['appointment_date']
            cur_time = current['start_time']

            if mode == 'day':
                cursor.execute(f"""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE a.appointment_date = %s AND a.start_time < %s AND a.id != %s
                    AND a.is_deleted = FALSE {excl_sql}
                    ORDER BY a.start_time DESC LIMIT 1
                """, (cur_date, cur_time, appointment_id, *excl_params))
                prev_row = cursor.fetchone()

                cursor.execute(f"""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE a.appointment_date = %s AND a.start_time > %s AND a.id != %s
                    AND a.is_deleted = FALSE {excl_sql}
                    ORDER BY a.start_time ASC LIMIT 1
                """, (cur_date, cur_time, appointment_id, *excl_params))
                next_row = cursor.fetchone()
            else:  # mode='all'
                cursor.execute(f"""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE (a.appointment_date, a.start_time) < (%s, %s) AND a.id != %s
                    AND a.is_deleted = FALSE {excl_sql}
                    ORDER BY a.appointment_date DESC, a.start_time DESC LIMIT 1
                """, (cur_date, cur_time, appointment_id, *excl_params))
                prev_row = cursor.fetchone()

                cursor.execute(f"""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE (a.appointment_date, a.start_time) > (%s, %s) AND a.id != %s
                    AND a.is_deleted = FALSE {excl_sql}
                    ORDER BY a.appointment_date ASC, a.start_time ASC LIMIT 1
                """, (cur_date, cur_time, appointment_id, *excl_params))
                next_row = cursor.fetchone()

        return {'prev': row_to_dict(prev_row), 'next': row_to_dict(next_row)}

    def update_confirmation_token(self, appointment_id: int, token: str) -> bool:
        query = "UPDATE appointments SET confirmation_token = %s WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (token, appointment_id))
            safe_commit(conn)
            return cursor.rowcount > 0

    def get_by_confirmation_token(self, token: str) -> Optional[Any]:
        query = """
            SELECT a.*, e.first_name || ' ' || e.last_name AS employee_name
            FROM appointments a
            LEFT JOIN employees e ON e.id = a.employee_id
            WHERE a.confirmation_token = %s AND a.is_deleted IS NOT TRUE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (token,))
            return cursor.fetchone()

    def update_confirmation_status(self, appointment_id: int, status: str) -> bool:
        query = """
            UPDATE appointments
            SET confirmation_status = %s, confirmation_updated_at = NOW()
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, appointment_id))
            safe_commit(conn)
            return cursor.rowcount > 0

    def get_appointments_due_for_type(self, hours_before: int,
                                       message_type_key: str) -> List[Any]:
        query = """
            SELECT a.*, c.phone, c.first_name AS client_first_name
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            WHERE a.status IN ('scheduled', 'pending', 'confirmed')
              AND a.is_deleted IS NOT TRUE
              AND c.phone IS NOT NULL AND c.phone != ''
              AND (a.appointment_date::timestamp + a.start_time::interval)
                  BETWEEN NOW() + INTERVAL '1 minute' * (%s * 60 - 15)
                      AND NOW() + INTERVAL '1 minute' * (%s * 60 + 15)
              AND a.id NOT IN (
                  SELECT DISTINCT appointment_id
                  FROM sms_reminders
                  WHERE message_type_key = %s
                    AND status IN ('sent', 'delivered', 'pending')
              )
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (hours_before, hours_before, message_type_key))
            return cursor.fetchall()

    def get_past_pending_appointments(self) -> List[Any]:
        """
        Pobierz przeszłe wizyty które nie mają jeszcze finalnego statusu.

        Kryteria:
        - Data i godzina zakończenia wizyty < NOW()
        - Status nie należy do: 'completed', 'cancelled', 'no_show'

        Returns:
            Lista wizyt z danymi klienta, pracownika i usług
        """
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        query = f"""
            SELECT
                a.id,
                a.client_id,
                a.employee_id,
                a.status,
                a.appointment_date,
                a.start_time,
                a.end_time,
                a.total_price,
                a.notes,
                c.first_name || ' ' || c.last_name as client_name,
                e.first_name || ' ' || e.last_name as employee_name,
                STRING_AGG(s.name, ', ') as service_names
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            JOIN employees e ON e.id = a.employee_id
            LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
            LEFT JOIN services s ON s.id = aps.service_id
            WHERE
                (a.appointment_date + a.end_time) < NOW()
                AND a.status NOT IN ('{AppointmentStatus.COMPLETED}', '{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
                AND a.is_deleted = FALSE {excl_sql}
            GROUP BY a.id, a.client_id, a.employee_id, a.status, a.appointment_date,
                     a.start_time, a.end_time, a.total_price, a.notes,
                     c.first_name, c.last_name, e.first_name, e.last_name
            ORDER BY a.appointment_date DESC, a.start_time DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(excl_params))
            return cursor.fetchall()

    def count_past_pending_appointments(self) -> int:
        """Liczba przeszłych wizyt bez finalnego statusu — lekki wariant
        get_past_pending_appointments() (bez joinów/GROUP BY) pod pill-count
        w sidebarze (odpytywane na każdym żądaniu przez context processor)."""
        excl_sql, excl_params = emp_exclusion_sql('a.employee_id')
        query = f"""
            SELECT COUNT(*) AS cnt
            FROM appointments a
            WHERE
                (a.appointment_date + a.end_time) < NOW()
                AND a.status NOT IN ('{AppointmentStatus.COMPLETED}', '{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
                AND a.is_deleted = FALSE {excl_sql}
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(excl_params))
            row = cursor.fetchone()
            return row['cnt'] if row else 0

    # ------------------------------------------------------------------
    # Visit rating methods (P03a)
    # ------------------------------------------------------------------

    def get_by_rating_token(self, token: str) -> Optional[Any]:
        """Public lookup by rating_token (no auth required)."""
        sql = """
            SELECT a.*, c.first_name, c.last_name, c.phone
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            WHERE a.rating_token = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (token,))
            return cursor.fetchone()

    def update_rating(self, appointment_id: int, score: int,
                      rated_on, rated_by: str = 'client') -> bool:
        """Set satisfaction_score + rating metadata atomically."""
        sql = """
            UPDATE appointments
            SET satisfaction_score = %s,
                rated_on           = %s,
                rated_by           = %s,
                rating_status      = 'received'
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (score, rated_on, rated_by, appointment_id))
            safe_commit(conn)
            return cursor.rowcount > 0

    def update_rating_status(self, appointment_id: int, status: str) -> bool:
        """Update the rating workflow status on an appointment."""
        sql = "UPDATE appointments SET rating_status = %s WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (status, appointment_id))
            safe_commit(conn)
            return cursor.rowcount > 0

    def get_today_for_employee(self, employee_id: int, bypass_admin_view_hiding: bool = False) -> List[Any]:
        """Today's appointments for an employee, ordered by start time.

        Widok administratora: by default the owner's own day hides too (the
        spec keeps their revenue-generating activity invisible even from
        their own normal views) — harmless for any other employee, since
        their id is never in the hidden set. The mobile PIN app passes
        bypass_admin_view_hiding=True: unlike a browsed desktop self-view,
        that request is already scoped to exactly one PIN-authenticated
        employee_id, so there is no "other viewer" for the hiding to protect
        against — the owner explicitly asked to see their own day there.
        """
        excl_sql, excl_params = ('', []) if bypass_admin_view_hiding else emp_exclusion_sql('a.employee_id')
        sql = f"""
            SELECT a.id, a.appointment_date, a.start_time, a.end_time,
                   a.status, a.employee_token,
                   c.first_name || ' ' || c.last_name AS client_name,
                   STRING_AGG(s.name, ', ') AS service_name
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
            LEFT JOIN services s ON s.id = aps.service_id
            WHERE a.employee_id = %s
              AND a.appointment_date = CURRENT_DATE
              AND a.is_deleted = FALSE
              AND a.status NOT IN ('{AppointmentStatus.CANCELLED}', '{AppointmentStatus.NO_SHOW}')
              {excl_sql}
            GROUP BY a.id, a.appointment_date, a.start_time, a.end_time,
                     a.status, a.employee_token,
                     c.first_name, c.last_name
            ORDER BY a.start_time ASC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (employee_id, *excl_params))
            return cursor.fetchall()

    def get_by_employee_token(self, token: str) -> Optional[Any]:
        """Public lookup by employee_token. Used by employee mobile form route."""
        try:
            uuid.UUID(token)
        except (ValueError, AttributeError, TypeError):
            # employee_token is a uuid column — a malformed token would otherwise
            # raise psycopg2.errors.InvalidTextRepresentation instead of "not found"
            return None

        sql = """
            SELECT a.*,
                   c.first_name, c.last_name, c.phone,
                   e.first_name || ' ' || e.last_name AS employee_name
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            LEFT JOIN employees e ON e.id = a.employee_id
            WHERE a.employee_token = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (token,))
            return cursor.fetchone()

    def get_candidates_for_conflict_scan(self, date_start: date, date_end: date) -> List[Any]:
        """Wizyty-kandydaci do skanu konfliktów (duplikaty/przełożenia), przeszłe i przyszłe.

        Zwraca jedną wizytę = jeden wiersz, dołączoną do jej głównej usługi
        (is_addon = FALSE). Import z caldis.pl zawsze tworzy dokładnie jedną
        taką usługę na wizytę, więc to złączenie nie mnoży wierszy w praktyce.
        Anulowane i już usunięte wizyty są pomijane — nie są kandydatami na
        "ostateczny" ani "nadpisany" termin.
        """
        query = f"""
            SELECT
                a.id, a.client_id, a.employee_id, a.appointment_date,
                a.start_time, a.end_time, a.status, a.total_price,
                c.first_name || ' ' || c.last_name AS client_name,
                e.first_name || ' ' || e.last_name AS employee_name,
                aps.service_id,
                s.name AS service_name
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            JOIN employees e ON e.id = a.employee_id
            JOIN appointment_services aps ON aps.appointment_id = a.id AND aps.is_addon = FALSE
            JOIN services s ON s.id = aps.service_id
            WHERE a.is_deleted = FALSE
              AND a.status != '{AppointmentStatus.CANCELLED}'
              AND a.appointment_date BETWEEN %s AND %s
            ORDER BY a.client_id, aps.service_id, a.appointment_date, a.start_time
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (date_start.isoformat(), date_end.isoformat()))
            return cursor.fetchall()

    def soft_delete_as_superseded(self, appointment_id: int, note: str) -> bool:
        """Soft-delete wizyty nadpisanej przez późniejsze przełożenie (skan konfliktów).

        Odwracalne przez istniejący restore() — tak jak ręczne usunięcie wizyty.
        Dopisuje `note` do notatek, żeby odróżnić to od ręcznego usunięcia.
        """
        query = """
            UPDATE appointments
            SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP,
                notes = CASE WHEN notes IS NULL OR notes = '' THEN %s
                             ELSE notes || E'\n' || %s END
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (note, note, appointment_id))
            safe_commit(conn)
            return cursor.rowcount > 0
