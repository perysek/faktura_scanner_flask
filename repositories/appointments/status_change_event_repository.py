"""Repository for real-time status-change notification events."""
from datetime import datetime
from typing import List

from repositories.base_repository import BaseRepository


class StatusChangeEventRepository(BaseRepository):
    """Manages the status_change_events table consumed by the web polling endpoint."""

    def __init__(self):
        super().__init__('status_change_events')

    def create(self, appointment_id: int, old_status: str, new_status: str,
               triggered_by: str = 'employee_mobile') -> int:
        """Insert a status_change_events row. Returns the new id."""
        sql = """
            INSERT INTO status_change_events
                (appointment_id, old_status, new_status, triggered_by)
            VALUES (%s, %s, %s, %s)
        """
        return self._execute_insert(sql, (appointment_id, old_status, new_status, triggered_by))

    def get_since(self, since: datetime) -> List[dict]:
        """Fetch all events created after 'since'. Consumed by the polling endpoint."""
        sql = """
            SELECT e.*,
                   c.first_name || ' ' || c.last_name AS client_name
            FROM status_change_events e
            JOIN appointments a ON a.id = e.appointment_id
            JOIN clients c      ON c.id = a.client_id
            WHERE e.created_at > %s
            ORDER BY e.created_at
        """
        return [dict(r) for r in self._fetch_all(sql, (since,))]
