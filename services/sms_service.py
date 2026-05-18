"""
Twilio SMS service — outbound only.
Requires: pip install twilio
"""
import logging
import re
import uuid
from datetime import datetime
from typing import Optional, Tuple, List

from flask import current_app

from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.audit_repository import AuditRepository
from repositories.clients.client_repository import ClientRepository
from repositories.sms.sms_repository import (
    SmsSettingsRepository, SmsMessageTypeRepository, SmsReminderRepository
)


class SmsError(Exception):
    pass


class SmsService:
    """Wraps Twilio API and manages all SMS reminder workflows."""

    def __init__(self):
        self._settings_repo = SmsSettingsRepository()
        self._type_repo = SmsMessageTypeRepository()
        self._reminder_repo = SmsReminderRepository()
        self._appt_repo = AppointmentRepository()
        self._client_repo = ClientRepository()
        self._audit_repo = AuditRepository()

    # ------------------------------------------------------------------
    # Settings helpers
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        return self._settings_repo.get_settings() or {}

    def save_settings(self, **kwargs) -> bool:
        return self._settings_repo.update_settings(**kwargs)

    def get_message_types(self) -> List[dict]:
        return self._type_repo.get_all()

    def save_message_type(self, type_id: int, **fields) -> bool:
        return self._type_repo.update(type_id, **fields)

    def create_custom_type(self, name: str, send_hours_before: int,
                           template_text: str, include_confirm_link: bool) -> int:
        return self._type_repo.create_custom(
            name=name, send_hours_before=send_hours_before,
            template_text=template_text, include_confirm_link=include_confirm_link
        )

    def delete_custom_type(self, type_id: int) -> bool:
        return self._type_repo.delete_custom(type_id)

    def test_connection(self, account_sid: str, auth_token: str,
                        from_number: str, to_number: str) -> Tuple[bool, str]:
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            msg = client.messages.create(
                body="Test wiadomości SMS z MyWay Beauty Salon.",
                from_=from_number,
                to=to_number,
            )
            return True, msg.sid
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Core: send one message type for one appointment
    # ------------------------------------------------------------------

    def send(
        self,
        appointment_id: int,
        message_type_key: str,
        sender_user_id: Optional[int] = None,
        sender_name: Optional[str] = None,
        base_url: str = None,
    ) -> dict:
        """
        Build and send a specific SMS type for appointment_id.
        Returns: {success, reminder_id, twilio_sid, message_body, error}
        Raises SmsError on config problems.
        """
        settings = self.get_settings()
        if not settings.get('account_sid') or not settings.get('auth_token'):
            raise SmsError("Brak konfiguracji Twilio (account_sid / auth_token)")
        if not settings.get('from_number'):
            raise SmsError("Brak numeru nadawcy SMS")
        if not settings.get('is_active'):
            raise SmsError("Wysyłanie SMS jest wyłączone w ustawieniach")

        msg_type = self._type_repo.get_by_key(message_type_key)
        if not msg_type:
            raise SmsError(f"Nieznany typ SMS: {message_type_key}")

        appt = self._appt_repo.get_by_id(appointment_id)
        if not appt:
            raise SmsError(f"Wizyta {appointment_id} nie istnieje")
        appt = dict(appt)

        client = self._client_repo.get_by_id(appt['client_id'])
        if not client:
            raise SmsError("Klient nie istnieje")

        phone_raw = client['phone'] if hasattr(client, '__getitem__') else getattr(client, 'phone', None)
        if not phone_raw:
            raise SmsError("Klient nie ma numeru telefonu")
        phone = self._normalize_phone(phone_raw)

        token = appt.get('confirmation_token')
        if not token:
            token = str(uuid.uuid4())
            self._appt_repo.update_confirmation_token(appointment_id, token)

        if base_url is None:
            base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        confirm_url = f"{base_url}/confirm/{token}"

        message_body = self._build_message(appt, client, msg_type, confirm_url)

        reminder_id = self._reminder_repo.create(
            appointment_id=appointment_id,
            client_id=appt['client_id'],
            message_type_id=msg_type['id'],
            message_type_key=message_type_key,
            phone_number=phone,
            message_body=message_body,
            created_by_user_id=sender_user_id,
            created_by_name=sender_name,
        )

        try:
            from twilio.rest import Client as TwilioClient
            twilio = TwilioClient(settings['account_sid'], settings['auth_token'])
            msg = twilio.messages.create(
                body=message_body,
                from_=settings['from_number'],
                to=phone,
            )
            twilio_sid = msg.sid
            self._reminder_repo.update_status(reminder_id, 'sent', twilio_sid=twilio_sid)

            appt_date_fmt = self._fmt_date(str(appt['appointment_date']))
            start_time = str(appt.get('start_time', ''))[:5]
            self._audit_repo.log_event(
                entity_type='appointment', action='SMS_SENT',
                entity_id=appointment_id,
                entity_label=f"{appt_date_fmt} {start_time}",
                field_name='sms_type',
                new_value=f"{msg_type['name']} → {phone} (SID: {twilio_sid})",
                user_id=sender_user_id, user_name=sender_name,
            )
            return {'success': True, 'reminder_id': reminder_id,
                    'twilio_sid': twilio_sid, 'message_body': message_body}

        except Exception as e:
            err = str(e)
            self._reminder_repo.update_status(reminder_id, 'failed', error_message=err)
            logging.error("SMS send failed appt=%s type=%s: %s", appointment_id, message_type_key, err)
            return {'success': False, 'reminder_id': reminder_id, 'error': err}

    # ------------------------------------------------------------------
    # Auto-send: called by APScheduler every 15 minutes
    # ------------------------------------------------------------------

    def send_due_reminders(self, base_url: str) -> dict:
        enabled_types = self._type_repo.get_enabled()
        sent = skipped = failed = 0

        for msg_type in enabled_types:
            hours_before = msg_type['send_hours_before']
            due_rows = self._appt_repo.get_appointments_due_for_type(
                hours_before=hours_before,
                message_type_key=msg_type['type_key'],
            )
            for row in due_rows:
                try:
                    result = self.send(
                        appointment_id=row['id'],
                        message_type_key=msg_type['type_key'],
                        sender_user_id=None,
                        sender_name='System (auto)',
                        base_url=base_url,
                    )
                    if result['success']:
                        sent += 1
                    else:
                        failed += 1
                except SmsError:
                    skipped += 1
                except Exception:
                    logging.exception("Auto-remind failed appt=%s type=%s", row['id'], msg_type['type_key'])
                    failed += 1

        return {'sent': sent, 'skipped': skipped, 'failed': failed}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_phone(self, phone: str) -> str:
        phone = re.sub(r'[\s\-\(\)]', '', phone.strip())
        if phone.startswith('+'):
            return phone
        if phone.startswith('48') and len(phone) == 11:
            return '+' + phone
        if phone.startswith('0') and len(phone) == 10:
            return '+48' + phone[1:]
        if len(phone) == 9:
            return '+48' + phone
        return phone

    def _fmt_date(self, date_str: str) -> str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            return date_str

    def _build_message(self, appt: dict, client, msg_type: dict, confirm_url: str) -> str:
        from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
        services_rows = AppointmentServiceRepository().get_all_for_appointment(appt['id'])
        service_names = ', '.join(s['service_name'] for s in services_rows) if services_rows else ''

        appt_date_fmt = self._fmt_date(str(appt['appointment_date']))
        start_time = str(appt.get('start_time', ''))[:5]
        salon_name = current_app.config.get('APP_NAME', 'MyWay Beauty Salon')
        client_first = client['first_name'] if hasattr(client, '__getitem__') else getattr(client, 'first_name', '')

        try:
            appt_dt = datetime.strptime(f"{appt['appointment_date']} {start_time}", '%Y-%m-%d %H:%M')
            delta = appt_dt - datetime.now()
            hours_before = max(0, int(delta.total_seconds() / 3600))
        except Exception:
            hours_before = msg_type['send_hours_before']

        template = msg_type['template_text']
        body = (template
            .replace('{salon_name}', salon_name)
            .replace('{client_name}', client_first)
            .replace('{date}', appt_date_fmt)
            .replace('{time}', start_time)
            .replace('{services}', service_names)
            .replace('{hours_before}', str(hours_before))
            .replace('{confirm_url}', confirm_url if msg_type['include_confirm_link'] else '')
        )
        return body.strip()
