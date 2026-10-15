"""
API routes for support tickets ("Zgłoś problem lub podziel się pomysłem").

/api/support/...        the AUTHOR side — any logged-in user, own tickets only
                        (main app: the sidebar phone button's pop-out)
/api/support/admin/...  the AGENT side — the 'support_tickets' module
                        (issues.my-way-solutions.com); read_only blocks writes

All rules live in services.support_ticket_service; routes only parse and answer.
Message bodies are plain text — both frontends render them escaped.
"""
import logging

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from config.auth_config import module_permission_required
from exceptions import AppError, ValidationError
from services.support_ticket_service import SupportTicketService, is_agent
from utils.audit import audit_event
from utils.client_ip import client_ip
from utils.timezone import now_local

support_bp = Blueprint('support', __name__)

AGENT_MODULE = 'support_tickets'


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _server_context() -> dict:
    """What the server knows about the sender — never trusted from the browser."""
    return {
        'received_at_local': now_local().isoformat(timespec='seconds'),
        'ip': client_ip(),
        'user_agent': request.headers.get('User-Agent', '')[:400],
        'host': request.host,
        'user': {
            'id': current_user.id,
            'email': current_user.email,
            'full_name': current_user.full_name,
            'role': current_user.role,
        },
    }


def _guard(fn_name):
    """Uniform 500 for anything unexpected (AppError subclasses pass through)."""
    logging.exception(f'Unexpected error in {fn_name}')
    return AppError('Wystapil blad serwera')


# ── author side ─────────────────────────────────────────────────────────────

@support_bp.route('/tickets', methods=['POST'])
@login_required
def create_ticket():
    """multipart/form-data: kind, area, area_label, body, context (JSON), files[] (≤3 images)."""
    try:
        result = SupportTicketService().create(
            current_user, request.form, request.files.getlist('files'), _server_context())
        audit_event('support_ticket', 'CREATE', entity_id=result['id'],
                    entity_label=f"Zgłoszenie #{result['id']}", field_name='kind',
                    new_value=request.form.get('kind'))
        return jsonify({'success': True, 'id': result['id']}), 201
    except AppError:
        raise
    except Exception:
        raise _guard('create_ticket')


@support_bp.route('/tickets', methods=['GET'])
@login_required
def my_tickets():
    try:
        return jsonify({'success': True, **SupportTicketService().list_mine(current_user)})
    except AppError:
        raise
    except Exception:
        raise _guard('my_tickets')


@support_bp.route('/unread-count', methods=['GET'])
@login_required
def unread_count():
    try:
        return jsonify({'success': True, 'unread': SupportTicketService().unread_count(current_user)})
    except AppError:
        raise
    except Exception:
        raise _guard('unread_count')


@support_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@login_required
def my_ticket(ticket_id):
    try:
        return jsonify({'success': True, 'ticket': SupportTicketService().get_mine(current_user, ticket_id)})
    except AppError:
        raise
    except Exception:
        raise _guard('my_ticket')


@support_bp.route('/tickets/<int:ticket_id>/messages', methods=['POST'])
@login_required
def reply_to_my_ticket(ticket_id):
    try:
        result = SupportTicketService().reply_as_author(
            current_user, ticket_id, request.form, request.files.getlist('files'))
        return jsonify({'success': True, 'id': result['id']}), 201
    except AppError:
        raise
    except Exception:
        raise _guard('reply_to_my_ticket')


@support_bp.route('/tickets/<int:ticket_id>/confirm', methods=['POST'])
@login_required
def confirm_my_ticket(ticket_id):
    try:
        SupportTicketService().confirm_fixed(current_user, ticket_id)
        return jsonify({'success': True})
    except AppError:
        raise
    except Exception:
        raise _guard('confirm_my_ticket')


@support_bp.route('/attachments/<int:attachment_id>', methods=['GET'])
@login_required
def attachment(attachment_id):
    """Screenshot bytes — the author (public messages only) or an agent."""
    try:
        att = SupportTicketService().attachment_for(current_user, attachment_id, is_agent(current_user))
        resp = Response(bytes(att['data']), mimetype=att['mime'])
        resp.headers['Cache-Control'] = 'private, max-age=3600'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['Content-Disposition'] = f'inline; filename="{att["filename"]}"'
        return resp
    except AppError:
        raise
    except Exception:
        raise _guard('attachment')


# ── agent side ──────────────────────────────────────────────────────────────

@support_bp.route('/admin/overview', methods=['GET'])
@login_required
@module_permission_required(AGENT_MODULE)
def admin_overview():
    try:
        return jsonify({'success': True, **SupportTicketService().admin_overview(current_user)})
    except AppError:
        raise
    except Exception:
        raise _guard('admin_overview')


@support_bp.route('/admin/tickets', methods=['GET'])
@login_required
@module_permission_required(AGENT_MODULE)
def admin_tickets():
    try:
        return jsonify({'success': True, **SupportTicketService().admin_list(current_user, request.args)})
    except (TypeError, ValueError):
        raise ValidationError('Nieprawidłowe parametry listy')
    except AppError:
        raise
    except Exception:
        raise _guard('admin_tickets')


@support_bp.route('/admin/tickets/<int:ticket_id>', methods=['GET'])
@login_required
@module_permission_required(AGENT_MODULE)
def admin_ticket(ticket_id):
    try:
        return jsonify({'success': True, 'ticket': SupportTicketService().admin_get(current_user, ticket_id)})
    except AppError:
        raise
    except Exception:
        raise _guard('admin_ticket')


@support_bp.route('/admin/tickets/<int:ticket_id>/messages', methods=['POST'])
@login_required
@module_permission_required(AGENT_MODULE)
def admin_reply(ticket_id):
    """multipart/form-data: body, is_internal, status (submit-as), close_reason, files[]."""
    try:
        result = SupportTicketService().admin_reply(
            current_user, ticket_id, request.form, request.files.getlist('files'))
        return jsonify({'success': True, 'id': result['id']}), 201
    except AppError:
        raise
    except Exception:
        raise _guard('admin_reply')


@support_bp.route('/admin/tickets/<int:ticket_id>', methods=['PATCH'])
@login_required
@module_permission_required(AGENT_MODULE)
def admin_update(ticket_id):
    """JSON: any of status (+ close_reason), priority, assigned_to."""
    try:
        data = _json_body()
        SupportTicketService().admin_update(current_user, ticket_id, data)
        if 'status' in data:
            audit_event('support_ticket', 'UPDATE', entity_id=ticket_id,
                        entity_label=f'Zgłoszenie #{ticket_id}', field_name='status',
                        new_value=str(data.get('status')))
        return jsonify({'success': True})
    except AppError:
        raise
    except Exception:
        raise _guard('admin_update')
