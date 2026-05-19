"""
Public routes — no authentication required.
Client-facing pages accessed via SMS confirmation links.
"""
import logging
from flask import Blueprint, render_template, request
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.clients.client_repository import ClientRepository
from repositories.audit_repository import AuditRepository

public_bp = Blueprint('public', __name__)


@public_bp.route('/confirm/<token>', methods=['GET'])
def appointment_confirm_view(token):
    repo = AppointmentRepository()
    appt = repo.get_by_confirmation_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)
    client = ClientRepository().get_by_id(appt['client_id'])
    return render_template(
        'public/appointment_confirm.html',
        appointment=appt,
        client=client,
        token=token,
        already_responded=(appt.get('confirmation_status') is not None),
        confirmation_status=appt.get('confirmation_status'),
        just_submitted=False,
    )


@public_bp.route('/confirm/<token>', methods=['POST'])
def appointment_confirm_submit(token):
    repo = AppointmentRepository()
    appt = repo.get_by_confirmation_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)

    if appt.get('confirmation_status'):
        return render_template(
            'public/appointment_confirm.html',
            appointment=appt, client=None, token=token,
            already_responded=True,
            confirmation_status=appt['confirmation_status'],
            just_submitted=False,
        )

    action = request.form.get('action')
    if action not in ('confirmed', 'declined'):
        return render_template(
            'public/appointment_confirm.html',
            appointment=appt, client=None, token=token,
            error='Nieprawidłowa akcja', already_responded=False,
            confirmation_status=None, just_submitted=False,
        )

    repo.update_confirmation_status(appt['id'], action)

    old_status = appt.get('status')
    if action == 'confirmed' and old_status in ('scheduled', 'pending'):
        repo.update_status(appt['id'], 'confirmed')

    try:
        audit = AuditRepository()
        audit.log_event(
            entity_type='appointment', action='CLIENT_CONFIRMATION',
            entity_id=appt['id'],
            entity_label=f"{appt.get('appointment_date')} {str(appt.get('start_time',''))[:5]}",
            field_name='confirmation_status',
            old_value=None, new_value=action,
            user_id=None, user_name='Klient (SMS)',
        )
        if action == 'confirmed' and old_status in ('scheduled', 'pending'):
            audit.log_event(
                entity_type='appointment', action='STATUS_CHANGED',
                entity_id=appt['id'],
                entity_label=f"{appt.get('appointment_date')} {str(appt.get('start_time',''))[:5]}",
                field_name='status',
                old_value=old_status, new_value='confirmed',
                user_id=None, user_name='Klient (SMS)',
            )
    except Exception:
        logging.exception("Audit log failed for confirmation token=%s", token)

    return render_template(
        'public/appointment_confirm.html',
        appointment=appt, client=None, token=token,
        just_submitted=True, already_responded=True,
        confirmation_status=action,
    )


_CANCELABLE_STATUSES = {'scheduled', 'confirmed', 'pending'}


@public_bp.route('/cancel/<token>', methods=['GET'])
def appointment_cancel_view(token):
    repo = AppointmentRepository()
    appt = repo.get_by_confirmation_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)
    client = ClientRepository().get_by_id(appt['client_id'])
    already_cancelled = appt.get('status') == 'cancelled'
    can_cancel = appt.get('status') in _CANCELABLE_STATUSES

    return render_template(
        'public/appointment_cancel.html',
        appointment=appt,
        client=client,
        token=token,
        already_cancelled=already_cancelled,
        can_cancel=can_cancel,
        just_submitted=False,
    )


@public_bp.route('/cancel/<token>', methods=['POST'])
def appointment_cancel_submit(token):
    repo = AppointmentRepository()
    appt = repo.get_by_confirmation_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)

    if appt.get('status') == 'cancelled':
        return render_template(
            'public/appointment_cancel.html',
            appointment=appt, client=None, token=token,
            already_cancelled=True, can_cancel=False, just_submitted=False,
        )

    if appt.get('status') not in _CANCELABLE_STATUSES:
        return render_template(
            'public/appointment_cancel.html',
            appointment=appt, client=None, token=token,
            already_cancelled=False, can_cancel=False, just_submitted=False,
        )

    repo.update_status(appt['id'], 'cancelled')

    try:
        AuditRepository().log_event(
            entity_type='appointment', action='STATUS_CHANGED',
            entity_id=appt['id'],
            entity_label=f"{appt.get('appointment_date')} {str(appt.get('start_time',''))[:5]}",
            field_name='status',
            old_value=appt.get('status'), new_value='cancelled',
            user_id=None, user_name='Klient (SMS)',
        )
    except Exception:
        logging.exception("Audit log failed for cancel token=%s", token)

    return render_template(
        'public/appointment_cancel.html',
        appointment=appt, client=None, token=token,
        already_cancelled=True, can_cancel=False, just_submitted=True,
    )
