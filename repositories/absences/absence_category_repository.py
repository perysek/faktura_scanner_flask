"""
Repository dla kategorii nieobecności (absence_categories).
"""
from typing import Any, List, Optional
from datetime import datetime

from config.database import get_db_connection, safe_commit
from database.models import AbsenceCategory
from repositories.db_utils import parse_dt


class AbsenceCategoryRepository:
    """CRUD dla słownikowej tabeli absence_categories."""

    _COLUMNS = (
        'id, name, description, absence_full_day, '
        'is_deleted, deleted_at, created_at, updated_at, '
        'is_tracked, count_period, resets_at, rolling_days, '
        'warning_threshold_pct, default_max_value'
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
            is_tracked=bool(row['is_tracked']),
            count_period=row['count_period'] or 'yearly',
            resets_at=row['resets_at'],
            rolling_days=row['rolling_days'],
            warning_threshold_pct=float(row['warning_threshold_pct'] or 0.80),
            default_max_value=float(row['default_max_value'] or 0.0),
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

    def list_tracked(self) -> List[Any]:
        """Kategorie z włączonym śledzeniem bilansu (is_tracked=TRUE)."""
        query = f"""
            SELECT {self._COLUMNS} FROM absence_categories
            WHERE is_tracked = TRUE AND is_deleted = FALSE
            ORDER BY absence_full_day DESC, name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def create(self, category: AbsenceCategory) -> int:
        query = """
            INSERT INTO absence_categories
                (name, description, absence_full_day,
                 is_tracked, count_period, resets_at, rolling_days,
                 warning_threshold_pct, default_max_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            category.name,
            category.description,
            category.absence_full_day,
            category.is_tracked,
            category.count_period,
            category.resets_at,
            category.rolling_days,
            category.warning_threshold_pct,
            category.default_max_value,
        ))
        new_id = cursor.fetchone()['id']
        safe_commit(conn)
        return new_id

    def update(self, category_id: int, category: AbsenceCategory) -> bool:
        query = """
            UPDATE absence_categories
            SET name = %s,
                description = %s,
                absence_full_day = %s,
                is_tracked = %s,
                count_period = %s,
                resets_at = %s,
                rolling_days = %s,
                warning_threshold_pct = %s,
                default_max_value = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            category.name,
            category.description,
            category.absence_full_day,
            category.is_tracked,
            category.count_period,
            category.resets_at,
            category.rolling_days,
            category.warning_threshold_pct,
            category.default_max_value,
            category_id,
        ))
        safe_commit(conn)
        return cursor.rowcount > 0

    def soft_delete(self, category_id: int) -> bool:
        query = """
            UPDATE absence_categories
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (category_id,))
        safe_commit(conn)
        return cursor.rowcount > 0

    def restore(self, category_id: int) -> bool:
        query = """
            UPDATE absence_categories
            SET is_deleted = FALSE,
                deleted_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = TRUE
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (category_id,))
        safe_commit(conn)
        return cursor.rowcount > 0

    def count_absence_references(self, category_id: int) -> int:
        """Count absences referencing this category (including soft-deleted ones).

        ``absence_categories.id`` is ``ON DELETE RESTRICT`` from
        ``employee_absences.category_id``, so a hard delete fails while ANY absence
        row references it — and ``employee_absences.is_deleted`` is a soft flag, so
        soft-deleted absences still count. The caller pre-checks this to return a
        clear message instead of a raw ForeignKeyViolation / 500.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) AS n FROM employee_absences WHERE category_id = %s",
                (category_id,),
            )
            return int(cursor.fetchone()['n'])

    def hard_delete(self, category_id: int) -> bool:
        """Permanently remove a category row (superuser purge of a soft-deleted row).

        ``employee_absence_limits`` and ``absence_balance_adjustments`` reference the
        category with ``ON DELETE CASCADE``, so their balance config / history is
        cleared automatically. ``employee_absences`` references it with ``RESTRICT``,
        so the caller MUST pre-check via :meth:`count_absence_references` and refuse
        when any absence uses it. Cooperates with a caller's ``managed_transaction``
        via ``safe_commit``.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM absence_categories WHERE id = %s", (category_id,))
        deleted = cursor.rowcount > 0
        safe_commit(conn)
        return deleted
