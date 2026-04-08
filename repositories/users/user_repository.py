"""
Repository dla użytkowników (user accounts)
"""
from datetime import datetime
from typing import Any, Optional
import bcrypt

from config.database import get_db_connection
from database.models import User
from repositories.base_repository import BaseRepository
from repositories.db_utils import parse_dt


class UserRepository(BaseRepository):
    """Repository dla operacji na użytkownikach"""

    _columns = 'id, email, password_hash, full_name, role, is_active, last_login, created_at, updated_at'

    def __init__(self):
        super().__init__("users")

    def _validate_role(self, role: str) -> None:
        """Sprawdź czy rola istnieje w tabeli roles. Rzuca ValueError jeśli nie."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM roles WHERE name = %s", (role,))
            if not cursor.fetchone():
                raise ValueError(f"Rola '{role}' nie istnieje w systemie")

    def create_user(self, email: str, password: str, full_name: str, role: str = 'receptionist') -> int:
        """
        Utwórz nowego użytkownika z zahashowanym hasłem

        Args:
            email: Adres email (unikalny)
            password: Hasło w postaci jawnej (zostanie zahashowane)
            full_name: Imię i nazwisko
            role: Rola użytkownika (domyślnie 'receptionist')

        Returns:
            ID nowego użytkownika
        """
        self._validate_role(role)
        # Hash password using bcrypt
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        query = """
            INSERT INTO users (email, password_hash, full_name, role, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
        """
        return self._execute_insert(query, (email, password_hash, full_name, role))

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Pobierz użytkownika po adresie email

        Args:
            email: Adres email

        Returns:
            User object lub None jeśli nie znaleziono
        """
        query = f"SELECT {self._columns} FROM users WHERE email = %s"
        row = self._fetch_one(query, (email,))

        if not row:
            return None

        return self.row_to_user(row)

    def verify_password(self, user: User, password: str) -> bool:
        """
        Weryfikuj hasło użytkownika

        Args:
            user: Obiekt User
            password: Hasło do sprawdzenia (w postaci jawnej)

        Returns:
            True jeśli hasło poprawne, False w przeciwnym razie
        """
        return bcrypt.checkpw(
            password.encode('utf-8'),
            user.password_hash.encode('utf-8')
        )

    def update_last_login(self, user_id: int):
        """
        Zaktualizuj timestamp ostatniego logowania

        Args:
            user_id: ID użytkownika
        """
        query = "UPDATE users SET last_login = %s, updated_at = %s WHERE id = %s"
        self._execute(query, (datetime.now(), datetime.now(), user_id))

    def update_password(self, user_id: int, new_password: str):
        """
        Zaktualizuj hasło użytkownika

        Args:
            user_id: ID użytkownika
            new_password: Nowe hasło (w postaci jawnej, zostanie zahashowane)
        """
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        query = "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s"
        self._execute(query, (password_hash, datetime.now(), user_id))

    def update_role(self, user_id: int, new_role: str):
        """
        Zaktualizuj rolę użytkownika

        Args:
            user_id: ID użytkownika
            new_role: Nowa rola
        """
        query = "UPDATE users SET role = %s, updated_at = %s WHERE id = %s"
        self._execute(query, (new_role, datetime.now(), user_id))

    def deactivate(self, user_id: int):
        """
        Dezaktywuj konto użytkownika (soft delete)

        Args:
            user_id: ID użytkownika
        """
        query = "UPDATE users SET is_active = FALSE, updated_at = %s WHERE id = %s"
        self._execute(query, (datetime.now(), user_id))

    def activate(self, user_id: int):
        """
        Aktywuj konto użytkownika

        Args:
            user_id: ID użytkownika
        """
        query = "UPDATE users SET is_active = TRUE, updated_at = %s WHERE id = %s"
        self._execute(query, (datetime.now(), user_id))

    def get_by_role(self, role: str) -> list:
        """
        Pobierz wszystkich użytkowników o danej roli

        Args:
            role: Nazwa roli

        Returns:
            Lista obiektów User
        """
        query = f"SELECT {self._columns} FROM users WHERE role = %s AND is_active = TRUE ORDER BY full_name"
        rows = self._fetch_all(query, (role,))
        return [self.row_to_user(row) for row in rows]

    def get_active_users(self) -> list:
        """
        Pobierz wszystkich aktywnych użytkowników

        Returns:
            Lista obiektów User
        """
        query = f"SELECT {self._columns} FROM users WHERE is_active = TRUE ORDER BY full_name"
        rows = self._fetch_all(query)
        return [self.row_to_user(row) for row in rows]

    def get_all_with_employee(self) -> list:
        """
        Pobierz wszystkich użytkowników wraz z powiązanym pracownikiem (jeśli istnieje).
        Zwraca surowe Row objects z polami: id, email, full_name, role, is_active,
        last_login, created_at, employee_id, employee_first_name, employee_last_name
        """
        query = """
            SELECT u.id, u.email, u.full_name, u.role, u.is_active,
                   u.last_login, u.created_at,
                   e.id AS employee_id,
                   e.first_name AS employee_first_name,
                   e.last_name AS employee_last_name
            FROM users u
            LEFT JOIN employees e ON e.user_id = u.id
            ORDER BY u.full_name
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    def update_user(self, user_id: int, email: str, full_name: str, role: str, is_active: bool):
        """
        Zaktualizuj dane użytkownika (email, imię, rola, aktywność).
        Nie aktualizuje hasła — użyj update_password() osobno.
        """
        self._validate_role(role)
        query = """
            UPDATE users
            SET email = %s, full_name = %s, role = %s, is_active = %s, updated_at = %s
            WHERE id = %s
        """
        self._execute(query, (email, full_name, role, is_active, datetime.now(), user_id))

    def unlink_employee(self, user_id: int):
        """Odepnij pracownika od konta użytkownika (ustaw user_id = NULL w employees)"""
        query = "UPDATE employees SET user_id = NULL WHERE user_id = %s"
        self._execute(query, (user_id,))

    def link_employee(self, user_id: int, employee_id: int):
        """
        Przypisz pracownika do konta użytkownika.
        Wszystkie trzy operacje wykonywane atomowo w jednej transakcji.
        """
        with self.transaction() as conn:
            cursor = conn.cursor()
            # Clear previous user link for this employee
            cursor.execute("UPDATE employees SET user_id = NULL WHERE id = %s", (employee_id,))
            # Clear previous employee link for this user
            cursor.execute(
                "UPDATE employees SET user_id = NULL WHERE user_id = %s AND id != %s",
                (user_id, employee_id)
            )
            # Link
            cursor.execute("UPDATE employees SET user_id = %s WHERE id = %s", (user_id, employee_id))

    def get_available_employees(self) -> list:
        """
        Pobierz pracowników bez przypisanego konta użytkownika.
        Używane w formularzu tworzenia/edycji użytkownika.
        """
        query = """
            SELECT id, first_name, last_name
            FROM employees
            WHERE user_id IS NULL AND is_active = TRUE
            ORDER BY last_name, first_name
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    def get_linked_employee(self, user_id: int):
        """Pobierz pracownika powiązanego z użytkownikiem (lub None)"""
        query = "SELECT id, first_name, last_name FROM employees WHERE user_id = %s"
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(query, (user_id,))
        return cursor.fetchone()

    def row_to_user(self, row: Any) -> User:
        """
        Konwertuj Row → User object

        Args:
            row: SQLite Row object

        Returns:
            User object
        """
        return User(
            id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            full_name=row["full_name"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            last_login=parse_dt(row["last_login"]),
            created_at=parse_dt(row["created_at"]),
            updated_at=parse_dt(row["updated_at"])
        )
