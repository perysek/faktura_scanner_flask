"""
Client Repository - Data access layer for clients
"""
from datetime import date, datetime, timedelta
from typing import Any, List, Optional, Tuple

from database.models import Client
from repositories.base_repository import BaseRepository
from repositories.db_utils import parse_dt, parse_date


class ClientRepository(BaseRepository):
    """Repository dla operacji na tabeli clients"""

    _soft_delete = True
    _columns = (
        'id, first_name, last_name, phone, email, date_of_birth, '
        'notes, preferences, first_visit_date, last_visit_date, '
        'is_active, is_deleted, deleted_at, created_at, updated_at'
    )

    def __init__(self):
        super().__init__('clients')

    def row_to_client(self, row: Any) -> Client:
        """Konwertuj Row na obiekt Client"""
        if not row:
            return None

        return Client(
            id=row['id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            phone=row['phone'],
            email=row['email'],
            date_of_birth=parse_date(row['date_of_birth']),
            notes=row['notes'],
            preferences=row['preferences'],
            first_visit_date=parse_date(row['first_visit_date']),
            last_visit_date=parse_date(row['last_visit_date']),
            is_active=bool(row['is_active']),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at'])
        )

    def create(self, client: Client) -> int:
        """Utwórz nowego klienta"""
        query = """
            INSERT INTO clients (
                first_name, last_name, phone, email, date_of_birth,
                notes, preferences, first_visit_date, last_visit_date, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            client.first_name,
            client.last_name,
            client.phone,
            client.email,
            client.date_of_birth.isoformat() if client.date_of_birth else None,
            client.notes,
            client.preferences,
            client.first_visit_date.isoformat() if client.first_visit_date else None,
            client.last_visit_date.isoformat() if client.last_visit_date else None,
            client.is_active
        )

        return self._execute_insert(query, params)

    def update(self, client_id: int, client: Client) -> bool:
        """Zaktualizuj dane klienta"""
        query = """
            UPDATE clients SET
                first_name = %s,
                last_name = %s,
                phone = %s,
                email = %s,
                date_of_birth = %s,
                notes = %s,
                preferences = %s,
                first_visit_date = %s,
                last_visit_date = %s,
                is_active = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        params = (
            client.first_name,
            client.last_name,
            client.phone,
            client.email,
            client.date_of_birth.isoformat() if client.date_of_birth else None,
            client.notes,
            client.preferences,
            client.first_visit_date.isoformat() if client.first_visit_date else None,
            client.last_visit_date.isoformat() if client.last_visit_date else None,
            client.is_active,
            client_id
        )

        cursor = self._execute(query, params)
        return cursor.rowcount > 0

    def search(self, search_term: str) -> List[Any]:
        """Wyszukaj klientów po imieniu, nazwisku, telefonie lub emailu"""
        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE
              AND (first_name ILIKE %s OR last_name ILIKE %s OR phone ILIKE %s OR email ILIKE %s)
            ORDER BY
                CASE WHEN last_name = '' OR last_name IS NULL THEN 1 ELSE 0 END,
                LOWER(last_name),
                LOWER(first_name)
        """
        search_pattern = f'%{search_term}%'
        return self._fetch_all(query, (search_pattern, search_pattern, search_pattern, search_pattern))

    def search_by_name(self, name: str) -> List[Any]:
        """Wyszukaj klientów po imieniu lub nazwisku"""
        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE
              AND (first_name ILIKE %s OR last_name ILIKE %s)
            ORDER BY last_name, first_name
        """
        search_pattern = f'%{name}%'
        return self._fetch_all(query, (search_pattern, search_pattern))

    def search_by_phone(self, phone: str) -> List[Any]:
        """Wyszukaj klientów po numerze telefonu"""
        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE AND phone ILIKE %s
            ORDER BY last_name, first_name
        """
        search_pattern = f'%{phone}%'
        return self._fetch_all(query, (search_pattern,))

    def find_by_email(self, email: str) -> Optional[Any]:
        """Znajdź klienta po dokładnym adresie email"""
        query = f"SELECT {self._columns} FROM clients WHERE email = %s AND is_deleted = FALSE"
        return self._fetch_one(query, (email,))

    def get_active_clients(self) -> List[Any]:
        """Pobierz tylko aktywnych klientów"""
        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE AND is_active = TRUE
            ORDER BY
                CASE WHEN last_name = '' OR last_name IS NULL THEN 1 ELSE 0 END,
                LOWER(last_name),
                LOWER(first_name)
        """
        return self._fetch_all(query)

    def get_clients_with_stats(self, search_query: str = '',
                               include_inactive: bool = False) -> List[Any]:
        """Pobierz klientów ze statystykami wizyt (zakończone, no-show, anulowane).

        Domyślnie tylko aktywni. ``include_inactive=True`` zwraca również
        zdezaktywowanych klientów (``is_active = FALSE``) — używane przez przełącznik
        „Wszyscy / Aktywni" na liście klientów, żeby dało się ich w ogóle zobaczyć
        i (przez ikonę edycji) ponownie aktywować. Soft-deleted (``is_deleted``)
        nadal są wykluczeni w obu trybach.
        """
        params = []
        search_clause = ''
        if search_query:
            search_clause = """
                AND (c.first_name ILIKE %s OR c.last_name ILIKE %s
                     OR c.phone ILIKE %s OR c.email ILIKE %s)
            """
            p = f'%{search_query}%'
            params = [p, p, p, p]

        active_clause = '' if include_inactive else 'AND c.is_active = TRUE'

        query = f"""
            SELECT
                c.id, c.first_name, c.last_name, c.phone, c.email,
                c.date_of_birth, c.notes, c.preferences,
                c.first_visit_date,
                GREATEST(
                    c.last_visit_date,
                    MAX(CASE WHEN a.status = 'completed' THEN a.appointment_date END)
                ) AS last_visit_date,
                c.is_active, c.created_at, c.updated_at,
                COALESCE(COUNT(CASE WHEN a.status = 'completed' THEN 1 END), 0) AS completed_visits,
                COALESCE(COUNT(CASE WHEN a.status = 'no_show' THEN 1 END), 0)  AS no_show_count,
                COALESCE(COUNT(CASE WHEN a.status = 'cancelled' THEN 1 END), 0) AS cancelled_count,
                COALESCE(COUNT(CASE WHEN a.status = 'completed'
                    AND a.appointment_date >= CURRENT_DATE - INTERVAL '56 days' THEN 1 END), 0) AS visits_last_8w,
                nv.next_visit_date,
                nv.next_visit_time,
                nv.next_visit_employee
            FROM clients c
            LEFT JOIN appointments a ON a.client_id = c.id
            -- Soonest upcoming (not-yet-past, non-cancelled/no-show/completed) appointment
            -- with its assigned employee. LATERAL returns at most one row per client.
            LEFT JOIN LATERAL (
                SELECT na.appointment_date AS next_visit_date,
                       na.start_time       AS next_visit_time,
                       (ne.first_name || ' ' || ne.last_name) AS next_visit_employee
                FROM appointments na
                JOIN employees ne ON ne.id = na.employee_id
                WHERE na.client_id = c.id
                  AND na.is_deleted = FALSE
                  AND na.status NOT IN ('cancelled', 'no_show', 'completed')
                  AND (na.appointment_date > CURRENT_DATE
                       OR (na.appointment_date = CURRENT_DATE AND na.start_time >= LOCALTIME))
                ORDER BY na.appointment_date ASC, na.start_time ASC
                LIMIT 1
            ) nv ON TRUE
            WHERE c.is_deleted = FALSE {active_clause}
            {search_clause}
            GROUP BY
                c.id, c.first_name, c.last_name, c.phone, c.email,
                c.date_of_birth, c.notes, c.preferences,
                c.first_visit_date, c.last_visit_date,
                c.is_active, c.created_at, c.updated_at,
                nv.next_visit_date, nv.next_visit_time, nv.next_visit_employee
            ORDER BY
                CASE WHEN c.last_name = '' OR c.last_name IS NULL THEN 1 ELSE 0 END,
                LOWER(c.last_name),
                LOWER(c.first_name)
        """
        return self._fetch_all(query, tuple(params) if params else ())

    def get_recent_clients(self, limit: int = 10) -> List[Any]:
        """Pobierz ostatnio dodanych klientów"""
        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetch_all(query, (limit,))

    def get_upcoming_birthdays(self, days_ahead: int = 30) -> List[Any]:
        """
        Pobierz klientów z nadchodzącymi urodzinami w ciągu określonej liczby dni
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        # SQLite nie ma wbudowanej funkcji do porównywania samych miesięcy/dni,
        # więc musimy pobrać wszystkich klientów z datami urodzenia i filtrować w Pythonie
        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE AND date_of_birth IS NOT NULL AND is_active = TRUE
            ORDER BY date_of_birth
        """
        all_clients = self._fetch_all(query)

        upcoming_birthdays = []
        for row in all_clients:
            if row['date_of_birth']:
                birth_date = parse_date(row['date_of_birth'])
                # Create birthday in current year
                this_year_birthday = birth_date.replace(year=today.year)

                # If birthday already passed this year, check next year
                if this_year_birthday < today:
                    this_year_birthday = birth_date.replace(year=today.year + 1)

                # Check if birthday is within the range
                if today <= this_year_birthday <= end_date:
                    upcoming_birthdays.append(row)

        return upcoming_birthdays

    def get_clients_without_recent_visits(self, days: int = 90) -> List[Any]:
        """Pobierz klientów, którzy nie mieli wizyty od określonej liczby dni"""
        cutoff_date = date.today() - timedelta(days=days)

        query = f"""
            SELECT {self._columns} FROM clients
            WHERE is_deleted = FALSE AND is_active = TRUE
            AND (last_visit_date IS NULL OR last_visit_date < %s)
            ORDER BY last_visit_date DESC NULLS LAST
        """
        return self._fetch_all(query, (cutoff_date.isoformat(),))

    def get_all_monthly_visit_trends(self, months: int = 12) -> dict:
        """Returns {client_id: [count_month0, ..., count_monthN]} oldest to newest."""
        query = """
            WITH month_series AS (
                SELECT
                    gs AS month_idx,
                    (date_trunc('month', CURRENT_DATE::date)
                        - ((%s - 1 - gs) * INTERVAL '1 month'))::date AS month_start
                FROM generate_series(0, %s - 1) AS gs
            ),
            completed AS (
                SELECT
                    a.client_id,
                    date_trunc('month', a.appointment_date)::date AS month_start,
                    COUNT(*) AS cnt
                FROM appointments a
                JOIN clients c ON c.id = a.client_id
                WHERE a.status = 'completed'
                  AND c.is_deleted = FALSE
                  AND c.is_active = TRUE
                  AND a.appointment_date >= (
                      date_trunc('month', CURRENT_DATE::date) - (%s - 1) * INTERVAL '1 month'
                  )
                GROUP BY a.client_id, date_trunc('month', a.appointment_date)::date
            )
            SELECT
                c.id AS client_id,
                ms.month_idx,
                COALESCE(comp.cnt, 0) AS visit_count
            FROM clients c
            CROSS JOIN month_series ms
            LEFT JOIN completed comp ON comp.client_id = c.id AND comp.month_start = ms.month_start
            WHERE c.is_deleted = FALSE AND c.is_active = TRUE
            ORDER BY c.id, ms.month_idx
        """
        rows = self._fetch_all(query, (months, months, months))
        result = {}
        for row in rows:
            cid = int(row['client_id'])
            if cid not in result:
                result[cid] = []
            result[cid].append(int(row['visit_count'] or 0))
        return result

    def update_last_visit(self, client_id: int, visit_date: date) -> bool:
        """Zaktualizuj datę ostatniej wizyty klienta"""
        query = """
            UPDATE clients SET
                last_visit_date = %s,
                first_visit_date = CASE
                    WHEN first_visit_date IS NULL THEN %s
                    ELSE first_visit_date
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (visit_date.isoformat(), visit_date.isoformat(), client_id))
        return cursor.rowcount > 0

    def deactivate(self, client_id: int) -> bool:
        """Dezaktywuj klienta (soft delete)"""
        query = """
            UPDATE clients SET
                is_active = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (client_id,))
        return cursor.rowcount > 0

    def activate(self, client_id: int) -> bool:
        """Aktywuj klienta"""
        query = """
            UPDATE clients SET
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (client_id,))
        return cursor.rowcount > 0

    def get_statistics(self) -> dict:
        """Pobierz statystyki klientów"""
        stats_query = """
            SELECT
                COUNT(*) as total_clients,
                SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active_clients,
                SUM(CASE WHEN is_active = FALSE THEN 1 ELSE 0 END) as inactive_clients,
                SUM(CASE WHEN last_visit_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1 ELSE 0 END) as recent_visitors,
                SUM(CASE WHEN date_of_birth IS NOT NULL THEN 1 ELSE 0 END) as clients_with_birthdate
            FROM clients
            WHERE is_deleted = FALSE
        """
        row = self._fetch_one(stats_query)

        return {
            'total_clients': row['total_clients'] or 0,
            'active_clients': row['active_clients'] or 0,
            'inactive_clients': row['inactive_clients'] or 0,
            'recent_visitors': row['recent_visitors'] or 0,
            'clients_with_birthdate': row['clients_with_birthdate'] or 0
        }
