"""Repository for support tickets ("Zgłoś problem lub podziel się pomysłem").

Pure data access — who may see/do what (author vs. 'support_tickets' module) and
every status transition live in services.support_ticket_service. Attachment bytes
are only ever read by `get_attachment`; every list query leaves the `data` column out.
"""
import json
from typing import Any, Dict, List, Optional, Sequence

from repositories.base_repository import BaseRepository

# Naive UTC — the house convention for server-stamped columns (see the migration).
_UTC_NOW = "(NOW() AT TIME ZONE 'UTC')"

OPEN_STATUSES = ('new', 'seen', 'in_progress', 'waiting_user', 'resolved')

# Admin list views (left rail of the issues app). Each is a WHERE fragment on `t`.
ADMIN_VIEWS: Dict[str, str] = {
    'open': "t.status <> 'closed'",
    'unread': "t.status <> 'closed' AND (t.admin_last_read_at IS NULL OR t.admin_last_read_at < t.last_user_activity_at)",
    'new': "t.status = 'new'",
    'in_progress': "t.status IN ('seen', 'in_progress')",
    'waiting_user': "t.status = 'waiting_user'",
    'resolved': "t.status = 'resolved'",
    'closed': "t.status = 'closed'",
    'mine': "t.status <> 'closed' AND t.assigned_to = %(me)s",
    'unassigned': "t.status <> 'closed' AND t.assigned_to IS NULL",
    'all': 'TRUE',
}

ADMIN_SORTS: Dict[str, str] = {
    'updated': 't.updated_at DESC, t.id DESC',
    'created': 't.created_at DESC, t.id DESC',
    'oldest': 't.created_at ASC, t.id ASC',
    'priority': ("CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, "
                 't.updated_at DESC, t.id DESC'),
}

_TICKET_COLUMNS = """
    t.id, t.created_by, t.kind, t.area, t.area_label, t.title, t.status, t.priority,
    t.assigned_to, t.close_reason, t.created_at, t.updated_at,
    t.last_user_activity_at, t.last_admin_activity_at, t.user_last_read_at,
    t.admin_last_read_at, t.first_response_at, t.resolved_at, t.closed_at
"""

# Last public message of a ticket (preview line in both lists).
_LAST_PUBLIC = """
    LEFT JOIN LATERAL (
        SELECT m.body, m.author_kind, m.created_at
        FROM support_ticket_messages m
        WHERE m.ticket_id = t.id AND m.is_internal = FALSE AND m.author_kind <> 'system'
        ORDER BY m.created_at DESC, m.id DESC
        LIMIT 1
    ) lm ON TRUE
"""


class SupportTicketRepository(BaseRepository):
    """Data access for support_tickets + its messages and attachments."""

    def __init__(self):
        super().__init__('support_tickets')

    # ── writes ───────────────────────────────────────────────────────────────

    def create_ticket(self, *, user_id: int, kind: str, area: str, area_label: str, title: str,
                      priority: str, context: dict, body: str,
                      attachments: Sequence[dict]) -> int:
        """Ticket + its first message + screenshots, all-or-nothing."""
        with self.transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO support_tickets (created_by, kind, area, area_label, title, priority, context)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (user_id, kind, area, area_label, title, priority, json.dumps(context, default=str)),
            )
            ticket_id = cur.fetchone()['id']
            self._insert_message(cur, ticket_id, user_id, 'user', body, False, None, None, attachments)
            cur.execute(f"UPDATE support_tickets SET user_last_read_at = {_UTC_NOW} WHERE id = %s", (ticket_id,))
        return ticket_id

    def add_message(self, ticket_id: int, *, author_id: Optional[int], author_kind: str, body: str,
                    is_internal: bool = False, attachments: Sequence[dict] = (),
                    ticket_updates: Optional[Dict[str, Any]] = None,
                    events: Sequence[dict] = ()) -> int:
        """One message (+ screenshots), optional system event rows and a ticket UPDATE —
        in one transaction, so a reply and the status change it causes never split."""
        with self.transaction() as conn:
            cur = conn.cursor()
            message_id = self._insert_message(cur, ticket_id, author_id, author_kind, body,
                                              is_internal, None, None, attachments)
            for ev in events:
                self._insert_message(cur, ticket_id, ev.get('author_id'), 'system', '', False,
                                     ev['event'], ev.get('meta'), ())
            self._update_ticket(cur, ticket_id, ticket_updates or {})
        return message_id

    def apply_changes(self, ticket_id: int, ticket_updates: Dict[str, Any], events: Sequence[dict]) -> None:
        """Ticket field changes (status/priority/assignee) + the system rows that record them."""
        with self.transaction() as conn:
            cur = conn.cursor()
            for ev in events:
                self._insert_message(cur, ticket_id, ev.get('author_id'), 'system', '', False,
                                     ev['event'], ev.get('meta'), ())
            self._update_ticket(cur, ticket_id, ticket_updates)

    def mark_read(self, ticket_id: int, side: str) -> None:
        column = 'admin_last_read_at' if side == 'admin' else 'user_last_read_at'
        self._execute(f"UPDATE support_tickets SET {column} = {_UTC_NOW} WHERE id = %s", (ticket_id,))

    @staticmethod
    def _insert_message(cur, ticket_id, author_id, author_kind, body, is_internal, event, meta,
                        attachments) -> int:
        cur.execute(
            """
            INSERT INTO support_ticket_messages (ticket_id, author_id, author_kind, body, is_internal, event, meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (ticket_id, author_id, author_kind, body or '', is_internal, event,
             json.dumps(meta) if meta is not None else None),
        )
        message_id = cur.fetchone()['id']
        for att in attachments:
            cur.execute(
                """
                INSERT INTO support_ticket_attachments
                    (ticket_id, message_id, filename, mime, size_bytes, width, height, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (ticket_id, message_id, att['filename'], att['mime'], len(att['data']),
                 att.get('width'), att.get('height'), att['data']),
            )
        return message_id

    @staticmethod
    def _update_ticket(cur, ticket_id: int, updates: Dict[str, Any]) -> None:
        """SET col = value for each update; the sentinel 'NOW' stamps the current UTC time.
        Column names come from the service only (a fixed allow-list), never from input."""
        allowed = {'status', 'priority', 'assigned_to', 'close_reason', 'last_user_activity_at',
                   'last_admin_activity_at', 'user_last_read_at', 'admin_last_read_at',
                   'first_response_at', 'resolved_at', 'closed_at'}
        sets, params = [f'updated_at = {_UTC_NOW}'], []
        for col, value in updates.items():
            if col not in allowed:
                raise ValueError(f'support_tickets.{col} is not updatable')
            if value == 'NOW':
                sets.append(f'{col} = {_UTC_NOW}')
            else:
                sets.append(f'{col} = %s')
                params.append(value)
        cur.execute(f"UPDATE support_tickets SET {', '.join(sets)} WHERE id = %s", tuple(params + [ticket_id]))

    # ── reads ────────────────────────────────────────────────────────────────

    def get_ticket(self, ticket_id: int, with_context: bool = False) -> Optional[Any]:
        context_col = ', t.context' if with_context else ''
        query = f"""
            SELECT {_TICKET_COLUMNS} {context_col},
                   u.full_name AS requester_name, u.email AS requester_email, u.role AS requester_role,
                   r.display_name AS requester_role_label,
                   a.full_name AS assignee_name
            FROM support_tickets t
            LEFT JOIN users u ON u.id = t.created_by
            LEFT JOIN roles r ON r.name = u.role
            LEFT JOIN users a ON a.id = t.assigned_to
            WHERE t.id = %s
        """
        return self._fetch_one(query, (ticket_id,))

    def list_messages(self, ticket_id: int, include_internal: bool) -> List[Any]:
        internal = '' if include_internal else ' AND m.is_internal = FALSE'
        query = f"""
            SELECT m.id, m.author_id, m.author_kind, m.body, m.is_internal, m.event, m.meta, m.created_at,
                   u.full_name AS author_name
            FROM support_ticket_messages m
            LEFT JOIN users u ON u.id = m.author_id
            WHERE m.ticket_id = %s {internal}
            ORDER BY m.created_at ASC, m.id ASC
        """
        return self._fetch_all(query, (ticket_id,))

    def list_attachments(self, ticket_id: int) -> List[Any]:
        query = """
            SELECT id, message_id, filename, mime, size_bytes, width, height, created_at
            FROM support_ticket_attachments
            WHERE ticket_id = %s
            ORDER BY id
        """
        return self._fetch_all(query, (ticket_id,))

    def get_attachment(self, attachment_id: int) -> Optional[Any]:
        query = """
            SELECT a.id, a.ticket_id, a.filename, a.mime, a.size_bytes, a.data,
                   t.created_by, m.is_internal
            FROM support_ticket_attachments a
            JOIN support_tickets t ON t.id = a.ticket_id
            LEFT JOIN support_ticket_messages m ON m.id = a.message_id
            WHERE a.id = %s
        """
        return self._fetch_one(query, (attachment_id,))

    def list_for_user(self, user_id: int) -> List[Any]:
        """The caller's own conversations: needs-your-answer first, then newest activity."""
        query = f"""
            SELECT t.id, t.kind, t.area_label, t.title, t.status, t.close_reason, t.created_at, t.updated_at,
                   t.closed_at,
                   (t.last_admin_activity_at IS NOT NULL
                    AND (t.user_last_read_at IS NULL OR t.user_last_read_at < t.last_admin_activity_at)) AS unread,
                   lm.body AS last_body, lm.author_kind AS last_author_kind, lm.created_at AS last_message_at
            FROM support_tickets t
            {_LAST_PUBLIC}
            WHERE t.created_by = %s
            ORDER BY (t.status IN ('waiting_user', 'resolved')) DESC, t.updated_at DESC, t.id DESC
            LIMIT 100
        """
        return self._fetch_all(query, (user_id,))

    def unread_for_user(self, user_id: int) -> int:
        query = """
            SELECT COUNT(*) AS n FROM support_tickets t
            WHERE t.created_by = %s AND t.last_admin_activity_at IS NOT NULL
              AND (t.user_last_read_at IS NULL OR t.user_last_read_at < t.last_admin_activity_at)
        """
        row = self._fetch_one(query, (user_id,))
        return int(row['n']) if row else 0

    def count_recent_by_user(self, user_id: int, minutes: int) -> int:
        query = f"""
            SELECT COUNT(*) AS n FROM support_tickets
            WHERE created_by = %s AND created_at > {_UTC_NOW} - (%s * INTERVAL '1 minute')
        """
        row = self._fetch_one(query, (user_id, minutes))
        return int(row['n']) if row else 0

    def admin_list(self, *, view: str, me: int, kind: Optional[str], area: Optional[str],
                   priority: Optional[str], q: Optional[str], sort: str,
                   limit: int, offset: int) -> Dict[str, Any]:
        where = [ADMIN_VIEWS.get(view, ADMIN_VIEWS['open'])]
        params: Dict[str, Any] = {'me': me, 'limit': limit, 'offset': offset}
        if kind:
            where.append('t.kind = %(kind)s')
            params['kind'] = kind
        if area:
            where.append('t.area = %(area)s')
            params['area'] = area
        if priority:
            where.append('t.priority = %(priority)s')
            params['priority'] = priority
        if q:
            params['q'] = f'%{q}%'
            where.append("""(
                t.title ILIKE %(q)s OR u.full_name ILIKE %(q)s OR u.email ILIKE %(q)s
                OR CAST(t.id AS TEXT) = %(qid)s
                OR EXISTS (SELECT 1 FROM support_ticket_messages mq
                           WHERE mq.ticket_id = t.id AND mq.body ILIKE %(q)s)
            )""")
            params['qid'] = q.lstrip('#')
        where_sql = ' AND '.join(f'({w})' for w in where)
        order_sql = ADMIN_SORTS.get(sort, ADMIN_SORTS['updated'])
        query = f"""
            SELECT {_TICKET_COLUMNS},
                   u.full_name AS requester_name, u.role AS requester_role,
                   a.full_name AS assignee_name,
                   (t.admin_last_read_at IS NULL OR t.admin_last_read_at < t.last_user_activity_at) AS unread,
                   lm.body AS last_body, lm.author_kind AS last_author_kind, lm.created_at AS last_message_at,
                   (SELECT COUNT(*) FROM support_ticket_attachments x WHERE x.ticket_id = t.id) AS attachment_count,
                   (SELECT COUNT(*) FROM support_ticket_messages x
                    WHERE x.ticket_id = t.id AND x.author_kind <> 'system') AS message_count,
                   COUNT(*) OVER () AS total
            FROM support_tickets t
            LEFT JOIN users u ON u.id = t.created_by
            LEFT JOIN users a ON a.id = t.assigned_to
            {_LAST_PUBLIC}
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT %(limit)s OFFSET %(offset)s
        """
        rows = self._fetch_all(query, params)
        total = int(rows[0]['total']) if rows else 0
        if not rows and offset:
            total = self._count(where_sql, params)
        return {'rows': rows, 'total': total}

    def _count(self, where_sql: str, params: Dict[str, Any]) -> int:
        query = f"""
            SELECT COUNT(*) AS n FROM support_tickets t
            LEFT JOIN users u ON u.id = t.created_by
            WHERE {where_sql}
        """
        row = self._fetch_one(query, params)
        return int(row['n']) if row else 0

    def admin_view_counts(self, me: int) -> Dict[str, int]:
        selects = ', '.join(
            f"COUNT(*) FILTER (WHERE {cond}) AS {name}" for name, cond in ADMIN_VIEWS.items())
        row = self._fetch_one(f'SELECT {selects} FROM support_tickets t', {'me': me})
        return {name: int(row[name]) for name in ADMIN_VIEWS} if row else {name: 0 for name in ADMIN_VIEWS}

    def admin_stats(self) -> Any:
        """Headline numbers for the dashboard strip (last 30 days + now)."""
        query = f"""
            SELECT
              COUNT(*) FILTER (WHERE status <> 'closed') AS open_count,
              COUNT(*) FILTER (WHERE created_at > {_UTC_NOW} - INTERVAL '30 days') AS created_30d,
              COUNT(*) FILTER (WHERE closed_at > {_UTC_NOW} - INTERVAL '30 days') AS closed_30d,
              EXTRACT(EPOCH FROM AVG(first_response_at - created_at)
                      FILTER (WHERE created_at > {_UTC_NOW} - INTERVAL '30 days')) AS avg_first_response_s,
              EXTRACT(EPOCH FROM AVG(COALESCE(resolved_at, closed_at) - created_at)
                      FILTER (WHERE COALESCE(resolved_at, closed_at) IS NOT NULL
                              AND created_at > {_UTC_NOW} - INTERVAL '30 days')) AS avg_resolution_s
            FROM support_tickets
        """
        return self._fetch_one(query)

    def requester_history(self, user_id: int, exclude_id: int) -> List[Any]:
        query = """
            SELECT id, title, status, kind, created_at
            FROM support_tickets
            WHERE created_by = %s AND id <> %s
            ORDER BY created_at DESC
            LIMIT 10
        """
        return self._fetch_all(query, (user_id, exclude_id))

    def list_agents(self) -> List[Any]:
        """Users whose role has the 'support_tickets' module — the assignee picker."""
        query = """
            SELECT u.id, u.full_name, u.email
            FROM users u
            JOIN roles r ON r.name = u.role
            JOIN role_permissions rp ON rp.role_id = r.id AND rp.module_name = 'support_tickets'
            WHERE rp.has_access = TRUE AND u.is_active = TRUE
            ORDER BY u.full_name
        """
        return self._fetch_all(query)
