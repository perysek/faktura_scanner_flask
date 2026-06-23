"""
SMS settings and reminder routes — admin only.
"""
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from config.auth_config import module_permission_required, can_send_appointment_sms
from services.sms_service import SmsService, SmsError
from repositories.sms.sms_repository import SmsReminderRepository, SmsMessageTypeRepository

sms_bp = Blueprint('sms', __name__)


@sms_bp.route('/settings/sms', methods=['GET'])
@login_required
@module_permission_required('settings')
def sms_settings():
    svc = SmsService()
    settings = svc.get_settings()
    message_types = svc.get_message_types()
    stats = SmsReminderRepository().get_stats()
    return render_template('settings/sms.html',
                           settings=settings,
                           message_types=message_types,
                           stats=stats)


@sms_bp.route('/settings/sms/credentials', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_credentials_save():
    svc = SmsService()
    data = request.form
    svc.save_settings(
        account_sid=data.get('account_sid', '').strip(),
        auth_token=data.get('auth_token', '').strip(),
        from_number=data.get('from_number', '').strip(),
        messaging_service_sid=data.get('messaging_service_sid', '').strip() or None,
        is_active=('is_active' in data),
    )
    flash('Dane Twilio zapisane. Teraz SMS-y mają z czego latać.', 'success')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/message-type/<int:type_id>', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_message_type_save(type_id):
    svc = SmsService()
    data = request.form
    svc.save_message_type(
        type_id,
        is_enabled=('is_enabled' in data),
        send_hours_before=int(data.get('send_hours_before', 24)),
        send_delay_minutes=int(data.get('send_delay_minutes', 0)),
        template_text=data.get('template_text', '').strip(),
        include_confirm_link=('include_confirm_link' in data),
        include_cancel_link=('include_cancel_link' in data),
        include_rate_link=('include_rate_link' in data),
        send_only_if_confirmed=('send_only_if_confirmed' in data),
        name=data.get('name', '').strip(),
    )
    flash('Typ SMS-a podrasowany.', 'success')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/message-type/create', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_message_type_create():
    data = request.form
    name = data.get('name', '').strip()
    if not name:
        flash('Nazwa się sama nie wymyśli. Wpisz coś.', 'error')
        return redirect(url_for('sms.sms_settings'))
    svc = SmsService()
    svc.create_custom_type(
        name=name,
        send_hours_before=int(data.get('send_hours_before', 24)),
        template_text=data.get('template_text', '').strip(),
        include_confirm_link=('include_confirm_link' in data),
        include_cancel_link=('include_cancel_link' in data),
    )
    flash('Nowy typ SMS-a na pokładzie.', 'success')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/message-type/<int:type_id>/delete', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_message_type_delete(type_id):
    try:
        svc = SmsService()
        ok = svc.delete_custom_type(type_id)
        if ok:
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Nie można usunąć wbudowanego typu wiadomości'}), 400
    except Exception:
        logging.exception('Error in sms_message_type_delete')
        return jsonify({'success': False, 'message': 'Błąd serwera'}), 500


@sms_bp.route('/settings/sms/test', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_test():
    data = request.get_json()
    svc = SmsService()
    ok, result = svc.test_connection(
        account_sid=data.get('account_sid', ''),
        auth_token=data.get('auth_token', ''),
        from_number=data.get('from_number', ''),
        to_number=data.get('to_number', ''),
        messaging_service_sid=data.get('messaging_service_sid', '') or None,
    )
    return jsonify({'success': ok, 'result': result})


@sms_bp.route('/settings/sms/log', methods=['GET'])
@login_required
@module_permission_required('settings')
def sms_log():
    repo = SmsReminderRepository()
    offset = request.args.get('offset', 0, type=int)
    rows = repo.get_log(limit=100, offset=offset)
    return render_template('settings/sms_log.html', rows=rows, offset=offset)


@sms_bp.route('/api/sms/stats', methods=['GET'])
@login_required
@module_permission_required('settings')
def sms_stats():
    stats = SmsReminderRepository().get_stats()
    return jsonify({'success': True, 'stats': stats})


# -----------------------------------------------------------------------
# Appointment-level SMS endpoints
# -----------------------------------------------------------------------

@sms_bp.route('/api/sms/send', methods=['POST'])
@login_required
@module_permission_required('appointments')
def send_sms():
    if not can_send_appointment_sms(current_user.role):
        return jsonify({'success': False,
                        'message': 'Brak uprawnień do wysyłania SMS'}), 403
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    message_type_key = data.get('message_type_key')
    if not appointment_id or not message_type_key:
        return jsonify({'success': False,
                        'message': 'Wymagane: appointment_id i message_type_key'}), 400

    base_url = request.host_url.rstrip('/')
    svc = SmsService()
    try:
        result = svc.send(
            appointment_id=int(appointment_id),
            message_type_key=message_type_key,
            sender_user_id=current_user.id,
            sender_name=current_user.full_name,
            base_url=base_url,
        )
        if result['success']:
            return jsonify({'success': True,
                            'message': 'SMS wysłany',
                            'reminder_id': result['reminder_id']})
        return jsonify({'success': False,
                        'message': result.get('error', 'Błąd wysyłki'),
                        'reminder_id': result.get('reminder_id')}), 500
    except SmsError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception:
        logging.exception("Unexpected error in send_sms")
        return jsonify({'success': False, 'message': 'Błąd serwera'}), 500


@sms_bp.route('/api/sms/bulk-send', methods=['POST'])
@login_required
@module_permission_required('appointments')
def bulk_send():
    if not can_send_appointment_sms(current_user.role):
        return jsonify({'success': False,
                        'message': 'Brak uprawnień do wysyłania SMS'}), 403
    data = request.get_json()
    ids = data.get('appointment_ids', [])
    message_type_key = data.get('message_type_key')
    if not ids or not message_type_key:
        return jsonify({'success': False,
                        'message': 'Wymagane: appointment_ids i message_type_key'}), 400

    base_url = request.host_url.rstrip('/')
    svc = SmsService()
    results = []
    for appt_id in ids:
        try:
            res = svc.send(
                appointment_id=int(appt_id),
                message_type_key=message_type_key,
                sender_user_id=current_user.id,
                sender_name=current_user.full_name,
                base_url=base_url,
            )
            results.append({'appointment_id': appt_id, **res})
        except SmsError as e:
            results.append({'appointment_id': appt_id, 'success': False, 'error': str(e)})

    sent = sum(1 for r in results if r.get('success'))
    return jsonify({'success': True, 'sent': sent, 'total': len(ids), 'details': results})


@sms_bp.route('/api/sms/appointment/<int:appointment_id>/log', methods=['GET'])
@login_required
@module_permission_required('appointments')
def appointment_sms_log(appointment_id):
    repo = SmsReminderRepository()
    rows = repo.get_for_appointment(appointment_id)
    for r in rows:
        if r.get('sent_at'):
            r['sent_at'] = str(r['sent_at'])
    return jsonify({'success': True, 'reminders': rows})
