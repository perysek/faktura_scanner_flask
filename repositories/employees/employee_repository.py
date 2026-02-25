"""
Repository dla operacji na pracownikach (employees)
"""
from typing import Any, List, Optional
from datetime import datetime
from repositories.db_utils import parse_dt, parse_date
from config.database import get_db_connection
from database.models import Employee


class EmployeeRepository:
    """Repository do zarządzania pracownikami salonu"""

    def row_to_employee(self, row: Any) -> Employee:
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
            hire_date=parse_date(row['hire_date']),
            termination_date=parse_date(row['termination_date']),
            base_salary=float(row['base_salary']) if row['base_salary'] else None,
            commission_rate=float(row['commission_rate']) if row['commission_rate'] else None,
            skills=row['skills'],
            specializations=row['specializations'],
            work_schedule=row['work_schedule'],
            max_appointments_per_day=row['max_appointments_per_day'],
            notes=row['notes'],
            photo_path=row['photo_path'],
            is_active=bool(row['is_active']),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at'])
        )

    def create(self, employee: Employee) -> int:
        """Utwórz nowego pracownika"""
        query = """
            INSERT INTO employees (
                user_id, first_name, last_name, phone, email, position,
                employment_status, hire_date, termination_date,
                base_salary, commission_rate, skills, specializations,
                work_schedule, max_appointments_per_day, notes, photo_path, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
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
            result_id = cursor.fetchone()["id"]
            conn.commit()
            return result_id

    def get_by_id(self, employee_id: int) -> Optional[Any]:
        """Pobierz pracownika po ID"""
        query = "SELECT * FROM employees WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchone()

    def get_by_user_id(self, user_id: int) -> Optional[Any]:
        """Pobierz pracownika po user_id"""
        query = "SELECT * FROM employees WHERE user_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchone()

    def get_all(self, active_only: bool = True) -> List[Any]:
        """Pobierz wszystkich pracowników"""
        if active_only:
            query = "SELECT * FROM employees WHERE is_active = TRUE ORDER BY last_name, first_name"
        else:
            query = "SELECT * FROM employees ORDER BY last_name, first_name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_position(self, position: str, active_only: bool = True) -> List[Any]:
        """Pobierz pracowników według pozycji"""
        if active_only:
            query = "SELECT * FROM employees WHERE position = %s AND is_active = TRUE ORDER BY last_name, first_name"
        else:
            query = "SELECT * FROM employees WHERE position = %s ORDER BY last_name, first_name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (position,))
            return cursor.fetchall()

    def get_by_employment_status(self, status: str) -> List[Any]:
        """Pobierz pracowników według statusu zatrudnienia"""
        query = "SELECT * FROM employees WHERE employment_status = %s ORDER BY last_name, first_name"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status,))
            return cursor.fetchall()

    def search(self, query: str, active_only: bool = True) -> List[Any]:
        """Wyszukaj pracowników po imieniu, nazwisku, telefonie lub emailu"""
        search_pattern = f"%{query}%"
        if active_only:
            sql = """
                SELECT * FROM employees
                WHERE (first_name LIKE %s OR last_name LIKE %s OR phone LIKE %s OR email LIKE %s)
                AND is_active = TRUE
                ORDER BY last_name, first_name
            """
        else:
            sql = """
                SELECT * FROM employees
                WHERE first_name LIKE %s OR last_name LIKE %s OR phone LIKE %s OR email LIKE %s
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
            SET user_id = %s,
                first_name = %s,
                last_name = %s,
                phone = %s,
                email = %s,
                position = %s,
                employment_status = %s,
                hire_date = %s,
                termination_date = %s,
                base_salary = %s,
                commission_rate = %s,
                skills = %s,
                specializations = %s,
                work_schedule = %s,
                max_appointments_per_day = %s,
                notes = %s,
                photo_path = %s,
                is_active = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
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
        query = "UPDATE employees SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            conn.commit()
            return cursor.rowcount > 0

    def activate(self, employee_id: int) -> bool:
        """Aktywuj pracownika"""
        query = "UPDATE employees SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
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
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_employees,
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

    def get_recent_hires(self, days: int = 90) -> List[Any]:
        """Pobierz pracowników zatrudnionych w ostatnich X dniach"""
        query = """
            SELECT * FROM employees
            WHERE hire_date >= CURRENT_DATE - INTERVAL '1 day' * %s
            ORDER BY hire_date DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (days,))
            return cursor.fetchall()

    def find_by_email(self, email: str) -> Optional[Any]:
        """Znajdź pracownika po adresie email"""
        query = "SELECT * FROM employees WHERE email = %s"
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
                termination_date = %s,
                is_active = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (termination_date.isoformat(), employee_id))
            conn.commit()
            return cursor.rowcount > 0
