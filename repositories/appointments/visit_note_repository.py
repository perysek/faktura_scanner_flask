"""Repository for visit notes ("Uwagi i zalecenia z wizyt").

Every read is scoped the same way, in one place (`_scope`): the app-wide
admin-view exclusion (the owner-employee's visits stay hidden from everyone but
superusers) AND the caller's own-data restriction. The service decides who may
do what; this layer guarantees the SQL actually carries that scope.
"""
from typing import Any, List, Optional

from config.admin_view import emp_exclusion_sql
from repositories.base_repository import BaseRepository

# Naive UTC — the house convention for server-stamped columns (see the migration).
_UTC_NOW = "(NOW() AT TIME ZONE 'UTC')"

# The visit's "first service": a main service before any add-on, then insertion order.
_FIRST_SERVICE = """
    LEFT JOIN LATERAL (
        SELECT s.name AS service_name
        FROM appointment_services aps
        JOIN services s ON s.id = aps.service_id
        WHERE aps.appointment_id = a.id
        ORDER BY aps.is_addon ASC, aps.id ASC
        LIMIT 1
    ) fs ON TRUE
"""


class VisitNoteRepository(BaseRepository):
    """Data access for the visit_notes table (soft-deleted via is_deleted)."""

    _soft_delete = True

    def __init__(self):
        super().__init__('visit_notes')

    @staticmethod
    def _scope(own_employee_id: Optional[int]) -> tuple:
        """AND-clause + params limiting ``a.employee_id`` for the current caller.

        ``own_employee_id`` None means "every visit"; an id restricts to that
        employee (``-1`` — own-data without a linked employee — matches nobody).
        """
        clause, params = emp_exclusion_sql('a.employee_id')
        params = list(params)
        if own_employee_id is not None:
            clause += ' AND a.employee_id = %s '
            params.append(own_employee_id)
        return clause, params

    # ── reads ────────────────────────────────────────────────────────────────

    def list_for_client(self, client_id: int, own_employee_id: Optional[int],
                        limit: int, offset: int) -> List[Any]:
        """A client's live notes across all their visits, newest edit first."""
        scope_sql, scope_params = self._scope(own_employee_id)
        query = f"""
            SELECT n.id, n.appointment_id, n.note_text, n.updated_at,
                   a.appointment_date, a.employee_id,
                   (c.first_name || ' ' || c.last_name) AS client_name,
                   fs.service_name,
                   u.full_name AS updated_by_name
            FROM visit_notes n
            JOIN appointments a ON a.id = n.appointment_id AND a.is_deleted = FALSE
            JOIN clients c ON c.id = a.client_id
            LEFT JOIN users u ON u.id = n.updated_by
            {_FIRST_SERVICE}
            WHERE a.client_id = %s AND n.is_deleted = FALSE {scope_sql}
            ORDER BY n.updated_at DESC, n.id DESC
            LIMIT %s OFFSET %s
        """
        return self._fetch_all(query, tuple([client_id] + scope_params + [limit, offset]))

    def count_for_client(self, client_id: int, own_employee_id: Optional[int]) -> int:
        scope_sql, scope_params = self._scope(own_employee_id)
        query = f"""
            SELECT COUNT(*) AS total
            FROM visit_notes n
            JOIN appointments a ON a.id = n.appointment_id AND a.is_deleted = FALSE
            WHERE a.client_id = %s AND n.is_deleted = FALSE {scope_sql}
        """
        row = self._fetch_one(query, tuple([client_id] + scope_params))
        return int(row['total']) if row else 0

    def eligible_visits(self, client_id: int, own_employee_id: Optional[int],
                        limit: int = 50) -> List[Any]:
        """Completed visits of the client that a note may be attached to."""
        scope_sql, scope_params = self._scope(own_employee_id)
        query = f"""
            SELECT a.id AS appointment_id, a.appointment_date, fs.service_name,
                   (e.first_name || ' ' || e.last_name) AS employee_name
            FROM appointments a
            JOIN employees e ON e.id = a.employee_id
            {_FIRST_SERVICE}
            WHERE a.client_id = %s AND a.status = 'completed' AND a.is_deleted = FALSE
                  {scope_sql}
            ORDER BY a.appointment_date DESC, a.start_time DESC
            LIMIT %s
        """
        return self._fetch_all(query, tuple([client_id] + scope_params + [limit]))

    def recent_for_clients(self, client_ids: List[int], own_employee_id: Optional[int],
                           per_client: int) -> List[Any]:
        """The ``per_client`` newest notes of each listed client — ONE query.

        Backs the list columns; a window function keeps it a single round trip
        however many clients are on screen (never N+1).
        """
        if not client_ids:
            return []
        scope_sql, scope_params = self._scope(own_employee_id)
        query = f"""
            SELECT client_id, note_text, updated_at
            FROM (
                SELECT a.client_id, n.note_text, n.updated_at,
                       ROW_NUMBER() OVER (PARTITION BY a.client_id
                                          ORDER BY n.updated_at DESC, n.id DESC) AS rn
                FROM visit_notes n
                JOIN appointments a ON a.id = n.appointment_id AND a.is_deleted = FALSE
                WHERE n.is_deleted = FALSE AND a.client_id = ANY(%s) {scope_sql}
            ) ranked
            WHERE rn <= %s
            ORDER BY client_id, rn
        """
        return self._fetch_all(query, tuple([list(client_ids)] + scope_params + [per_client]))

    def get_with_visit(self, note_id: int) -> Optional[Any]:
        """A live note with the visit facts the service needs to authorize a write."""
        query = """
            SELECT n.id, n.appointment_id, n.note_text,
                   a.employee_id, a.client_id,
                   (c.first_name || ' ' || c.last_name) AS client_name
            FROM visit_notes n
            JOIN appointments a ON a.id = n.appointment_id AND a.is_deleted = FALSE
            JOIN clients c ON c.id = a.client_id
            WHERE n.id = %s AND n.is_deleted = FALSE
        """
        return self._fetch_one(query, (note_id,))

    # ── writes ───────────────────────────────────────────────────────────────

    def create(self, appointment_id: int, note_text: str, user_id: int) -> Optional[int]:
        """Insert a note; created_* and updated_* start out identical."""
        query = """
            INSERT INTO visit_notes (appointment_id, note_text, created_by, updated_by)
            VALUES (%s, %s, %s, %s)
        """
        return self._execute_insert(query, (appointment_id, note_text, user_id, user_id))

    def update_text(self, note_id: int, note_text: str, user_id: int) -> bool:
        """Edit the text; only updated_* move — created_* are never touched."""
        query = f"""
            UPDATE visit_notes
            SET note_text = %s, updated_at = {_UTC_NOW}, updated_by = %s
            WHERE id = %s AND is_deleted = FALSE
        """
        return self._execute(query, (note_text, user_id, note_id)).rowcount > 0

    def soft_delete(self, note_id: int, user_id: int) -> bool:
        query = f"""
            UPDATE visit_notes
            SET is_deleted = TRUE, deleted_at = {_UTC_NOW}, updated_by = %s
            WHERE id = %s AND is_deleted = FALSE
        """
        return self._execute(query, (user_id, note_id)).rowcount > 0
