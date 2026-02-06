"""
Repository dla operacji na pracownikach (employees)
"""
import sqlite3
from typing import List, Optional
from datetime import datetime, date
from config.database import get_db_connection
from database.models import Employee


class EmployeeRepository:
    """Repository do zarządzania pracownikami salonu"""

    def row_to_employee(self, row: sqlite3.Row) -> Employee:
        """Konwertuj Row na obiekt Employee"""
        if not row:
            return None

        return Employee(
            id=row['id'],
            user_id=row['user_id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            phone=row['phone'],
            email=row['email'],
            position=row['position'],
            employment_status=row['employment_status'],
            hire_date=datetime.strptime(row['hire_date'], '%Y-%m-%d').date() if row['hire_date'] else None,
            termination_date=datetime.strptime(row['termination_date'], '%Y-%m-%d').date() if row['termination_date'] else None,
            base_salary=float(row['base_salary']) if row['base_salary'] else None,
            commission_rate=float(row['commission_rate']) if row['commission_rate'] else None,
            skills=row['skills'],
            specializations=row['specializations'],
            work_schedule=row['work_schedule'],
            max_appointments_per_day=row['max_appointments_per_day'],
            notes=row['notes'],
            photo_path=row['photo_path'],
            is_active=bool(row['is_active']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

    def create(self, employee: Employee) -> int:
        """Utwórz nowego pracownika"""
        query = """
            INSERT INTO employees (
                user_id, first_name, last_name, phone, email, position,
                employment_status, hire_date, termination_date,
                base_salary, commission_rate, skills, specializations,
                work_schedule, max_appointments_per_day, notes, photo_path, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                employee.user_id,
                employee.first_name,
                employee.last_name,
                employee.phone,
                employee.email,
                employee.position,
                employee.employment_status,
                employee.hire_date.isoformat() if employee.hire_date else None,
                employee.termination_date.isoformat() if employee.termination_date else None,
                employee.base_salary,
                employee.commission_rate,
                employee.skills,
                employee.specializations,
                employee.work_schedule,
                employee.max_appointments_per_day,
                employee.notes,
                employee.photo_path,
                employee.is_active
            ))
            conn.commit()
            return cursor.lastrowid

    def get_by_id(self, employee_id: int) -> Optional[sqlite3.Row]:
        """Pobierz pracownika po ID"""
        query = "SELECT * FROM employees WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchone()

    def get_by_user_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """Pobierz pracownika po user_id"""
        query = "SELECT * FROM employees WHERE user_id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchone()

    def get_all(self, active_only: bool = True) -> List[sqlite3.Row]:
        """Pobierz wszystkich pracowników"""
        if active_only:
            query = "SELECT * FROM employees WHERE is_active = 1 ORDER BY last_name, first_name"
        else:
            query = "SELECT * FROM employees ORDER BY last_name, first_name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_position(self, position: str, active_only: bool = True) -> List[sqlite3.Row]:
        """Pobierz pracowników według pozycji"""
        if active_only:
            query = "SELECT * FROM employees WHERE position = ? AND is_active = 1 ORDER BY last_name, first_name"
        else:
            query = "SELECT * FROM employees WHERE position = ? ORDER BY last_name, first_name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (position,))
            return cursor.fetchall()

    def get_by_employment_status(self, status: str) -> List[sqlite3.Row]:
        """Pobierz pracowników według statusu zatrudnienia"""
        query = "SELECT * FROM employees WHERE employment_status = ? ORDER BY last_name, first_name"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status,))
            return cursor.fetchall()

    def search(self, query: str, active_only: bool = True) -> List[sqlite3.Row]:
        """Wyszukaj pracowników po imieniu, nazwisku, telefonie lub emailu"""
        search_pattern = f"%{query}%"
        if active_only:
            sql = """
                SELECT * FROM employees
                WHERE (first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? OR email LIKE ?)
                AND is_active = 1
                ORDER BY last_name, first_name
            """
        else:
            sql = """
                SELECT * FROM employees
                WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? OR email LIKE ?
                ORDER BY last_name, first_name
            """

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (search_pattern, search_pattern, search_pattern, search_pattern))
            return cursor.fetchall()

    def update(self, employee_id: int, employee: Employee) -> bool:
        """Zaktualizuj pracownika"""
        query = """
            UPDATE employees
            SET user_id = ?,
                first_name = ?,
                last_name = ?,
                phone = ?,
                email = ?,
                position = ?,
                employment_status = ?,
                hire_date = ?,
                termination_date = ?,
                base_salary = ?,
                commission_rate = ?,
                skills = ?,
                specializations = ?,
                work_schedule = ?,
                max_appointments_per_day = ?,
                notes = ?,
                photo_path = ?,
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                employee.user_id,
                employee.first_name,
                employee.last_name,
                employee.phone,
                employee.email,
                employee.position,
                employee.employment_status,
                employee.hire_date.isoformat() if employee.hire_date else None,
                employee.termination_date.isoformat() if employee.termination_date else None,
                employee.base_salary,
                employee.commission_rate,
                employee.skills,
                employee.specializations,
                employee.work_schedule,
                employee.max_appointments_per_day,
                employee.notes,
                employee.photo_path,
                employee.is_active,
                employee_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, employee_id: int) -> bool:
        """Usuń pracownika (soft delete - ustawia is_active na False)"""
        return self.deactivate(employee_id)

    def deactivate(self, employee_id: int) -> bool:
        """Dezaktywuj pracownika"""
        query = "UPDATE employees SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            conn.commit()
            return cursor.rowcount > 0

    def activate(self, employee_id: int) -> bool:
        """Aktywuj pracownika"""
        query = "UPDATE employees SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_positions(self) -> List[str]:
        """Pobierz listę wszystkich pozycji"""
        query = "SELECT DISTINCT position FROM employees WHERE position IS NOT NULL ORDER BY position"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [row['position'] for row in cursor.fetchall()]

    def get_statistics(self) -> dict:
        """Pobierz statystyki pracowników"""
        query = """
            SELECT
                COUNT(*) as total_employees,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_employees,
                COUNT(CASE WHEN employment_status = 'active' THEN 1 END) as employed,
                COUNT(CASE WHEN employment_status = 'on_leave' THEN 1 END) as on_leave,
                COUNT(CASE WHEN employment_status = 'terminated' THEN 1 END) as terminated,
                COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as linked_to_users,
                AVG(CASE WHEN base_salary IS NOT NULL THEN base_salary END) as avg_salary
            FROM employees
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()

            return {
                'total_employees': row['total_employees'],
                'active_employees': row['active_employees'],
                'inactive_employees': row['total_employees'] - row['active_employees'],
                'employed': row['employed'],
                'on_leave': row['on_leave'],
                'terminated': row['terminated'],
                'linked_to_users': row['linked_to_users'],
                'avg_salary': float(row['avg_salary']) if row['avg_salary'] else 0
            }

    def get_recent_hires(self, days: int = 90) -> List[sqlite3.Row]:
        """Pobierz pracowników zatrudnionych w ostatnich X dniach"""
        query = """
            SELECT * FROM employees
            WHERE hire_date >= date('now', '-' || ? || ' days')
            ORDER BY hire_date DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (days,))
            return cursor.fetchall()

    def find_by_email(self, email: str) -> Optional[sqlite3.Row]:
        """Znajdź pracownika po adresie email"""
        query = "SELECT * FROM employees WHERE email = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (email,))
            return cursor.fetchone()

    def terminate_employee(self, employee_id: int, termination_date: date = None) -> bool:
        """Zwolnij pracownika (ustaw status na terminated)"""
        if termination_date is None:
            termination_date = date.today()

        query = """
            UPDATE employees
            SET employment_status = 'terminated',
                termination_date = ?,
                is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (termination_date.isoformat(), employee_id))
            conn.commit()
            return cursor.rowcount > 0
