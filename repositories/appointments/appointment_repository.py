"""
Repository dla operacji na wizytach (appointments)
"""
from decimal import Decimal
from typing import Any, List, Optional
from datetime import datetime, date, time
from config.database import get_db_connection
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
            conn.commit()
            return result_id

    def get_by_id(self, appointment_id: int) -> Optional[Any]:
        """Pobierz wizytę po ID"""
        query = "SELECT * FROM appointments WHERE id = %s"
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
            WHERE a.id = %s
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
        filters = ["a.appointment_date BETWEEN %s AND %s"]

        if employee_id:
            filters.append("a.employee_id = %s")
            params.append(employee_id)
        if status:
            filters.append("a.status = %s")
            params.append(status)

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
            WHERE {where_clause}
            GROUP BY a.id, c.first_name, c.last_name, e.first_name, e.last_name
            ORDER BY a.appointment_date, a.start_time
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_daily_schedule(self, employee_id: int, schedule_date: date) -> List[Any]:
        """Pobierz harmonogram dnia pracownika z nazwami usług"""
        query = """
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
            AND a.status NOT IN ('cancelled', 'no_show')
            GROUP BY a.id, c.first_name, c.last_name, c.phone, e.first_name, e.last_name
            ORDER BY a.start_time
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, schedule_date.isoformat()))
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
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Jeśli nie podano employee_ids, znajdź wszystkich pracowników z wizytami tego dnia
            if employee_ids is None:
                query_employees = """
                    SELECT DISTINCT
                        e.id,
                        e.first_name || ' ' || e.last_name as full_name,
                        e.position
                    FROM employees e
                    JOIN appointments a ON a.employee_id = e.id
                    WHERE a.appointment_date = %s
                    AND a.status NOT IN ('cancelled', 'no_show')
                    AND e.is_active = TRUE
                    ORDER BY full_name
                """
                cursor.execute(query_employees, (schedule_date.isoformat(),))
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
                    AND e.is_active = TRUE
                    ORDER BY e.first_name, e.last_name
                """
                cursor.execute(query_employees, employee_ids)

            employees = [dict(row) for row in cursor.fetchall()]

            # Pobierz wizyty dla każdego pracownika (włącznie z anulowanymi dla statystyk)
            schedules = {}
            query_appointments = """
                SELECT
                    a.*,
                    c.first_name || ' ' || c.last_name as client_name,
                    c.phone as client_phone,
                    e.first_name || ' ' || e.last_name as employee_name,
                    STRING_AGG(s.name, ', ') as service_name,
                    STRING_AGG(
                        CASE WHEN aps.is_addon = TRUE THEN s.name ELSE NULL END, ', '
                    ) as addon_services
                FROM appointments a
                JOIN clients c ON c.id = a.client_id
                JOIN employees e ON e.id = a.employee_id
                LEFT JOIN appointment_services aps ON aps.appointment_id = a.id
                LEFT JOIN services s ON s.id = aps.service_id
                WHERE a.employee_id = %s AND a.appointment_date = %s
                GROUP BY a.id, c.first_name, c.last_name, c.phone, e.first_name, e.last_name
                ORDER BY a.start_time
            """

            for emp in employees:
                cursor.execute(query_appointments, (emp['id'], schedule_date.isoformat()))
                schedules[emp['id']] = [dict(row) for row in cursor.fetchall()]

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
            AND a.status NOT IN ('cancelled', 'no_show')
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
            AND a.status NOT IN ('cancelled', 'no_show')
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

    def update_status(self, appointment_id: int, new_status: str,
                       cancellation_reason: Optional[str] = None) -> bool:
        """Zaktualizuj status wizyty"""
        if new_status == 'cancelled':
            query = """
                UPDATE appointments
                SET status = %s, cancellation_reason = %s, cancelled_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
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
            conn.commit()
            return cursor.rowcount > 0

    def update_satisfaction_score(self, appointment_id: int, score: int) -> bool:
        """Ustaw ocenę satysfakcji (1–5) tylko dla zakończonych wizyt. Zwraca True jeśli zaktualizowano."""
        query = """
            UPDATE appointments
            SET satisfaction_score = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'completed'
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (score, appointment_id))
            conn.commit()
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
            conn.commit()
            return cursor.rowcount > 0

    def update(self, appointment_id: int, appt: Appointment) -> bool:
        """Zaktualizuj wizytę"""
        query = """
            UPDATE appointments
            SET client_id = %s, employee_id = %s, appointment_date = %s,
                start_time = %s, end_time = %s, status = %s,
                total_price = %s, total_duration = %s, discount_amount = %s,
                notes = %s, updated_at = CURRENT_TIMESTAMP
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
                appt.notes,
                appointment_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, appointment_id: int) -> bool:
        """Usuń wizytę"""
        query = "DELETE FROM appointments WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (appointment_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_client_appointments(self, client_id: int, limit: int = 20) -> List[Any]:
        """Pobierz wizyty klienta"""
        query = """
            SELECT
                a.*,
                e.first_name || ' ' || e.last_name as employee_name
            FROM appointments a
            JOIN employees e ON e.id = a.employee_id
            WHERE a.client_id = %s
            ORDER BY a.appointment_date DESC, a.start_time DESC
            LIMIT %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id, limit))
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
            WHERE appointment_date = %s AND status NOT IN ('cancelled', 'no_show')
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
                AND a.status NOT IN ('cancelled', 'no_show')
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

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT appointment_date, start_time FROM appointments WHERE id = %s",
                (appointment_id,)
            )
            current = cursor.fetchone()
            if not current:
                return {'prev': None, 'next': None}

            cur_date = current['appointment_date']
            cur_time = current['start_time']

            if mode == 'day':
                cursor.execute("""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE a.appointment_date = %s AND a.start_time < %s AND a.id != %s
                    ORDER BY a.start_time DESC LIMIT 1
                """, (cur_date, cur_time, appointment_id))
                prev_row = cursor.fetchone()

                cursor.execute("""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE a.appointment_date = %s AND a.start_time > %s AND a.id != %s
                    ORDER BY a.start_time ASC LIMIT 1
                """, (cur_date, cur_time, appointment_id))
                next_row = cursor.fetchone()
            else:  # mode='all'
                cursor.execute("""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE (a.appointment_date, a.start_time) < (%s, %s) AND a.id != %s
                    ORDER BY a.appointment_date DESC, a.start_time DESC LIMIT 1
                """, (cur_date, cur_time, appointment_id))
                prev_row = cursor.fetchone()

                cursor.execute("""
                    SELECT a.id, a.appointment_date, a.start_time,
                           c.first_name || ' ' || c.last_name AS client_name
                    FROM appointments a
                    LEFT JOIN clients c ON c.id = a.client_id
                    WHERE (a.appointment_date, a.start_time) > (%s, %s) AND a.id != %s
                    ORDER BY a.appointment_date ASC, a.start_time ASC LIMIT 1
                """, (cur_date, cur_time, appointment_id))
                next_row = cursor.fetchone()

        return {'prev': row_to_dict(prev_row), 'next': row_to_dict(next_row)}

    def get_past_pending_appointments(self) -> List[Any]:
        """
        Pobierz przeszłe wizyty które nie mają jeszcze finalnego statusu.

        Kryteria:
        - Data i godzina zakończenia wizyty < NOW()
        - Status nie należy do: 'completed', 'cancelled', 'no_show'

        Returns:
            Lista wizyt z danymi klienta, pracownika i usług
        """
        query = """
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
                AND a.status NOT IN ('completed', 'cancelled', 'no_show')
            GROUP BY a.id, a.client_id, a.employee_id, a.status, a.appointment_date,
                     a.start_time, a.end_time, a.total_price, a.notes,
                     c.first_name, c.last_name, e.first_name, e.last_name
            ORDER BY a.appointment_date DESC, a.start_time DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
