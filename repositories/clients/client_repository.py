"""
Client Repository - Data access layer for clients
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from database.models import Client
from repositories.base_repository import BaseRepository


class ClientRepository(BaseRepository):
    """Repository dla operacji na tabeli clients"""

    def __init__(self):
        super().__init__('clients')

    def row_to_client(self, row: sqlite3.Row) -> Client:
        """Konwertuj Row na obiekt Client"""
        if not row:
            return None

        return Client(
            id=row['id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            phone=row['phone'],
            email=row['email'],
            date_of_birth=datetime.strptime(row['date_of_birth'], '%Y-%m-%d').date() if row['date_of_birth'] else None,
            notes=row['notes'],
            preferences=row['preferences'],
            first_visit_date=datetime.strptime(row['first_visit_date'], '%Y-%m-%d').date() if row['first_visit_date'] else None,
            last_visit_date=datetime.strptime(row['last_visit_date'], '%Y-%m-%d').date() if row['last_visit_date'] else None,
            is_active=bool(row['is_active']),
            created_at=datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S') if row['created_at'] else None,
            updated_at=datetime.strptime(row['updated_at'], '%Y-%m-%d %H:%M:%S') if row['updated_at'] else None
        )

    def create(self, client: Client) -> int:
        """Utwórz nowego klienta"""
        query = """
            INSERT INTO clients (
                first_name, last_name, phone, email, date_of_birth,
                notes, preferences, first_visit_date, last_visit_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        cursor = self._execute(query, params)
        return cursor.lastrowid

    def update(self, client_id: int, client: Client) -> bool:
        """Zaktualizuj dane klienta"""
        query = """
            UPDATE clients SET
                first_name = ?,
                last_name = ?,
                phone = ?,
                email = ?,
                date_of_birth = ?,
                notes = ?,
                preferences = ?,
                first_visit_date = ?,
                last_visit_date = ?,
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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

    def search(self, search_term: str) -> List[sqlite3.Row]:
        """Wyszukaj klientów po imieniu, nazwisku, telefonie lub emailu"""
        query = """
            SELECT * FROM clients
            WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? OR email LIKE ?
            ORDER BY
                CASE WHEN last_name = '' OR last_name IS NULL THEN 1 ELSE 0 END,
                last_name COLLATE NOCASE,
                first_name COLLATE NOCASE
        """
        search_pattern = f'%{search_term}%'
        return self._fetch_all(query, (search_pattern, search_pattern, search_pattern, search_pattern))

    def search_by_name(self, name: str) -> List[sqlite3.Row]:
        """Wyszukaj klientów po imieniu lub nazwisku"""
        query = """
            SELECT * FROM clients
            WHERE first_name LIKE ? OR last_name LIKE ?
            ORDER BY last_name, first_name
        """
        search_pattern = f'%{name}%'
        return self._fetch_all(query, (search_pattern, search_pattern))

    def search_by_phone(self, phone: str) -> List[sqlite3.Row]:
        """Wyszukaj klientów po numerze telefonu"""
        query = """
            SELECT * FROM clients
            WHERE phone LIKE ?
            ORDER BY last_name, first_name
        """
        search_pattern = f'%{phone}%'
        return self._fetch_all(query, (search_pattern,))

    def find_by_email(self, email: str) -> Optional[sqlite3.Row]:
        """Znajdź klienta po dokładnym adresie email"""
        query = "SELECT * FROM clients WHERE email = ?"
        return self._fetch_one(query, (email,))

    def get_active_clients(self) -> List[sqlite3.Row]:
        """Pobierz tylko aktywnych klientów"""
        query = """
            SELECT * FROM clients
            WHERE is_active = 1
            ORDER BY
                CASE WHEN last_name = '' OR last_name IS NULL THEN 1 ELSE 0 END,
                last_name COLLATE NOCASE,
                first_name COLLATE NOCASE
        """
        return self._fetch_all(query)

    def get_recent_clients(self, limit: int = 10) -> List[sqlite3.Row]:
        """Pobierz ostatnio dodanych klientów"""
        query = """
            SELECT * FROM clients
            ORDER BY created_at DESC
            LIMIT ?
        """
        return self._fetch_all(query, (limit,))

    def get_upcoming_birthdays(self, days_ahead: int = 30) -> List[sqlite3.Row]:
        """
        Pobierz klientów z nadchodzącymi urodzinami w ciągu określonej liczby dni
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        # SQLite nie ma wbudowanej funkcji do porównywania samych miesięcy/dni,
        # więc musimy pobrać wszystkich klientów z datami urodzenia i filtrować w Pythonie
        query = """
            SELECT * FROM clients
            WHERE date_of_birth IS NOT NULL AND is_active = 1
            ORDER BY date_of_birth
        """
        all_clients = self._fetch_all(query)

        upcoming_birthdays = []
        for row in all_clients:
            if row['date_of_birth']:
                birth_date = datetime.strptime(row['date_of_birth'], '%Y-%m-%d').date()
                # Create birthday in current year
                this_year_birthday = birth_date.replace(year=today.year)

                # If birthday already passed this year, check next year
                if this_year_birthday < today:
                    this_year_birthday = birth_date.replace(year=today.year + 1)

                # Check if birthday is within the range
                if today <= this_year_birthday <= end_date:
                    upcoming_birthdays.append(row)

        return upcoming_birthdays

    def get_clients_without_recent_visits(self, days: int = 90) -> List[sqlite3.Row]:
        """Pobierz klientów, którzy nie mieli wizyty od określonej liczby dni"""
        cutoff_date = date.today() - timedelta(days=days)

        query = """
            SELECT * FROM clients
            WHERE is_active = 1
            AND (last_visit_date IS NULL OR last_visit_date < ?)
            ORDER BY last_visit_date DESC NULLS LAST
        """
        return self._fetch_all(query, (cutoff_date.isoformat(),))

    def update_last_visit(self, client_id: int, visit_date: date) -> bool:
        """Zaktualizuj datę ostatniej wizyty klienta"""
        query = """
            UPDATE clients SET
                last_visit_date = ?,
                first_visit_date = CASE
                    WHEN first_visit_date IS NULL THEN ?
                    ELSE first_visit_date
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        cursor = self._execute(query, (visit_date.isoformat(), visit_date.isoformat(), client_id))
        return cursor.rowcount > 0

    def deactivate(self, client_id: int) -> bool:
        """Dezaktywuj klienta (soft delete)"""
        query = """
            UPDATE clients SET
                is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        cursor = self._execute(query, (client_id,))
        return cursor.rowcount > 0

    def activate(self, client_id: int) -> bool:
        """Aktywuj klienta"""
        query = """
            UPDATE clients SET
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        cursor = self._execute(query, (client_id,))
        return cursor.rowcount > 0

    def get_statistics(self) -> dict:
        """Pobierz statystyki klientów"""
        stats_query = """
            SELECT
                COUNT(*) as total_clients,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_clients,
                SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive_clients,
                SUM(CASE WHEN last_visit_date >= date('now', '-30 days') THEN 1 ELSE 0 END) as recent_visitors,
                SUM(CASE WHEN date_of_birth IS NOT NULL THEN 1 ELSE 0 END) as clients_with_birthdate
            FROM clients
        """
        row = self._fetch_one(stats_query)

        return {
            'total_clients': row['total_clients'] or 0,
            'active_clients': row['active_clients'] or 0,
            'inactive_clients': row['inactive_clients'] or 0,
            'recent_visitors': row['recent_visitors'] or 0,
            'clients_with_birthdate': row['clients_with_birthdate'] or 0
        }
