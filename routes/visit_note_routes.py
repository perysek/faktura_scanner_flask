"""
API routes for visit notes ("Uwagi i zalecenia z wizyt").

Deliberately NOT under /api/appointments: the SPA's API client fires the
"appointments changed" event (calendar + income refetch) for any write below
that prefix, and a note changes neither.

Every route needs `appointments` access. `module_permission_required` also turns
read_only into "GET only"; the own-data / hidden-owner / completed-visit rules
live in services.visit_note_service so they are enforced in exactly one place.
"""
import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from config.auth_config import module_permission_required
from exceptions import AppError, NotFoundError, ValidationError
from services.visit_note_service import (
    DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, VisitNoteService, visit_note_scope,
)
from utils.audit import audit_event

visit_note_bp = Blueprint('visit_notes', __name__)


# Postgres rejects an OFFSET beyond bigint with a 500; nobody pages 100k notes deep.
MAX_OFFSET = 100_000


def _page_args():
    """(limit, offset) from the query string, clamped to sane bounds."""
    limit = request.args.get('limit', type=int)
    if limit is None or limit < 1:
        limit = DEFAULT_PAGE_SIZE
    offset = request.args.get('offset', type=int)
    if offset is None or offset < 0:
        offset = 0
    return min(limit, MAX_PAGE_SIZE), min(offset, MAX_OFFSET)


def _json_body() -> dict:
    """The request's JSON object, or {} for a missing/non-object body (list, string, null)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _as_id(value):
    """A positive integer id from JSON, or None.

    Strict on purpose: `int(True)` is 1 and `int(5.9)` is 5, so a bool or float
    would silently address visit 1 / visit 5; `int(float('inf'))` raises
    OverflowError. Only a real int or a string of digits is an id."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip()) or None
    return None


def _length(text) -> str:
    """Audit value for a note's text: its length. The text itself must NEVER reach
    audit_log — GET /api/history is open to every logged-in user (no module check,
    no own-data or hidden-owner scope), so anything stored there is readable by all."""
    return str(len(text or ''))


def _client_label(client_id):
    row = current_app.client_repo.get_by_id(client_id)
    name = f"{row['first_name']} {row['last_name']}".strip() if row else ''
    return name or f'Klient #{client_id}'


@visit_note_bp.route('/clients/<int:client_id>/visit-notes', methods=['GET'])
@login_required
@module_permission_required('appointments')
def list_visit_notes(client_id):
    """A client's notes across all their visits, newest edit first, paged."""
    try:
        if not current_app.client_repo.get_by_id(client_id):
            raise NotFoundError('Klient nie istnieje')
        limit, offset = _page_args()
        data = VisitNoteService().list_for_client(
            client_id, visit_note_scope(current_user), limit, offset,
            appointment_id=request.args.get('appointment_id', type=int))
        return jsonify({'success': True, **data})
    except AppError:
        raise
    except Exception:
        logging.exception('Unexpected error in list_visit_notes')
        raise AppError('Wystapil blad serwera')


@visit_note_bp.route('/clients/<int:client_id>/visit-notes/visits', methods=['GET'])
@login_required
@module_permission_required('appointments')
def list_noteable_visits(client_id):
    """Completed visits of the client a note can be attached to (client-page picker)."""
    try:
        visits = VisitNoteService().eligible_visits(client_id, visit_note_scope(current_user))
        return jsonify({'success': True, 'visits': visits})
    except AppError:
        raise
    except Exception:
        logging.exception('Unexpected error in list_noteable_visits')
        raise AppError('Wystapil blad serwera')


@visit_note_bp.route('/visit-notes', methods=['POST'])
@login_required
@module_permission_required('appointments')
def create_visit_note():
    """Attach a note to a completed visit."""
    try:
        data = _json_body()
        appointment_id = _as_id(data.get('appointment_id'))
        if appointment_id is None:
            raise ValidationError('Brak appointment_id')

        created = VisitNoteService().create(
            appointment_id, data.get('note_text'), visit_note_scope(current_user), current_user)
        audit_event('visit_note', 'CREATE', entity_id=created['id'],
                    entity_label=_client_label(created['client_id']),
                    field_name='note_length', new_value=_length(created['text']))
        return jsonify({'success': True, 'id': created['id']}), 201
    except AppError:
        raise
    except Exception:
        logging.exception('Unexpected error in create_visit_note')
        raise AppError('Wystapil blad serwera')


@visit_note_bp.route('/visit-notes/<int:note_id>', methods=['PUT'])
@login_required
@module_permission_required('appointments')
def update_visit_note(note_id):
    """Edit a note's text."""
    try:
        data = _json_body()
        result = VisitNoteService().update(
            note_id, data.get('note_text'), visit_note_scope(current_user), current_user)
        note = result['note']
        audit_event('visit_note', 'UPDATE', entity_id=note_id,
                    entity_label=note['client_name'], field_name='note_length',
                    old_value=_length(note['note_text']), new_value=_length(result['text']))
        return jsonify({'success': True})
    except AppError:
        raise
    except Exception:
        logging.exception('Unexpected error in update_visit_note')
        raise AppError('Wystapil blad serwera')


@visit_note_bp.route('/visit-notes/<int:note_id>', methods=['DELETE'])
@login_required
@module_permission_required('appointments')
def delete_visit_note(note_id):
    """Soft-delete a note."""
    try:
        note = VisitNoteService().delete(note_id, visit_note_scope(current_user), current_user)
        audit_event('visit_note', 'DELETE', entity_id=note_id,
                    entity_label=note['client_name'], field_name='note_length',
                    old_value=_length(note['note_text']))
        return jsonify({'success': True})
    except AppError:
        raise
    except Exception:
        logging.exception('Unexpected error in delete_visit_note')
        raise AppError('Wystapil blad serwera')
