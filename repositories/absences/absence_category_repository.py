"""
Repository dla kategorii nieobecności (absence_categories).
"""
from typing import Any, List, Optional
from datetime import datetime

from config.database import get_db_connection
from database.models import AbsenceCategory
from repositories.db_utils import parse_dt


class AbsenceCategoryRepository:
    """CRUD dla słownikowej tabeli absence_categories."""

    _COLUMNS = (
        'id, name, description, absence_full_day, '
        'is_deleted, deleted_at, created_at, updated_at'
    )

    def row_to_category(self, row: Any) -> AbsenceCategory:
        if not row:
            return None
        return AbsenceCategory(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            absence_full_day=bool(row['absence_full_day']),
            is_deleted=bool(row['is_deleted']),
            deleted_at=parse_dt(row['deleted_at']),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at']),
        )

    # ── reads ─────────────────────────────────────────────────────────────────

    def list_active(self) -> List[Any]:
        """Wszystkie nie-usunięte kategorie — do zasilania dropdownów."""
        query = f"""
            SELECT {self._COLUMNS} FROM absence_categories
            WHERE is_deleted = FALSE
            ORDER BY absence_full_day DESC, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def list_with_deleted(self) -> List[Any]:
        """Wszystkie kategorie łącznie z usuniętymi (widok admina — tab #3)."""
        query = f"""
            SELECT {self._COLUMNS} FROM absence_categories
            ORDER BY is_deleted, absence_full_day DESC, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def get_by_id(self, category_id: int) -> Optional[Any]:
        query = f"SELECT {self._COLUMNS} FROM absence_categories WHERE id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_id,))
            return cursor.fetchone()

    def get_by_name(self, name: str) -> Optional[Any]:
        query = f"SELECT {self._COLUMNS} FROM absence_categories WHERE name = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (name,))
            return cursor.fetchone()

    # ── writes ────────────────────────────────────────────────────────────────

    def create(self, category: AbsenceCategory) -> int:
        query = """
            INSERT INTO absence_categories (name, description, absence_full_day)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                category.name,
                category.description,
                category.absence_full_day,
            ))
            new_id = cursor.fetchone()['id']
            conn.commit()
            return new_id

    def update(self, category_id: int, category: AbsenceCategory) -> bool:
        query = """
            UPDATE absence_categories
            SET name = %s,
                description = %s,
                absence_full_day = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                category.name,
                category.description,
                category.absence_full_day,
                category_id,
            ))
            conn.commit()
            return cursor.rowcount > 0

    def soft_delete(self, category_id: int) -> bool:
        query = """
            UPDATE absence_categories
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_id,))
            conn.commit()
            return cursor.rowcount > 0

    def restore(self, category_id: int) -> bool:
        query = """
            UPDATE absence_categories
            SET is_deleted = FALSE,
                deleted_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = TRUE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_id,))
            conn.commit()
            return cursor.rowcount > 0
