"""
Repository dla operacji na pracownikach (employees)
"""
from typing import Any, List, Optional
from datetime import datetime, date
from repositories.db_utils import parse_dt, parse_date
from config.database import get_db_connection, safe_commit
from config.admin_view import emp_exclusion_sql_inline
from database.models import Employee
from repositories.auditable import AuditableMixin
from repositories.audit_repository import AuditRepository


class EmployeeRepository(AuditableMixin):
    """Repository do zarządzania pracownikami salonu.

    Audytowane (improvement #7 Step 3 via AuditableMixin): create / update /
    deactivate / activate / terminate_employee — zmiany danych pracownika, w tym
    wynagrodzeń (base_salary, employer_cost_rate). Writes używają safe_commit zamiast
    surowego conn.commit(), więc audyt jest atomowy z zapisem wewnątrz
    managed_transaction (a poza nią commituje natychmiast — bez zmiany zachowania).
    """

    audit_entity_type = 'employee'

    def row_to_employee(self, row: Any) -> Employee:
        """Konwertuj Row na obiekt Employee"""
        if not row:
            return None

        return Employee(
            id=row['id'],
            user_id=row['user_id'],
            forma_zatrudnienia_id=row['forma_zatrudnienia_id'],
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
            employer_cost_rate=float(row['employer_cost_rate']) if row['employer_cost_rate'] else 0.22,
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
                user_id, forma_zatrudnienia_id, first_name, last_name, phone, email, position,
                employment_status, hire_date, termination_date,
                base_salary, commission_rate, employer_cost_rate, skills, specializations,
                work_schedule, max_appointments_per_day, notes, photo_path, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            employee.user_id,
            employee.forma_zatrudnienia_id,
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
            employee.employer_cost_rate,
            employee.skills,
            employee.specializations,
            employee.work_schedule,
            employee.max_appointments_per_day,
            employee.notes,
            employee.photo_path,
            employee.is_active
        ))
        result_id = cursor.fetchone()["id"]
        safe_commit(conn)
        self._audit('CREATE', result_id,
                    label=f"{employee.first_name} {employee.last_name}".strip())
        return result_id

    _COLUMNS = (
        'id, user_id, forma_zatrudnienia_id, first_name, last_name, phone, email, '
        'position, employment_status, hire_date, termination_date, '
        'base_salary, commission_rate, employer_cost_rate, '
        'skills, specializations, work_schedule, max_appointments_per_day, '
        'notes, photo_path, is_active, created_at, updated_at'
    )

    def get_by_id(self, employee_id: int) -> Optional[Any]:
        """Pobierz pracownika po ID"""
        query = f"SELECT {self._COLUMNS} FROM employees WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchone()

    def get_mobile_pin_hash(self, employee_id: int) -> Optional[str]:
        """Bcrypt hash of the employee's mobile-app PIN, or None if not set yet.

        Kept out of _COLUMNS / the Employee dataclass on purpose — this must
        never surface through the admin employee-edit forms or any other
        existing serialization path.
        """
        excl = emp_exclusion_sql_inline('id')
        query = f"SELECT mobile_pin_hash FROM employees WHERE id = %s AND is_active = TRUE {excl}"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            row = cursor.fetchone()
            return row['mobile_pin_hash'] if row else None

    def set_mobile_pin_hash(self, employee_id: int, pin_hash: str) -> None:
        """Set the employee's mobile-app PIN hash. Only ever called when none exists yet."""
        excl = emp_exclusion_sql_inline('id')
        query = f"UPDATE employees SET mobile_pin_hash = %s, updated_at = %s WHERE id = %s AND is_active = TRUE {excl}"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (pin_hash, datetime.now(), employee_id))
            safe_commit(conn)

    def get_by_user_id(self, user_id: int) -> Optional[Any]:
        """Pobierz pracownika po user_id"""
        query = f"SELECT {self._COLUMNS} FROM employees WHERE user_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            return cursor.fetchone()

    def get_all(self, active_only: bool = True) -> List[Any]:
        """Pobierz wszystkich pracowników.

        Widok administratora: superuser-linked employees are dropped from this
        selection list (and everything fed by it — /employees, calendar pickers,
        direct-report choosers, balance lists) unless admin view is ON. ``WHERE
        TRUE`` keeps the non-active branch valid whether or not a clause is added.
        """
        excl = emp_exclusion_sql_inline('id')
        if active_only:
            query = f"SELECT {self._COLUMNS} FROM employees WHERE is_active = TRUE {excl} ORDER BY last_name, first_name"
        else:
            query = f"SELECT {self._COLUMNS} FROM employees WHERE TRUE {excl} ORDER BY last_name, first_name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_position(self, position: str, active_only: bool = True) -> List[Any]:
        """Pobierz pracowników według pozycji"""
        excl = emp_exclusion_sql_inline('id')
        if active_only:
            query = f"SELECT {self._COLUMNS} FROM employees WHERE position = %s AND is_active = TRUE {excl} ORDER BY last_name, first_name"
        else:
            query = f"SELECT {self._COLUMNS} FROM employees WHERE position = %s {excl} ORDER BY last_name, first_name"

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (position,))
            return cursor.fetchall()

    def get_by_employment_status(self, status: str) -> List[Any]:
        """Pobierz pracowników według statusu zatrudnienia"""
        excl = emp_exclusion_sql_inline('id')
        query = f"SELECT {self._COLUMNS} FROM employees WHERE employment_status = %s {excl} ORDER BY last_name, first_name"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status,))
            return cursor.fetchall()

    def search(self, query: str, active_only: bool = True) -> List[Any]:
        """Wyszukaj pracowników po imieniu, nazwisku, telefonie lub emailu"""
        search_pattern = f"%{query}%"
        excl = emp_exclusion_sql_inline('id')
        if active_only:
            sql = f"""
                SELECT {self._COLUMNS} FROM employees
                WHERE (first_name ILIKE %s OR last_name ILIKE %s OR phone ILIKE %s OR email ILIKE %s)
                AND is_active = TRUE {excl}
                ORDER BY last_name, first_name
            """
        else:
            sql = f"""
                SELECT {self._COLUMNS} FROM employees
                WHERE (first_name ILIKE %s OR last_name ILIKE %s OR phone ILIKE %s OR email ILIKE %s) {excl}
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
                forma_zatrudnienia_id = %s,
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
                employer_cost_rate = %s,
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            employee.user_id,
            employee.forma_zatrudnienia_id,
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
            employee.employer_cost_rate,
            employee.skills,
            employee.specializations,
            employee.work_schedule,
            employee.max_appointments_per_day,
            employee.notes,
            employee.photo_path,
            employee.is_active,
            employee_id
        ))
        changed = cursor.rowcount > 0
        safe_commit(conn)
        if changed:
            self._audit('UPDATE', employee_id,
                        label=f"{employee.first_name} {employee.last_name}".strip())
        return changed

    def delete(self, employee_id: int) -> bool:
        """Usuń pracownika (soft delete - ustawia is_active na False)"""
        return self.deactivate(employee_id)

    def deactivate(self, employee_id: int) -> bool:
        """Dezaktywuj pracownika"""
        query = "UPDATE employees SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (employee_id,))
        changed = cursor.rowcount > 0
        safe_commit(conn)
        if changed:
            self._audit('UPDATE', employee_id,
                        field_name='is_active', old='true', new='false')
        return changed

    def activate(self, employee_id: int) -> bool:
        """Aktywuj pracownika"""
        query = "UPDATE employees SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (employee_id,))
        changed = cursor.rowcount > 0
        safe_commit(conn)
        if changed:
            self._audit('UPDATE', employee_id,
                        field_name='is_active', old='false', new='true')
        return changed

    def get_positions(self) -> List[str]:
        """Pobierz listę wszystkich pozycji"""
        excl = emp_exclusion_sql_inline('id')
        query = f"SELECT DISTINCT position FROM employees WHERE position IS NOT NULL {excl} ORDER BY position"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [row['position'] for row in cursor.fetchall()]

    def get_statistics(self) -> dict:
        """Pobierz statystyki pracowników"""
        query = f"""
            SELECT
                COUNT(*) as total_employees,
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_employees,
                COUNT(CASE WHEN employment_status = 'active' THEN 1 END) as employed,
                COUNT(CASE WHEN employment_status = 'on_leave' THEN 1 END) as on_leave,
                COUNT(CASE WHEN employment_status = 'terminated' THEN 1 END) as terminated,
                COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as linked_to_users,
                AVG(CASE WHEN base_salary IS NOT NULL THEN base_salary END) as avg_salary
            FROM employees
            WHERE TRUE {emp_exclusion_sql_inline('id')}
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
        query = f"""
            SELECT {self._COLUMNS} FROM employees
            WHERE hire_date >= CURRENT_DATE - INTERVAL '1 day' * %s {emp_exclusion_sql_inline('id')}
            ORDER BY hire_date DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (days,))
            return cursor.fetchall()

    def find_by_email(self, email: str) -> Optional[Any]:
        """Znajdź pracownika po adresie email"""
        query = f"SELECT {self._COLUMNS} FROM employees WHERE email = %s"
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (termination_date.isoformat(), employee_id))
        changed = cursor.rowcount > 0
        safe_commit(conn)
        if changed:
            self._audit('UPDATE', employee_id, field_name='employment_status',
                        new='terminated')
        return changed

    def count_blocking_references(self, employee_id: int) -> dict:
        """Count RESTRICT-protected rows that would block a hard delete.

        ``appointments.employee_id`` and ``income_records.employee_id`` are
        ``ON DELETE RESTRICT`` and hold operational / financial history that must
        stay intact. A hard delete has to be refused while any such rows exist —
        otherwise PostgreSQL raises ForeignKeyViolation and the whole transaction
        aborts. The route uses this to give a clear message instead of a 500.

        Returns ``{'appointments': int, 'income_records': int}``.
        """
        query = """
            SELECT
                (SELECT COUNT(*) FROM appointments   WHERE employee_id = %s) AS appointments,
                (SELECT COUNT(*) FROM income_records WHERE employee_id = %s) AS income_records
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, employee_id))
            row = cursor.fetchone()
        return {
            'appointments': int(row['appointments']),
            'income_records': int(row['income_records']),
        }

    def hard_delete(self, employee_id: int) -> bool:
        """Permanently delete an employee row plus its absence / balance data.

        DESTRUCTIVE — superuser-only, intended for cleaning up production-test
        records. MUST run inside ``managed_transaction()`` so the absence wipe, the
        row delete and the DELETE audit entry commit atomically (and any linked
        user deletion the caller performs joins the same unit of work).

        Removes, in order:
          1. balance-adjustment / limit audit-log history (joined on the limit and
             adjustment rows, so it must run *before* the CASCADE drops them);
          2. ``employee_absences`` rows (``ON DELETE RESTRICT`` — would otherwise
             block step 3);
          3. the ``employees`` row itself, whose CASCADE foreign keys clear the
             dependent junction data: ``employee_services``,
             ``employee_availability``, ``employee_supervisors``,
             ``client_preferences``, ``employee_absence_limits`` and
             ``absence_balance_adjustments``.

        It deliberately does NOT touch ``appointments`` / ``income_records`` (those
        are RESTRICT and must stay intact — caller pre-checks via
        :meth:`count_blocking_references`). Writes a ``DELETE`` audit entry for the
        employee. Returns True when a row was removed.
        """
        emp = self.get_by_id(employee_id)
        if not emp:
            return False
        label = f"{emp['first_name']} {emp['last_name']}".strip()

        # 1) balance audit history — while limit/adjustment rows still exist
        AuditRepository().delete_for_employee_balance(employee_id)
        # 2) absence records (RESTRICT — explicit delete required) + the employee row
        #    (CASCADE clears the junction tables + balance rows). Same connection so
        #    safe_commit defers inside the caller's managed_transaction.
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM employee_absences WHERE employee_id = %s", (employee_id,))
        cursor.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
        deleted = cursor.rowcount > 0
        safe_commit(conn)
        if deleted:
            self._audit('DELETE', employee_id, label=label)
        return deleted
