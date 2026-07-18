"""
Public routes — no authentication required.
Client-facing pages accessed via SMS confirmation links.
"""
import logging
from flask import Blueprint, render_template, request, jsonify
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


# ---------------------------------------------------------------------------
# Visit rating routes (P08)
# ---------------------------------------------------------------------------

@public_bp.route('/rate/<token>', methods=['GET'])
def appointment_rate_view(token):
    """Public rating form — no auth required."""
    appt = AppointmentRepository().get_by_rating_token(token)
    if not appt:
        return render_template('public/rate_invalid.html'), 404

    appt = dict(appt)
    already_rated = appt.get('satisfaction_score') is not None
    return render_template(
        'public/appointment_rate.html',
        appointment=appt, token=token,
        already_rated=already_rated,
        current_score=appt.get('satisfaction_score'),
        just_submitted=False,
    )


@public_bp.route('/rate/<token>', methods=['POST'])
def appointment_rate_submit(token):
    """Save client rating — idempotent."""
    repo = AppointmentRepository()
    appt = repo.get_by_rating_token(token)
    if not appt:
        return render_template('public/rate_invalid.html'), 404

    appt = dict(appt)

    # Idempotent guard: already rated -> show confirmation, no DB write
    if appt.get('satisfaction_score') is not None:
        return render_template(
            'public/appointment_rate.html',
            appointment=appt, token=token,
            already_rated=True,
            current_score=appt['satisfaction_score'],
            just_submitted=False,
        )

    try:
        score = int(request.form.get('score', 0))
        if not 1 <= score <= 5:
            raise ValueError('score out of range')
    except (ValueError, TypeError):
        return render_template(
            'public/appointment_rate.html',
            appointment=appt, token=token,
            already_rated=False, current_score=None,
            error='Nieprawidlowa ocena — wybierz od 1 do 5 gwiazdek.',
            just_submitted=False,
        )

    from datetime import datetime, timezone
    repo.update_rating(
        appointment_id=appt['id'],
        score=score,
        rated_on=datetime.now(timezone.utc),
        rated_by='client',
    )

    try:
        AuditRepository().log_event(
            entity_type='appointment', action='CLIENT_RATING',
            entity_id=appt['id'],
            entity_label=f"{appt.get('appointment_date')} — ocena: {score}/5",
            field_name='satisfaction_score',
            old_value=None, new_value=str(score),
            user_id=None, user_name='Klient (SMS)',
        )
    except Exception:
        logging.exception("Audit log failed for rating token=%s", token)

    return render_template(
        'public/appointment_rate.html',
        appointment=appt, token=token,
        already_rated=True, current_score=score, just_submitted=True,
    )


# ---------------------------------------------------------------------------
# Employee visit status routes (P10b)
# ---------------------------------------------------------------------------

def _employee_visit_state(appt: dict) -> tuple:
    """Return (state_str, context_dict) for the employee visit form."""
    from datetime import datetime, time as _time
    now       = datetime.now()
    start_time = appt['start_time']
    appt_date  = appt['appointment_date']

    if hasattr(start_time, 'hour'):
        appt_dt = datetime.combine(appt_date, start_time)
    else:
        h, m = str(start_time)[:5].split(':')
        appt_dt = datetime.combine(appt_date, _time(int(h), int(m)))

    minutes_until = (appt_dt - now).total_seconds() / 60
    status = appt['status']

    if status in ('completed', 'cancelled', 'no_show'):
        return 'already_done', {}
    if status == 'in_progress':
        return 'end_visit', {}
    if status in ('scheduled', 'confirmed', 'pending'):
        if minutes_until > 20:
            return 'too_early', {'minutes_remaining': int(minutes_until - 20)}
        return 'start_visit', {}
    return 'wrong_status', {}


def _serialize_appt(appt: dict) -> dict:
    """JSON-safe appointment fields for the companion mobile app."""
    return {
        'first_name': appt.get('first_name'),
        'last_name': appt.get('last_name'),
        'appointment_date': str(appt.get('appointment_date')),
        'start_time': str(appt.get('start_time'))[:5],
        'status': appt.get('status'),
    }


def _process_visit_action(repo: AppointmentRepository, appt: dict, token: str, action: str) -> dict:
    """Validate + apply a start/end action; shared by the HTML form and the JSON API.

    Returns {'state', 'ctx', 'error', 'new_status'}. On success mutates
    appt['status'] in place and sets error=None, new_status='in_progress'|'completed'.
    """
    state, ctx = _employee_visit_state(appt)

    if action not in ('start', 'end'):
        return {'state': state, 'ctx': ctx, 'error': 'Akcja niedostepna w biezacym stanie wizyty.', 'new_status': None}
    if action == 'start' and state != 'start_visit':
        return {'state': state, 'ctx': ctx, 'error': 'Akcja niedostepna w biezacym stanie wizyty.', 'new_status': None}
    if action == 'end' and state != 'end_visit':
        return {'state': state, 'ctx': ctx, 'error': 'Akcja niedostepna w biezacym stanie wizyty.', 'new_status': None}

    old_status = appt['status']
    new_status = 'in_progress' if action == 'start' else 'completed'
    repo.update_status(appt['id'], new_status)

    # Real-time notification event
    from repositories.appointments.status_change_event_repository import StatusChangeEventRepository
    try:
        StatusChangeEventRepository().create(appt['id'], old_status, new_status, 'employee_mobile')
    except Exception:
        logging.exception("StatusChangeEvent insert failed appt=%s", appt['id'])

    # Audit log
    try:
        AuditRepository().log_event(
            entity_type='appointment', action='STATUS_CHANGED',
            entity_id=appt['id'],
            entity_label=f"{appt.get('appointment_date')} {str(appt.get('start_time',''))[:5]}",
            field_name='status', old_value=old_status, new_value=new_status,
            user_id=None, user_name='Pracownik (mobile)',
        )
    except Exception:
        logging.exception("Audit log failed for employee visit token=%s", token)

    # Trigger post-visit rating SMS when completing
    if new_status == 'completed':
        try:
            from routes.appointment_routes import _schedule_post_visit_sms
            _schedule_post_visit_sms(appt['id'])
        except Exception:
            logging.exception("_schedule_post_visit_sms failed appt=%s", appt['id'])

    appt['status'] = new_status
    return {'state': 'success', 'ctx': {}, 'error': None, 'new_status': new_status}


@public_bp.route('/visit/<token>', methods=['GET'])
def employee_visit_status_view(token):
    """Employee mobile form — time-gated visit status transition."""
    appt = AppointmentRepository().get_by_employee_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)
    state, ctx = _employee_visit_state(appt)
    return render_template(
        'public/appointment_employee_status.html',
        appointment=appt, state=state, **ctx,
    )


@public_bp.route('/visit/<token>', methods=['POST'])
def employee_visit_status_submit(token):
    """Process employee start/end visit action (HTML form, reached via SMS link)."""
    repo = AppointmentRepository()
    appt = repo.get_by_employee_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)
    action = request.form.get('action')   # 'start' | 'end'
    result = _process_visit_action(repo, appt, token, action)

    if result['error']:
        return render_template(
            'public/appointment_employee_status.html',
            appointment=appt, state=result['state'],
            error=result['error'], **result['ctx'],
        )
    return render_template(
        'public/appointment_employee_status.html',
        appointment=appt, state='success', new_status=result['new_status'],
    )


@public_bp.route('/api/visit/<token>', methods=['GET'])
def employee_visit_status_api(token):
    """JSON status lookup for the companion mobile app."""
    appt = AppointmentRepository().get_by_employee_token(token)
    if not appt:
        return jsonify({'success': False, 'error': 'not_found'}), 404

    appt = dict(appt)
    state, ctx = _employee_visit_state(appt)
    return jsonify({'success': True, 'state': state, 'appointment': _serialize_appt(appt), **ctx})


@public_bp.route('/api/visit/<token>', methods=['POST'])
def employee_visit_status_api_submit(token):
    """JSON start/end action for the companion mobile app."""
    repo = AppointmentRepository()
    appt = repo.get_by_employee_token(token)
    if not appt:
        return jsonify({'success': False, 'error': 'not_found'}), 404

    appt = dict(appt)
    action = (request.get_json(silent=True) or {}).get('action')
    result = _process_visit_action(repo, appt, token, action)

    if result['error']:
        return jsonify({'success': False, 'state': result['state'], 'error': result['error'], **result['ctx']})

    return jsonify({
        'success': True, 'state': 'success', 'new_status': result['new_status'],
        'appointment': _serialize_appt(appt),
    })
