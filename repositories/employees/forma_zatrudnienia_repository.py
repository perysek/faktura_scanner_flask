"""
Repository dla operacji na formach zatrudnienia
"""
from typing import Any, List, Optional

from config.database import get_db_connection
from database.models import FormaZatrudnienia


class FormaZatrudnieniaRepository:
    """Repository do zarządzania formami zatrudnienia"""

    def row_to_forma(self, row: Any) -> FormaZatrudnienia:
        """Konwertuj Row na obiekt FormaZatrudnienia"""
        if not row:
            return None

        return FormaZatrudnienia(
            id=row['id'],
            nazwa=row['nazwa'],
            uwagi=row['uwagi'],
            min_salary_required=bool(row['min_salary_required']),
            granted_salary=bool(row['granted_salary']),
            commision_included=bool(row['commision_included']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )

    def get_all(self) -> List[Any]:
        """Pobierz wszystkie formy zatrudnienia"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM formy_zatrudnienia ORDER BY nazwa")
            return cursor.fetchall()

    def get_by_id(self, forma_id: int) -> Optional[Any]:
        """Pobierz formę zatrudnienia po ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM formy_zatrudnienia WHERE id = %s", (forma_id,))
            return cursor.fetchone()

    def create(self, forma: FormaZatrudnienia) -> int:
        """Utwórz nową formę zatrudnienia"""
        query = """
            INSERT INTO formy_zatrudnienia
                (nazwa, uwagi, min_salary_required, granted_salary, commision_included)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                forma.nazwa,
                forma.uwagi,
                forma.min_salary_required,
                forma.granted_salary,
                forma.commision_included,
            ))
            result_id = cursor.fetchone()['id']
            conn.commit()
            return result_id

    def update(self, forma_id: int, forma: FormaZatrudnienia) -> bool:
        """Zaktualizuj formę zatrudnienia"""
        query = """
            UPDATE formy_zatrudnienia
            SET nazwa = %s,
                uwagi = %s,
                min_salary_required = %s,
                granted_salary = %s,
                commision_included = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                forma.nazwa,
                forma.uwagi,
                forma.min_salary_required,
                forma.granted_salary,
                forma.commision_included,
                forma_id,
            ))
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, forma_id: int) -> bool:
        """Usuń formę zatrudnienia (sprawdza czy nie jest używana)"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as count FROM employees WHERE forma_zatrudnienia_id = %s",
                (forma_id,)
            )
            count = cursor.fetchone()['count']
            if count > 0:
                raise ValueError(
                    f"Nie można usunąć formy zatrudnienia — jest przypisana do {count} pracownik(ów)"
                )
            cursor.execute("DELETE FROM formy_zatrudnienia WHERE id = %s", (forma_id,))
            conn.commit()
            return cursor.rowcount > 0
