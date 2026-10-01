"""Visit notes ("Uwagi i zalecenia z wizyt") — the access rule and the use-cases.

ONE rule, derived from the caller's ``appointments`` permission flags and nothing
else (superuser is an ordinary role here — principal, 2026-10-01):

  * access OFF   -> nothing
  * read_only ON -> view only; every write is refused
  * own_data ON  -> only visits of the caller's linked employee, for view AND
                    write (no linked employee -> nothing)
  * own_data OFF -> every visit

On top of that sits the app-wide admin-view invariant (config.admin_view): the
owner-employee's visits stay hidden from everyone but superusers. It is AND-ed in,
so it can only ever narrow access — reads get it from the repository's SQL scope,
single-note writes get it from ``is_employee_hidden`` here.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config.admin_view import is_employee_hidden
from config.auth_config import get_permission_flags, own_data_employee_id
from exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.visit_note_repository import VisitNoteRepository
from utils.timezone import to_local

MODULE = 'appointments'
MAX_NOTE_LENGTH = 2000
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
ELIGIBLE_VISITS_LIMIT = 50


@dataclass(frozen=True)
class VisitNoteScope:
    """What the caller may do with visit notes."""
    has_access: bool
    read_only: bool
    # None = every visit. Otherwise the only employee whose visits are in scope;
    # -1 is own-data without a linked employee, an id nobody has.
    own_employee_id: Optional[int]

    @property
    def can_write(self) -> bool:
        return bool(self.has_access and not self.read_only)

    def covers(self, employee_id: int) -> bool:
        """True when a visit assigned to ``employee_id`` is inside the caller's scope."""
        return bool(self.has_access and (self.own_employee_id is None
                                         or employee_id == self.own_employee_id))


def visit_note_scope(user) -> VisitNoteScope:
    """Resolve the caller's note scope from their ``appointments`` flags."""
    flags = get_permission_flags(user.role, MODULE)
    return VisitNoteScope(
        has_access=flags['has_access'],
        read_only=flags['read_only'],
        own_employee_id=own_data_employee_id(user, MODULE),
    )


def clean_note_text(raw: Any) -> str:
    """Trim and validate note text; raises ValidationError (400) when unusable."""
    if not isinstance(raw, str):
        raise ValidationError('Treść uwagi jest wymagana')
    text = raw.strip()
    if not text:
        raise ValidationError('Treść uwagi nie może być pusta')
    if '\x00' in text:  # Postgres text cannot hold NUL; psycopg2 would raise a 500
        raise ValidationError('Treść uwagi zawiera niedozwolone znaki')
    if len(text) > MAX_NOTE_LENGTH:
        raise ValidationError(f'Treść uwagi może mieć maksymalnie {MAX_NOTE_LENGTH} znaków')
    return text


def iso_local(dt) -> Optional[str]:
    """Naive-UTC column value -> Warsaw-local ISO string (no designator)."""
    return to_local(dt).isoformat(timespec='seconds') if dt else None


class VisitNoteService:
    """Use-cases over visit notes; every rule above is enforced here, not in routes."""

    def __init__(self, notes: Optional[VisitNoteRepository] = None,
                 appointments: Optional[AppointmentRepository] = None):
        self.notes = notes or VisitNoteRepository()
        self.appointments = appointments or AppointmentRepository()

    # ── reads ────────────────────────────────────────────────────────────────

    def list_for_client(self, client_id: int, scope: VisitNoteScope, limit: int,
                        offset: int, appointment_id: Optional[int] = None) -> Dict[str, Any]:
        """One page of a client's notes plus paging flags and whether adding is possible."""
        rows = self.notes.list_for_client(client_id, scope.own_employee_id, limit, offset)
        total = self.notes.count_for_client(client_id, scope.own_employee_id)
        return {
            'notes': [self._serialize(row, scope) for row in rows],
            'total': total,
            'has_more': offset + len(rows) < total,
            'can_add': self._can_add(client_id, scope, appointment_id),
        }

    def eligible_visits(self, client_id: int, scope: VisitNoteScope) -> List[Dict[str, Any]]:
        """Completed visits (in scope) a note can be attached to — the client-page picker."""
        rows = self.notes.eligible_visits(client_id, scope.own_employee_id, ELIGIBLE_VISITS_LIMIT)
        return [{
            'appointment_id': r['appointment_id'],
            'appointment_date': r['appointment_date'].isoformat(),
            'service_name': r['service_name'],
            'employee_name': r['employee_name'],
        } for r in rows]

    def recent_by_client(self, client_ids: List[int], scope: VisitNoteScope,
                         per_client: int) -> Dict[int, List[Dict[str, Optional[str]]]]:
        """``{client_id: [{text, at}, ...]}`` newest first, at most ``per_client`` each."""
        if not scope.has_access or not client_ids:
            return {}
        grouped: Dict[int, List[Dict[str, Optional[str]]]] = {}
        for row in self.notes.recent_for_clients(list(client_ids), scope.own_employee_id, per_client):
            grouped.setdefault(row['client_id'], []).append(
                {'text': row['note_text'], 'at': iso_local(row['updated_at'])})
        return grouped

    # ── writes ───────────────────────────────────────────────────────────────

    def create(self, appointment_id: int, raw_text: Any, scope: VisitNoteScope, user) -> Dict[str, Any]:
        """Attach a note to a COMPLETED visit inside the caller's scope."""
        self._require_write(scope)
        text = clean_note_text(raw_text)
        visit = self.appointments.get_by_id(appointment_id)
        if not visit:
            raise NotFoundError('Wizyta nie istnieje')
        self._guard_employee(visit['employee_id'], scope)
        if visit['status'] != 'completed':
            raise ConflictError('Uwagę można dodać tylko do zakończonej wizyty')
        note_id = self.notes.create(appointment_id, text, user.id)
        return {'id': note_id, 'client_id': visit['client_id'], 'text': text}

    def update(self, note_id: int, raw_text: Any, scope: VisitNoteScope, user) -> Dict[str, Any]:
        """Edit a note's text. Returns the note as it was (for the audit trail) + the new text."""
        self._require_write(scope)
        text = clean_note_text(raw_text)
        note = self._writable_note(note_id, scope)
        if not self.notes.update_text(note_id, text, user.id):
            raise NotFoundError('Uwaga nie istnieje')
        return {'note': note, 'text': text}

    def delete(self, note_id: int, scope: VisitNoteScope, user) -> Dict[str, Any]:
        """Soft-delete a note. Returns it as it was (for the audit trail)."""
        self._require_write(scope)
        note = self._writable_note(note_id, scope)
        if not self.notes.soft_delete(note_id, user.id):
            raise NotFoundError('Uwaga nie istnieje')
        return note

    # ── internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _require_write(scope: VisitNoteScope) -> None:
        if not scope.has_access:
            raise PermissionDeniedError('Brak dostępu do wizyt')
        if not scope.can_write:
            raise PermissionDeniedError('Tryb tylko do odczytu — nie można zmieniać uwag')

    @staticmethod
    def _guard_employee(employee_id: int, scope: VisitNoteScope) -> None:
        """404 for the hidden owner-employee (as if it didn't exist), 403 outside own-data scope."""
        if is_employee_hidden(employee_id):
            raise NotFoundError('Wizyta nie istnieje')
        if not scope.covers(employee_id):
            raise PermissionDeniedError('Brak dostępu do uwag tej wizyty')

    def _writable_note(self, note_id: int, scope: VisitNoteScope) -> Dict[str, Any]:
        note = self.notes.get_with_visit(note_id)
        if not note:
            raise NotFoundError('Uwaga nie istnieje')
        self._guard_employee(note['employee_id'], scope)
        return dict(note)

    def _can_add(self, client_id: int, scope: VisitNoteScope, appointment_id: Optional[int]) -> bool:
        """Whether the add-note button should show: writable, and a completed visit in scope.

        With ``appointment_id`` (visit page) that very visit must qualify; without
        it (client page) any eligible visit of the client will do.
        """
        if not scope.can_write:
            return False
        if appointment_id is not None:
            visit = self.appointments.get_by_id(appointment_id)
            return bool(
                visit
                and visit['client_id'] == client_id
                and visit['status'] == 'completed'
                and scope.covers(visit['employee_id'])
                and not is_employee_hidden(visit['employee_id'])
            )
        return bool(self.notes.eligible_visits(client_id, scope.own_employee_id, 1))

    @staticmethod
    def _serialize(row: Any, scope: VisitNoteScope) -> Dict[str, Any]:
        """Row -> API shape. created_on / created_by are stored but never sent."""
        return {
            'id': row['id'],
            'appointment_id': row['appointment_id'],
            'appointment_date': row['appointment_date'].isoformat(),
            'client_name': row['client_name'],
            'service_name': row['service_name'],
            'note_text': row['note_text'],
            'updated_at': iso_local(row['updated_at']),
            'updated_by_name': row['updated_by_name'],
            'can_edit': bool(scope.can_write and scope.covers(row['employee_id'])),
        }
