"""
Repository dla nieobecności pracowników (employee_absences).
"""
from datetime import date, datetime, time
from typing import Any, List, Optional

from config.database import get_db_connection
from database.models import EmployeeAbsence
from repositories.db_utils import parse_date, parse_dt, parse_time


class AbsenceRepository:
    """CRUD i zapytania specjalistyczne dla tabeli employee_absences."""

    _COLUMNS = (
        'ea.id, ea.employee_id, ea.category_id, ea.date_from, ea.date_to, '
        'ea.time_from, ea.time_to, ea.approver_id, ea.status, '
        'ea.rejection_reason, ea.notes, ea.source, '
        'ea.requested_at, ea.responded_at, ea.created_by, '
        'ea.is_deleted, ea.deleted_at, ea.created_at, ea.updated_at'
    )

    # ── row conversion ────────────────────────────────────────────────────────

    def row_to_absence(self, row: Any) -> EmployeeAbsence:
        if not row:
            return None
        return EmployeeAbsence(
            id=row['id'],
            employee_id=row['employee_id'],
            category_id=row['category_id'],
            date_from=parse_date(row['date_from']),
            date_to=parse_date(row['date_to']),
            time_from=parse_time(row['time_from']),
            time_to=parse_time(row['time_to']),
            approver_id=row['approver_id'],
            status=row['status'],
            rejection_reason=row['rejection_reason'],
            notes=row['notes'],
            source=row['source'],
            requested_at=parse_dt(row['requested_at']),
            responded_at=parse_dt(row['responded_at']),
            created_by=row['created_by'],
            is_deleted=bool(row['is_deleted']),
            deleted_at=parse_dt(row['deleted_at']),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at']),
        )

    # ── reads ─────────────────────────────────────────────────────────────────

    def get_by_id(self, absence_id: int) -> Optional[Any]:
        """Pobierz nieobecność po ID (łącznie z soft-deleted — decyduje caller)."""
        query = f"""
            SELECT {self._COLUMNS},
                   ac.name AS category_name,
                   ac.absence_full_day,
                   e.first_name || ' ' || e.last_name AS employee_name,
                   sup.first_name || ' ' || sup.last_name AS approver_name
            FROM employee_absences ea
            JOIN absence_categories ac ON ac.id = ea.category_id
            JOIN employees e ON e.id = ea.employee_id
            LEFT JOIN employees sup ON sup.id = ea.approver_id
            WHERE ea.id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (absence_id,))
            return cursor.fetchone()

    def list_for_employee(self, employee_id: int,
                           status_in: Optional[List[str]] = None) -> List[Any]:
        """Nieobecności danego pracownika (widok 'Moje nieobecności')."""
        params: list = [employee_id]
        status_clause = ''
        if status_in:
            placeholders = ','.join(['%s'] * len(status_in))
            status_clause = f'AND ea.status IN ({placeholders})'
            params.extend(status_in)

        query = f"""
            SELECT {self._COLUMNS},
                   ac.name AS category_name,
                   ac.absence_full_day,
                   sup.first_name || ' ' || sup.last_name AS approver_name
            FROM employee_absences ea
            JOIN absence_categories ac ON ac.id = ea.category_id
            LEFT JOIN employees sup ON sup.id = ea.approver_id
            WHERE ea.employee_id = %s
              AND ea.is_deleted = FALSE
              {status_clause}
            ORDER BY ea.date_from DESC, ea.requested_at DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def list_for_approver(self, approver_employee_id: int,
                           status_in: Optional[List[str]] = None) -> List[Any]:
        """Wnioski skierowane do danego przełożonego (tab #1 zarządzania)."""
        params: list = [approver_employee_id]
        status_clause = ''
        if status_in:
            placeholders = ','.join(['%s'] * len(status_in))
            status_clause = f'AND ea.status IN ({placeholders})'
            params.extend(status_in)

        query = f"""
            SELECT {self._COLUMNS},
                   ac.name AS category_name,
                   ac.absence_full_day,
                   e.first_name || ' ' || e.last_name AS employee_name
            FROM employee_absences ea
            JOIN absence_categories ac ON ac.id = ea.category_id
            JOIN employees e ON e.id = ea.employee_id
            WHERE ea.approver_id = %s
              AND ea.is_deleted = FALSE
              {status_clause}
            ORDER BY ea.requested_at DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def list_all(self, status_in: Optional[List[str]] = None,
                 employee_id: Optional[int] = None,
                 date_from: Optional[date] = None,
                 date_to: Optional[date] = None,
                 include_deleted: bool = False) -> List[Any]:
        """Wszystkie nieobecności z opcjonalnymi filtrami (admin / widok kalendarza)."""
        params: list = []
        clauses: list = []

        if not include_deleted:
            clauses.append('ea.is_deleted = FALSE')
        if status_in:
            placeholders = ','.join(['%s'] * len(status_in))
            clauses.append(f'ea.status IN ({placeholders})')
            params.extend(status_in)
        if employee_id is not None:
            clauses.append('ea.employee_id = %s')
            params.append(employee_id)
        if date_from is not None:
            clauses.append('ea.date_to >= %s')
            params.append(date_from.isoformat())
        if date_to is not None:
            clauses.append('ea.date_from <= %s')
            params.append(date_to.isoformat())

        where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
        query = f"""
            SELECT {self._COLUMNS},
                   ac.name AS category_name,
                   ac.absence_full_day,
                   e.first_name || ' ' || e.last_name AS employee_name,
                   sup.first_name || ' ' || sup.last_name AS approver_name
            FROM employee_absences ea
            JOIN absence_categories ac ON ac.id = ea.category_id
            JOIN employees e ON e.id = ea.employee_id
            LEFT JOIN employees sup ON sup.id = ea.approver_id
            {where}
            ORDER BY ea.date_from DESC, ea.requested_at DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    # ── conflict detection ────────────────────────────────────────────────────

    def check_absence_conflicts(self, employee_id: int,
                                 date_from: date, date_to: date,
                                 time_from: Optional[time] = None,
                                 time_to: Optional[time] = None,
                                 exclude_id: Optional[int] = None) -> List[Any]:
        """Sprawdź czy proponowana nieobecność koliduje z istniejącymi.

        Logika nakładania się:
        - Data: istniejąca.date_from <= proponowana.date_to
                AND istniejąca.date_to >= proponowana.date_from
        - Czas (tylko gdy obie strony to sloty czasowe):
                istniejąca.time_from < proponowana.time_to
                AND istniejąca.time_to > proponowana.time_from
        - Jeśli którakolwiek strona jest całodniowa → konflikt na podstawie dat
        """
        params: list = [
            employee_id,
            date_to.isoformat(),    # istniejąca.date_from <= proponowana.date_to
            date_from.isoformat(),  # istniejąca.date_to   >= proponowana.date_from
        ]

        if time_from is None:
            # Proponowana jest całodniowa — konflikt z czymkolwiek co nakłada daty
            time_clause = ''
        else:
            # Proponowana jest time-slot — nakłada się tylko z full-day LUB nakładającymi się slotami
            time_clause = """
                AND (
                    ea.time_from IS NULL
                    OR (ea.time_from < %s AND ea.time_to > %s)
                )
            """
            params.extend([
                time_to.strftime('%H:%M:%S'),    # istniejąca.time_from < proponowana.time_to
                time_from.strftime('%H:%M:%S'),  # istniejąca.time_to   > proponowana.time_from
            ])

        exclude_clause = ''
        if exclude_id is not None:
            exclude_clause = 'AND ea.id != %s'
            params.append(exclude_id)

        query = f"""
            SELECT ea.id, ea.date_from, ea.date_to, ea.time_from, ea.time_to,
                   ea.status, ac.name AS category_name
            FROM employee_absences ea
            JOIN absence_categories ac ON ac.id = ea.category_id
            WHERE ea.employee_id = %s
              AND ea.is_deleted = FALSE
              AND ea.status IN ('pending', 'approved')
              AND ea.date_from <= %s
              AND ea.date_to   >= %s
              {time_clause}
              {exclude_clause}
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_overlapping_appointments(self, employee_id: int,
                                      date_from: date, date_to: date,
                                      time_from: Optional[time] = None,
                                      time_to: Optional[time] = None) -> List[Any]:
        """Wizyty klientów kolidujące z proponowanym zakresem nieobecności.

        Używane przy zatwierdzaniu wniosku — zwraca dane do wyświetlenia w modalu.
        """
        params: list = [
            employee_id,
            date_to.isoformat(),
            date_from.isoformat(),
        ]

        if time_from is None:
            # Nieobecność całodniowa — koliduje z każdą wizytą w tym zakresie dat
            time_clause = ''
        else:
            time_clause = """
                AND a.start_time < %s
                AND a.end_time   > %s
            """
            params.extend([
                time_to.strftime('%H:%M:%S'),
                time_from.strftime('%H:%M:%S'),
            ])

        query = f"""
            SELECT a.id, a.appointment_date, a.start_time, a.end_time,
                   a.status AS appointment_status,
                   c.first_name || ' ' || c.last_name AS client_name,
                   s.name AS service_name
            FROM appointments a
            JOIN clients c ON c.id = a.client_id
            LEFT JOIN appointment_services aps ON aps.appointment_id = a.id AND aps.is_addon = FALSE
            LEFT JOIN services s ON s.id = aps.service_id
            WHERE a.employee_id = %s
              AND a.is_deleted = FALSE
              AND a.status NOT IN ('cancelled', 'no_show')
              AND a.appointment_date <= %s
              AND a.appointment_date >= %s
              {time_clause}
            ORDER BY a.appointment_date, a.start_time
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    # ── writes ────────────────────────────────────────────────────────────────

    def create(self, absence: EmployeeAbsence) -> int:
        query = """
            INSERT INTO employee_absences (
                employee_id, category_id, date_from, date_to,
                time_from, time_to, approver_id, status,
                rejection_reason, notes, source,
                requested_at, responded_at, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                absence.employee_id,
                absence.category_id,
                absence.date_from.isoformat() if absence.date_from else None,
                absence.date_to.isoformat() if absence.date_to else None,
                absence.time_from.strftime('%H:%M:%S') if absence.time_from else None,
                absence.time_to.strftime('%H:%M:%S') if absence.time_to else None,
                absence.approver_id,
                absence.status,
                absence.rejection_reason,
                absence.notes,
                absence.source,
                absence.requested_at,
                absence.responded_at,
                absence.created_by,
            ))
            new_id = cursor.fetchone()['id']
            conn.commit()
            return new_id

    def update(self, absence_id: int, absence: EmployeeAbsence) -> bool:
        """Aktualizacja danych nieobecności — tylko rekordy source='manual'."""
        query = """
            UPDATE employee_absences
            SET category_id = %s,
                date_from = %s,
                date_to = %s,
                time_from = %s,
                time_to = %s,
                notes = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                absence.category_id,
                absence.date_from.isoformat() if absence.date_from else None,
                absence.date_to.isoformat() if absence.date_to else None,
                absence.time_from.strftime('%H:%M:%S') if absence.time_from else None,
                absence.time_to.strftime('%H:%M:%S') if absence.time_to else None,
                absence.notes,
                absence_id,
            ))
            conn.commit()
            return cursor.rowcount > 0

    def respond(self, absence_id: int, status: str,
                approver_id: int, rejection_reason: Optional[str] = None) -> bool:
        """Zatwierdź lub odrzuć wniosek — ustawia status, responded_at, approver_id."""
        query = """
            UPDATE employee_absences
            SET status = %s,
                approver_id = %s,
                rejection_reason = %s,
                responded_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, approver_id, rejection_reason, absence_id))
            conn.commit()
            return cursor.rowcount > 0

    def cancel(self, absence_id: int) -> bool:
        """Anuluj własny wniosek (tylko status=pending)."""
        query = """
            UPDATE employee_absences
            SET status = 'cancelled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'pending' AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (absence_id,))
            conn.commit()
            return cursor.rowcount > 0

    def soft_delete(self, absence_id: int) -> bool:
        query = """
            UPDATE employee_absences
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (absence_id,))
            conn.commit()
            return cursor.rowcount > 0
