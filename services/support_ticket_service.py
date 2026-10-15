"""Support tickets — every rule in one place (plans/261013-support-tickets/plan.md §5).

Two sides, one conversation:

  * the AUTHOR (any logged-in user) files a ticket from the phone button's pop-out,
    reads the public part of their own tickets, replies, confirms a fix;
  * an AGENT (role with the 'support_tickets' module, the issues.my-way-solutions.com
    app) sees every ticket with its technical context, replies publicly or with an
    internal note, and moves the ticket through its lifecycle.

Lifecycle::

    new ─(agent opens)→ seen ─(agent replies / takes it)→ in_progress
    in_progress ─(agent asks)→ waiting_user ─(author replies)→ in_progress
    any open ─(agent)→ resolved ─(author: "Działa")→ closed[confirmed]
    resolved/waiting_user ─(author replies)→ in_progress
    closed ─(author replies ≤ REOPEN_DAYS)→ in_progress        (later: "napisz nową")
    any ─(agent)→ closed[done|declined|duplicate]

Every status/priority/assignee change writes a 'system' message, so both sides
see the same history.
"""
import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from repositories.support.support_ticket_repository import ADMIN_SORTS, ADMIN_VIEWS, SupportTicketRepository

logger = logging.getLogger(__name__)

MODULE = 'support_tickets'

KINDS = ('problem', 'idea')
STATUSES = ('new', 'seen', 'in_progress', 'waiting_user', 'resolved', 'closed')
PRIORITIES = ('low', 'normal', 'high', 'urgent')
CLOSE_REASONS = ('done', 'confirmed', 'declined', 'duplicate')

MIN_TEXT = 10
MAX_TEXT = 5000
MAX_AREA_LEN = 40
MAX_AREA_LABEL_LEN = 80
MAX_FILES_PER_MESSAGE = 3
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_CONTEXT_BYTES = 400 * 1024
MAX_TICKETS_PER_HOUR = 10
REOPEN_DAYS = 14

_IMAGE_FORMATS = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}
_EXT = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}
_AREA_RE = re.compile(r'^[a-z0-9-]{1,40}$')


# ── helpers ──────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    """Naive UTC, the same frame as the DB's naive-UTC columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> Optional[str]:
    """Naive-UTC DB timestamp → ISO 8601 with 'Z', so the browser formats local time."""
    if value is None:
        return None
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.isoformat() + 'Z'
    return value.isoformat()


def _clean_text(value) -> str:
    text = value if isinstance(value, str) else ''
    # Normalise newlines, drop NULs and other control chars except \n and \t.
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = ''.join(ch for ch in text if ch in '\n\t' or ord(ch) >= 32)
    return text.strip()


def _title_from(body: str, fallback: str) -> str:
    """First sentence/line of the first message, ≤ 120 chars."""
    first = re.split(r'(?<=[.!?])\s|\n', body.strip(), maxsplit=1)[0].strip() if body.strip() else ''
    title = first or fallback
    return title if len(title) <= 120 else title[:117].rstrip() + '…'


def _app_commit() -> Optional[str]:
    """Short git SHA of the running backend checkout (best effort, no subprocess)."""
    try:
        git = Path(__file__).resolve().parents[1] / '.git'
        head = (git / 'HEAD').read_text().strip()
        if head.startswith('ref: '):
            ref = head[5:]
            ref_file = git / ref
            if ref_file.exists():
                return ref_file.read_text().strip()[:10]
            packed = (git / 'packed-refs')
            if packed.exists():
                for line in packed.read_text().splitlines():
                    if line.endswith(' ' + ref):
                        return line.split(' ', 1)[0][:10]
            return None
        return head[:10]
    except Exception:
        return None


def read_images(files: Iterable) -> List[Dict[str, Any]]:
    """Validate uploaded screenshots (real PNG/JPEG/WebP, ≤ 4 MB, ≤ 3) → attachment dicts.

    The declared Content-Type is ignored: Pillow decodes the bytes and the format it
    finds is what gets stored and later served — a renamed HTML file never passes."""
    from PIL import Image

    out: List[Dict[str, Any]] = []
    for storage in files:
        if storage is None:
            continue
        data = storage.read()
        if not data:
            continue
        if len(out) >= MAX_FILES_PER_MESSAGE:
            raise ValidationError(f'Maksymalnie {MAX_FILES_PER_MESSAGE} zdjęcia w jednej wiadomości')
        if len(data) > MAX_FILE_BYTES:
            raise ValidationError('Zdjęcie jest za duże (maks. 4 MB)')
        try:
            with Image.open(io.BytesIO(data)) as img:
                fmt = img.format
                width, height = img.size
                img.verify()
        except Exception:
            raise ValidationError('Załącznik nie jest obrazem (PNG, JPG lub WebP)')
        mime = _IMAGE_FORMATS.get(fmt or '')
        if not mime:
            raise ValidationError('Dozwolone są tylko obrazy PNG, JPG lub WebP')
        stem = re.sub(r'[^A-Za-z0-9._-]+', '-', Path(storage.filename or 'zdjecie').stem)[:60] or 'zdjecie'
        out.append({'filename': f'{stem}.{_EXT[mime]}', 'mime': mime, 'data': data,
                    'width': width, 'height': height})
    return out


def parse_context(raw) -> Dict[str, Any]:
    """The browser's technical snapshot: a JSON object, capped in size.

    Over the cap, the bulkiest parts (page text, storage dump, API log) are dropped
    one by one rather than refusing the whole ticket."""
    if not raw:
        return {}
    try:
        ctx = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {'_error': 'context was not valid JSON'}
    if not isinstance(ctx, dict):
        return {'_error': 'context was not an object'}
    for heavy in (('page', 'text'), ('storage',), ('network',), ('console',)):
        if len(json.dumps(ctx, default=str)) <= MAX_CONTEXT_BYTES:
            break
        node = ctx
        for key in heavy[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict) and heavy[-1] in node:
            node[heavy[-1]] = '[usunięte — przekroczony limit rozmiaru]'
    if len(json.dumps(ctx, default=str)) > MAX_CONTEXT_BYTES:
        return {'_error': 'context too large', 'keys': sorted(ctx.keys())[:50]}
    return ctx


# ── serialisers ──────────────────────────────────────────────────────────────

def _message_out(row, attachments_by_message: Dict[int, list]) -> Dict[str, Any]:
    return {
        'id': row['id'],
        'author_kind': row['author_kind'],
        'author_name': row['author_name'],
        'body': row['body'],
        'is_internal': bool(row['is_internal']),
        'event': row['event'],
        'meta': row['meta'],
        'created_at': _iso(row['created_at']),
        'attachments': attachments_by_message.get(row['id'], []),
    }


def _attachment_out(row) -> Dict[str, Any]:
    return {
        'id': row['id'], 'filename': row['filename'], 'mime': row['mime'],
        'size_bytes': row['size_bytes'], 'width': row['width'], 'height': row['height'],
        'url': f"/api/support/attachments/{row['id']}",
    }


def _ticket_base(row) -> Dict[str, Any]:
    return {
        'id': row['id'], 'kind': row['kind'], 'area': row.get('area'), 'area_label': row['area_label'],
        'title': row['title'], 'status': row['status'], 'close_reason': row['close_reason'],
        'created_at': _iso(row['created_at']), 'updated_at': _iso(row['updated_at']),
        'closed_at': _iso(row.get('closed_at')),
    }


class SupportTicketService:
    def __init__(self, repo: Optional[SupportTicketRepository] = None):
        self.repo = repo or SupportTicketRepository()

    # ── author side ─────────────────────────────────────────────────────────

    def create(self, user, form: Dict[str, Any], files: Iterable, server_context: Dict[str, Any]) -> Dict[str, Any]:
        kind = (form.get('kind') or '').strip()
        if kind not in KINDS:
            raise ValidationError('Nieznany rodzaj zgłoszenia')
        area = (form.get('area') or '').strip()
        if not _AREA_RE.match(area):
            raise ValidationError('Wybierz temat zgłoszenia')
        area_label = _clean_text(form.get('area_label'))[:MAX_AREA_LABEL_LEN] or area
        body = _clean_text(form.get('body'))
        if len(body) > MAX_TEXT:
            raise ValidationError(f'Wiadomość jest za długa (maks. {MAX_TEXT} znaków)')
        images = read_images(files)
        if len(body) < MIN_TEXT and not images:
            raise ValidationError('Napisz chociaż jedno zdanie albo zaznacz miejsce na ekranie')
        if self.repo.count_recent_by_user(user.id, 60) >= MAX_TICKETS_PER_HOUR:
            raise ConflictError('Wysłano już dużo zgłoszeń w ciągu godziny — spróbuj za chwilę', status_code=429)

        context = parse_context(form.get('context'))
        context['server'] = {**server_context, 'app_commit': _app_commit()}
        ticket_id = self.repo.create_ticket(
            user_id=user.id, kind=kind, area=area, area_label=area_label,
            title=_title_from(body, area_label), priority='normal' if kind == 'problem' else 'low',
            context=context, body=body, attachments=images,
        )
        return {'id': ticket_id}

    def _own_ticket(self, user, ticket_id: int):
        ticket = self.repo.get_ticket(ticket_id)
        # Someone else's ticket answers exactly like a missing one — ids are not secrets
        # worth confirming.
        if not ticket or ticket['created_by'] != user.id:
            raise NotFoundError('Nie znaleziono rozmowy')
        return ticket

    def list_mine(self, user) -> Dict[str, Any]:
        rows = self.repo.list_for_user(user.id)
        tickets = []
        for r in rows:
            item = _ticket_base(r)
            item.update({
                'unread': bool(r['unread']),
                'last_body': (r['last_body'] or '')[:160],
                'last_author_kind': r['last_author_kind'],
                'last_message_at': _iso(r['last_message_at']),
            })
            tickets.append(item)
        return {'tickets': tickets, 'unread': sum(1 for t in tickets if t['unread'])}

    def unread_count(self, user) -> int:
        return self.repo.unread_for_user(user.id)

    def get_mine(self, user, ticket_id: int) -> Dict[str, Any]:
        ticket = self._own_ticket(user, ticket_id)
        self.repo.mark_read(ticket_id, 'user')
        return self._thread(ticket, include_internal=False)

    def reply_as_author(self, user, ticket_id: int, form: Dict[str, Any], files: Iterable) -> Dict[str, Any]:
        ticket = self._own_ticket(user, ticket_id)
        body = _clean_text(form.get('body'))
        if len(body) > MAX_TEXT:
            raise ValidationError(f'Wiadomość jest za długa (maks. {MAX_TEXT} znaków)')
        images = read_images(files)
        if not body and not images:
            raise ValidationError('Napisz wiadomość')

        updates: Dict[str, Any] = {'last_user_activity_at': 'NOW', 'user_last_read_at': 'NOW'}
        events: List[dict] = []
        status = ticket['status']
        if status == 'closed':
            closed_at = ticket['closed_at']
            if closed_at and _utcnow() - closed_at > timedelta(days=REOPEN_DAYS):
                raise ConflictError('Ta rozmowa jest zamknięta — napisz nową wiadomość')
        if status in ('waiting_user', 'resolved', 'closed'):
            updates.update({'status': 'in_progress', 'close_reason': None, 'closed_at': None, 'resolved_at': None})
            events.append({'author_id': user.id, 'event': 'status',
                           'meta': {'from': status, 'to': 'in_progress', 'by': 'user'}})
        message_id = self.repo.add_message(ticket_id, author_id=user.id, author_kind='user', body=body,
                                           attachments=images, ticket_updates=updates, events=events)
        return {'id': message_id}

    def confirm_fixed(self, user, ticket_id: int) -> None:
        """'Działa ✅' on a resolved ticket closes it."""
        ticket = self._own_ticket(user, ticket_id)
        if ticket['status'] != 'resolved':
            raise ConflictError('Tę rozmowę można potwierdzić dopiero, gdy jest oznaczona jako gotowa')
        self.repo.apply_changes(
            ticket_id,
            {'status': 'closed', 'close_reason': 'confirmed', 'closed_at': 'NOW',
             'last_user_activity_at': 'NOW', 'user_last_read_at': 'NOW'},
            [{'author_id': user.id, 'event': 'status',
              'meta': {'from': 'resolved', 'to': 'closed', 'reason': 'confirmed', 'by': 'user'}}],
        )

    # ── shared ──────────────────────────────────────────────────────────────

    def _thread(self, ticket, include_internal: bool) -> Dict[str, Any]:
        attachments = [a for a in self.repo.list_attachments(ticket['id'])]
        messages = self.repo.list_messages(ticket['id'], include_internal)
        visible_ids = {m['id'] for m in messages}
        by_message: Dict[int, list] = {}
        for a in attachments:
            if a['message_id'] in visible_ids:
                by_message.setdefault(a['message_id'], []).append(_attachment_out(a))
        out = _ticket_base(ticket)
        out['messages'] = [_message_out(m, by_message) for m in messages]
        out['can_reply'] = not (
            ticket['status'] == 'closed' and ticket['closed_at']
            and _utcnow() - ticket['closed_at'] > timedelta(days=REOPEN_DAYS))
        return out

    def attachment_for(self, user, attachment_id: int, is_agent: bool):
        att = self.repo.get_attachment(attachment_id)
        if not att:
            raise NotFoundError('Nie znaleziono załącznika')
        if is_agent:
            return att
        if att['created_by'] != user.id or att['is_internal']:
            raise NotFoundError('Nie znaleziono załącznika')
        return att

    # ── agent side ──────────────────────────────────────────────────────────

    def admin_list(self, user, args: Dict[str, Any]) -> Dict[str, Any]:
        view = args.get('view') if args.get('view') in ADMIN_VIEWS else 'open'
        sort = args.get('sort') if args.get('sort') in ADMIN_SORTS else 'updated'
        kind = args.get('kind') if args.get('kind') in KINDS else None
        priority = args.get('priority') if args.get('priority') in PRIORITIES else None
        area = args.get('area') if _AREA_RE.match(args.get('area') or '') else None
        q = (args.get('q') or '').strip()[:100] or None
        limit = max(1, min(int(args.get('limit') or 50), 200))
        offset = max(0, min(int(args.get('offset') or 0), 100_000))
        data = self.repo.admin_list(view=view, me=user.id, kind=kind, area=area, priority=priority,
                                    q=q, sort=sort, limit=limit, offset=offset)
        tickets = []
        for r in data['rows']:
            item = _ticket_base(r)
            item.update({
                'priority': r['priority'],
                'requester_name': r['requester_name'], 'requester_role': r['requester_role'],
                'assigned_to': r['assigned_to'], 'assignee_name': r['assignee_name'],
                'unread': bool(r['unread']),
                'last_body': (r['last_body'] or '')[:200],
                'last_author_kind': r['last_author_kind'],
                'last_message_at': _iso(r['last_message_at']),
                'last_user_activity_at': _iso(r['last_user_activity_at']),
                'first_response_at': _iso(r['first_response_at']),
                'attachment_count': int(r['attachment_count']),
                'message_count': int(r['message_count']),
            })
            tickets.append(item)
        return {'tickets': tickets, 'total': data['total'], 'limit': limit, 'offset': offset,
                'counts': self.repo.admin_view_counts(user.id)}

    def admin_overview(self, user) -> Dict[str, Any]:
        stats = self.repo.admin_stats() or {}
        return {
            'counts': self.repo.admin_view_counts(user.id),
            'stats': {
                'open': int(stats.get('open_count') or 0),
                'created_30d': int(stats.get('created_30d') or 0),
                'closed_30d': int(stats.get('closed_30d') or 0),
                'avg_first_response_s': float(stats['avg_first_response_s']) if stats.get('avg_first_response_s') is not None else None,
                'avg_resolution_s': float(stats['avg_resolution_s']) if stats.get('avg_resolution_s') is not None else None,
            },
            'agents': [dict(a) for a in self.repo.list_agents()],
        }

    def _ticket_or_404(self, ticket_id: int, with_context: bool = False):
        ticket = self.repo.get_ticket(ticket_id, with_context=with_context)
        if not ticket:
            raise NotFoundError('Nie znaleziono zgłoszenia')
        return ticket

    def admin_get(self, user, ticket_id: int) -> Dict[str, Any]:
        ticket = self._ticket_or_404(ticket_id, with_context=True)
        if ticket['status'] == 'new':
            # First agent look: 'Przeczytane' for the author.
            self.repo.apply_changes(
                ticket_id, {'status': 'seen', 'last_admin_activity_at': 'NOW'},
                [{'author_id': user.id, 'event': 'status', 'meta': {'from': 'new', 'to': 'seen', 'by': 'admin'}}])
            ticket = self._ticket_or_404(ticket_id, with_context=True)
        self.repo.mark_read(ticket_id, 'admin')
        out = self._thread(ticket, include_internal=True)
        out.update({
            'priority': ticket['priority'],
            'assigned_to': ticket['assigned_to'], 'assignee_name': ticket['assignee_name'],
            'context': ticket['context'],
            'requester': {
                'id': ticket['created_by'], 'name': ticket['requester_name'],
                'email': ticket['requester_email'], 'role': ticket['requester_role'],
                'role_label': ticket['requester_role_label'],
            },
            'first_response_at': _iso(ticket['first_response_at']),
            'resolved_at': _iso(ticket['resolved_at']),
            'last_user_activity_at': _iso(ticket['last_user_activity_at']),
            'last_admin_activity_at': _iso(ticket['last_admin_activity_at']),
            'requester_history': [
                {**dict(h), 'created_at': _iso(h['created_at'])}
                for h in (self.repo.requester_history(ticket['created_by'], ticket_id)
                          if ticket['created_by'] else [])
            ],
        })
        return out

    def _status_changes(self, user, ticket, new_status: str, close_reason: Optional[str]):
        """Ticket updates + system event for an agent-driven status change."""
        if new_status not in STATUSES or new_status == 'new':
            raise ValidationError('Nieprawidłowy status')
        old = ticket['status']
        if new_status == old and not (new_status == 'closed' and close_reason and close_reason != ticket['close_reason']):
            return {}, []
        updates: Dict[str, Any] = {'status': new_status, 'last_admin_activity_at': 'NOW'}
        meta: Dict[str, Any] = {'from': old, 'to': new_status, 'by': 'admin'}
        if new_status == 'closed':
            reason = close_reason if close_reason in CLOSE_REASONS and close_reason != 'confirmed' else 'done'
            updates.update({'close_reason': reason, 'closed_at': 'NOW'})
            meta['reason'] = reason
        else:
            updates.update({'close_reason': None, 'closed_at': None})
        if new_status == 'resolved':
            updates['resolved_at'] = 'NOW'
        elif old == 'resolved' and new_status != 'closed':
            updates['resolved_at'] = None
        return updates, [{'author_id': user.id, 'event': 'status', 'meta': meta}]

    def admin_reply(self, user, ticket_id: int, form: Dict[str, Any], files: Iterable) -> Dict[str, Any]:
        ticket = self._ticket_or_404(ticket_id)
        body = _clean_text(form.get('body'))
        if len(body) > MAX_TEXT:
            raise ValidationError(f'Wiadomość jest za długa (maks. {MAX_TEXT} znaków)')
        is_internal = str(form.get('is_internal', '')).lower() in ('1', 'true', 'on')
        images = read_images(files)
        if not body and not images:
            raise ValidationError('Napisz wiadomość')

        updates: Dict[str, Any] = {'admin_last_read_at': 'NOW'}
        events: List[dict] = []
        if not is_internal:
            updates['last_admin_activity_at'] = 'NOW'
            if not ticket['first_response_at']:
                updates['first_response_at'] = 'NOW'
            # "Wyślij jako …" — Zendesk-style submit-as; default: a first reply takes the ticket.
            target = form.get('status') or ''
            if not target:
                target = 'in_progress' if ticket['status'] in ('new', 'seen') else ''
            if target:
                status_updates, events = self._status_changes(user, ticket, target, form.get('close_reason'))
                updates.update(status_updates)
        elif form.get('status'):
            raise ValidationError('Notatka wewnętrzna nie zmienia statusu')
        message_id = self.repo.add_message(ticket_id, author_id=user.id, author_kind='admin', body=body,
                                           is_internal=is_internal, attachments=images,
                                           ticket_updates=updates, events=events)
        return {'id': message_id}

    def admin_update(self, user, ticket_id: int, data: Dict[str, Any]) -> None:
        ticket = self._ticket_or_404(ticket_id)
        updates: Dict[str, Any] = {}
        events: List[dict] = []
        if 'status' in data:
            st_updates, st_events = self._status_changes(user, ticket, data.get('status'), data.get('close_reason'))
            updates.update(st_updates)
            events += st_events
        if 'priority' in data:
            priority = data.get('priority')
            if priority not in PRIORITIES:
                raise ValidationError('Nieprawidłowy priorytet')
            if priority != ticket['priority']:
                updates['priority'] = priority
                events.append({'author_id': user.id, 'event': 'priority',
                               'meta': {'from': ticket['priority'], 'to': priority}})
        if 'assigned_to' in data:
            assignee = data.get('assigned_to')
            if assignee in ('', None):
                assignee = None
            else:
                if isinstance(assignee, bool) or not str(assignee).isdigit():
                    raise ValidationError('Nieprawidłowa osoba')
                assignee = int(assignee)
                agents = {a['id']: a['full_name'] for a in self.repo.list_agents()}
                if assignee not in agents:
                    raise ValidationError('Ta osoba nie ma dostępu do panelu zgłoszeń')
            if assignee != ticket['assigned_to']:
                updates['assigned_to'] = assignee
                events.append({'author_id': user.id, 'event': 'assigned', 'meta': {'to': assignee}})
        if not updates:
            return
        # Priority / assignee are agent bookkeeping, invisible to the author: only a
        # status change counts as news for them.
        self.repo.apply_changes(ticket_id, updates, events)


def is_agent(user) -> bool:
    from config.auth_config import get_permission_flags
    try:
        return bool(get_permission_flags(user.role, MODULE)['has_access'])
    except Exception:
        logger.exception('support: permission lookup failed')
        return False


def can_agent_write(user) -> bool:
    from config.auth_config import get_permission_flags
    flags = get_permission_flags(user.role, MODULE)
    return bool(flags['has_access'] and not flags['read_only'])


__all__ = ['SupportTicketService', 'is_agent', 'can_agent_write', 'PermissionDeniedError']
