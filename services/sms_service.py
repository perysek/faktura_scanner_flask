"""
Twilio SMS service — outbound only.
Requires: pip install twilio
"""
import logging
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
from utils.phone import normalize_phone
from utils.timezone import now_local, WARSAW_TZ


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
                           template_text: str, include_confirm_link: bool,
                           include_cancel_link: bool = False,
                           include_booking_link: bool = False) -> int:
        return self._type_repo.create_custom(
            name=name, send_hours_before=send_hours_before,
            template_text=template_text, include_confirm_link=include_confirm_link,
            include_cancel_link=include_cancel_link,
            include_booking_link=include_booking_link,
        )

    def delete_custom_type(self, type_id: int) -> bool:
        return self._type_repo.delete_custom(type_id)

    def test_connection(self, account_sid: str, auth_token: str,
                        from_number: str, to_number: str,
                        messaging_service_sid: Optional[str] = None) -> Tuple[bool, str]:
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            send_kwargs = {
                'body': "Test wiadomości SMS z MyWay Beauty Salon.",
                'to': to_number,
            }
            if messaging_service_sid:
                send_kwargs['messaging_service_sid'] = messaging_service_sid
            else:
                send_kwargs['from_'] = from_number
            msg = client.messages.create(**send_kwargs)
            return True, msg.sid
        except Exception as e:
            return False, str(e)

    def type_status(self, type_key: str) -> dict:
        """Can a text of this type actually go out right now? -> {'available': bool, 'reason': str}.

        For UIs offering an optional "send SMS" action. `send()` refuses a switched-off type,
        so a checkbox that does not check this would let staff believe they notified a client
        while nothing was sent (the absence-conflict modal ships with its box ticked and its
        type disabled). `reason` is Polish, ready to show.
        """
        settings = self.get_settings()
        configured = bool(settings.get('account_sid') and settings.get('auth_token')
                          and (settings.get('messaging_service_sid') or settings.get('from_number')))
        if not settings.get('is_active') or not configured:
            return {'available': False,
                    'reason': 'Wysyłanie SMS jest wyłączone lub nieskonfigurowane (Ustawienia SMS).'}
        msg_type = self._type_repo.get_by_key(type_key)
        if not msg_type:
            return {'available': False, 'reason': f'Nieznany typ SMS: {type_key}.'}
        if not msg_type.get('is_enabled'):
            return {'available': False,
                    'reason': f'Typ SMS „{msg_type.get("name") or type_key}” jest wyłączony w Ustawieniach SMS.'}
        return {'available': True, 'reason': ''}

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
        auto: bool = False,
    ) -> dict:
        """
        Build and send a specific SMS type for appointment_id.
        Returns: {success, reminder_id, twilio_sid, message_body, error}
        Raises SmsError on config problems — including a type that is switched off
        (`is_enabled` is the "this text may be used" switch for scheduler AND manual
        sends alike; before, only the scheduler's own query honoured it).

        `auto=True` marks scheduler/event-queue sends: those are idempotent per
        (appointment, type) — a second attempt returns `{'success': False,
        'skipped': True}` instead of texting the client again (a rating request must
        arrive exactly once). Manual sends by staff are deliberate and stay repeatable.
        """
        settings = self.get_settings()
        if not settings.get('account_sid') or not settings.get('auth_token'):
            raise SmsError("Brak konfiguracji Twilio (account_sid / auth_token)")
        if not settings.get('messaging_service_sid') and not settings.get('from_number'):
            raise SmsError("Brak numeru nadawcy SMS lub Messaging Service SID")
        if not settings.get('is_active'):
            raise SmsError("Wysyłanie SMS jest wyłączone w ustawieniach")

        msg_type = self._type_repo.get_by_key(message_type_key)
        if not msg_type:
            raise SmsError(f"Nieznany typ SMS: {message_type_key}")
        if not msg_type.get('is_enabled'):
            raise SmsError(f"Typ SMS „{msg_type.get('name') or message_type_key}” jest wyłączony w ustawieniach")

        if auto and self._reminder_repo.exists_active(appointment_id, message_type_key):
            return {'success': False, 'skipped': True,
                    'error': f"SMS „{message_type_key}” dla wizyty {appointment_id} już wysłany"}

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

        if msg_type.get('send_only_if_confirmed') and appt.get('status') != 'confirmed':
            raise SmsError(
                f"SMS nie wysłany — wymagany status 'Potwierdzona', "
                f"aktualny: '{appt.get('status')}'"
            )

        if base_url is None:
            base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        confirm_url = f"{base_url}/confirm/{token}"
        cancel_url = f"{base_url}/cancel/{token}"
        booking_url = f"{base_url.rstrip('/')}/booking"

        message_body = self._build_message(appt, client, msg_type, confirm_url, cancel_url,
                                            base_url, booking_url)

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
            send_kwargs = {'body': message_body, 'to': phone}
            if settings.get('messaging_service_sid'):
                send_kwargs['messaging_service_sid'] = settings['messaging_service_sid']
            else:
                send_kwargs['from_'] = settings['from_number']
            msg = twilio.messages.create(**send_kwargs)
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

    # ------------------------------------------------------------------
    # Event-triggered SMS scheduling (P04)
    # ------------------------------------------------------------------

    def schedule_event_sms(self, appointment_id: int, event_type: str,
                           delay_minutes: int, base_url: str) -> Optional[int]:
        """
        Create an sms_events row to fire event_type SMS after delay_minutes.
        Updates appointment.rating_status = 'scheduled' for post_visit_message.
        Returns sms_events.id, or None if SMS globally disabled.
        """
        from datetime import datetime, timedelta, timezone
        from repositories.sms.sms_event_repository import SmsEventRepository

        settings = self.get_settings()
        if not settings.get('is_active'):
            return None

        scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        event_id = SmsEventRepository().create(appointment_id, event_type, scheduled_at)

        if event_type == 'post_visit_message':
            self._appt_repo.update_rating_status(appointment_id, 'scheduled')

        return event_id

    def schedule_employee_reminder(self, appointment_id: int,
                                    appointment_dt) -> Optional[int]:
        """Schedule employee_visit_reminder SMS 20 min before appointment start.
        Cancels any existing pending reminder first (handles reschedules).
        Returns sms_events.id or None if SMS disabled / window already passed.

        `appointment_dt` is naive *Warsaw* wall-clock (how appointments are stored).
        It must be compared with Warsaw "now" and handed to the TIMESTAMPTZ column
        as an aware datetime — a naive value would be read in the DB session
        timezone (UTC on the server), landing the reminder 1-2h after the visit
        had already started."""
        from datetime import timedelta
        from repositories.sms.sms_event_repository import SmsEventRepository

        settings = self.get_settings()
        if not settings.get('is_active'):
            return None

        scheduled_local = appointment_dt - timedelta(minutes=20)
        if scheduled_local <= now_local():
            return None
        scheduled_at = scheduled_local.replace(tzinfo=WARSAW_TZ)

        repo = SmsEventRepository()
        repo.cancel_type_for_appointment(appointment_id, 'employee_visit_reminder')
        return repo.create(appointment_id, 'employee_visit_reminder', scheduled_at)

    def _send_employee_reminder_direct(self, event: dict, base_url: str) -> dict:
        """Send visit-reminder SMS to the employee's phone (not the client's)."""
        settings = self.get_settings()
        employee_phone = event.get('employee_phone')
        if not employee_phone:
            return {'success': False, 'error': 'Brak numeru telefonu pracownika'}

        employee_name  = event.get('employee_first_name', 'Pracowniku')
        client_name    = event.get('employee_client_name', '')
        start_time     = str(event.get('start_time', ''))[:5]
        employee_token = event.get('employee_token', '')
        visit_url = f"{base_url.rstrip('/')}/visit/{employee_token}" if employee_token else ''

        body = (
            f"Hej {employee_name}! Za 20 min wizyta: {client_name} godz. {start_time}. "
            f"Formularz: {visit_url}"
        )

        try:
            from twilio.rest import Client as TwilioClient
            twilio = TwilioClient(settings['account_sid'], settings['auth_token'])
            # Twilio only accepts E.164; employees' phones are free text like "500 100 200".
            send_kwargs = {'body': body, 'to': self._normalize_phone(employee_phone)}
            if settings.get('messaging_service_sid'):
                send_kwargs['messaging_service_sid'] = settings['messaging_service_sid']
            else:
                send_kwargs['from_'] = settings['from_number']
            twilio.messages.create(**send_kwargs)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def notify_employee_direct(self, employee_id: int, body: str) -> dict:
        """Plain-text SMS straight to an employee's own phone, bypassing the
        sms_message_types lookup entirely — for internal staff notices (e.g. 'you
        were reassigned a visit') that aren't a client-facing configurable
        template. Mirrors _send_employee_reminder_direct's Twilio-call shape.
        Returns {success, error?} instead of raising — callers treat this as a
        best-effort notification, never a reason to fail the caller's own action.
        """
        from repositories.employees.employee_repository import EmployeeRepository

        settings = self.get_settings()
        if not settings.get('is_active') or not settings.get('account_sid') or not settings.get('auth_token'):
            return {'success': False, 'error': 'SMS wyłączone lub brak konfiguracji Twilio'}
        if not settings.get('messaging_service_sid') and not settings.get('from_number'):
            return {'success': False, 'error': 'Brak numeru nadawcy SMS'}

        employee = EmployeeRepository().get_by_id(employee_id)
        if not employee or not employee['phone']:
            return {'success': False, 'error': 'Brak numeru telefonu pracownika'}

        try:
            from twilio.rest import Client as TwilioClient
            twilio = TwilioClient(settings['account_sid'], settings['auth_token'])
            send_kwargs = {'body': body, 'to': self._normalize_phone(employee['phone'])}
            if settings.get('messaging_service_sid'):
                send_kwargs['messaging_service_sid'] = settings['messaging_service_sid']
            else:
                send_kwargs['from_'] = settings['from_number']
            twilio.messages.create(**send_kwargs)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def send_due_event_sms(self, base_url: str) -> dict:
        """
        Called by scheduler every 15 min. Sends all due sms_events rows.
        Returns {sent, failed, skipped}.
        """
        from repositories.sms.sms_event_repository import SmsEventRepository
        event_repo = SmsEventRepository()

        sent = failed = skipped = 0
        for event in event_repo.get_due():
            try:
                if event['event_type'] == 'employee_visit_reminder':
                    result = self._send_employee_reminder_direct(event, base_url)
                    if result.get('success'):
                        event_repo.mark_sent(event['id'], None)
                        sent += 1
                    else:
                        event_repo.mark_failed(event['id'], result.get('error', ''))
                        failed += 1
                else:
                    result = self.send(
                        appointment_id=event['appointment_id'],
                        message_type_key=event['event_type'],
                        base_url=base_url,
                        auto=True,
                    )
                    if result.get('skipped'):
                        # Already texted (e.g. the event was queued twice): close it quietly.
                        event_repo.mark_skipped(event['id'], result.get('error', ''))
                        skipped += 1
                    elif result.get('success'):
                        event_repo.mark_sent(event['id'], result.get('reminder_id'))
                        if event['event_type'] == 'post_visit_message':
                            self._appt_repo.update_rating_status(
                                event['appointment_id'], 'sent'
                            )
                        sent += 1
                    else:
                        event_repo.mark_failed(event['id'], result.get('error', ''))
                        failed += 1
            except Exception as e:
                event_repo.mark_failed(event['id'], str(e))
                failed += 1

        return {'sent': sent, 'failed': failed, 'skipped': skipped}

    def schedule_status_triggered_sms(self, appointment_id: int,
                                       trigger_status: str, base_url: str) -> int:
        """
        Look up all enabled event-triggered types for trigger_status,
        schedule each, and return count scheduled.
        """
        settings = self.get_settings()
        if not settings.get('is_active'):
            return 0

        types = self._type_repo.get_event_triggered_by_status(trigger_status)
        count = 0
        for mt in types:
            if mt.get('is_enabled'):
                self.schedule_event_sms(
                    appointment_id, mt['type_key'],
                    mt.get('send_delay_minutes', 0), base_url,
                )
                count += 1
        return count

    def send_due_reminders(self, base_url: str) -> dict:
        # Only "N hours before the visit" types. Event-only/manual types (rating text,
        # absence cancellation, booking confirmation) have their own triggers — feeding
        # them to this loop texted clients at the visit's start (P0-2).
        enabled_types = self._type_repo.get_enabled_before_visit()
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
                        auto=True,
                    )
                    if result.get('skipped'):
                        skipped += 1
                    elif result['success']:
                        sent += 1
                    else:
                        failed += 1
                except SmsError:
                    skipped += 1
                except Exception:
                    logging.exception("Auto-remind failed appt=%s type=%s", row['id'], msg_type['type_key'])
                    failed += 1

        return {'sent': sent, 'skipped': skipped, 'failed': failed}

    def send_booking_confirmation(self, appointment_id: int, *, hold: bool) -> dict:
        """The ONE text an online booking triggers: "reservation received" + confirm/cancel links.

        `hold=True` is for a phone number we have never verified: the visit's automatic
        client reminders are held until the client clicks the confirm link, so a stranger
        typing someone else's number can cause at most this single text — not a stream.
        The hold is set BEFORE sending (closing the race with the 15-minute loop) and lifted
        again if the text did not actually go out; otherwise the client would never receive
        the link that releases it and would silently get no reminders at all.

        Never raises — a failed SMS must not undo a successful booking.
        Returns {'status': 'sent' | 'skipped' | 'failed', 'hold': bool, 'error'?: str}.
        'skipped' = SMS switched off or the type is disabled (the go-live switch); no hold then.
        """
        settings = self.get_settings()
        msg_type = self._type_repo.get_by_key('booking_confirmed')
        if not settings.get('is_active') or not msg_type or not msg_type.get('is_enabled'):
            return {'status': 'skipped', 'hold': False}

        held = False
        try:
            if hold:
                self._appt_repo.set_sms_hold(appointment_id, True)
                held = True
            result = self.send(appointment_id, 'booking_confirmed',
                               sender_name='Rezerwacja online', auto=True)
        except SmsError as exc:
            result = {'success': False, 'error': str(exc)}
        except Exception as exc:
            logging.exception("Booking confirmation SMS crashed appt=%s", appointment_id)
            result = {'success': False, 'error': str(exc)}

        if result.get('success'):
            return {'status': 'sent', 'hold': held}
        if held:
            try:
                self._appt_repo.set_sms_hold(appointment_id, False)
            except Exception:
                logging.exception("Could not lift sms_hold appt=%s after a failed send", appointment_id)
        return {'status': 'failed', 'hold': False, 'error': result.get('error', '')}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_phone(self, phone: str) -> str:
        """E.164 or SmsError. The old lenient version returned anything it couldn't parse and
        Twilio then rejected it (or, for a long string, the VARCHAR(20) column did first)."""
        normalized = normalize_phone(phone)
        if not normalized:
            raise SmsError(f"Nieprawidłowy numer telefonu: {str(phone)[:30]!r}")
        return normalized

    def _fmt_date(self, date_str: str) -> str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            return date_str

    def _build_message(self, appt: dict, client, msg_type: dict,
                       confirm_url: str, cancel_url: str = '',
                       base_url: str = '', booking_url: str = '') -> str:
        from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
        services_rows = AppointmentServiceRepository().get_all_for_appointment(appt['id'])
        service_names = ', '.join(s['service_name'] for s in services_rows) if services_rows else ''

        appt_date_fmt = self._fmt_date(str(appt['appointment_date']))
        start_time = str(appt.get('start_time', ''))[:5]
        salon_name = current_app.config.get('APP_NAME', 'MyWay Beauty Salon')
        client_first = client['first_name'] if hasattr(client, '__getitem__') else getattr(client, 'first_name', '')

        try:
            appt_dt = datetime.strptime(f"{appt['appointment_date']} {start_time}", '%Y-%m-%d %H:%M')
            delta = appt_dt - now_local()   # Warsaw-vs-Warsaw; bare now() is naive-UTC on the server
            hours_before = max(0, int(delta.total_seconds() / 3600))
        except Exception:
            hours_before = msg_type['send_hours_before']

        template = msg_type['template_text']
        has_confirm_placeholder = '{confirm_url}' in template
        has_cancel_placeholder = '{cancel_url}' in template
        has_rate_placeholder = '{rate_url}' in template
        has_booking_placeholder = '{booking_url}' in template

        rating_token = appt.get('rating_token', '')
        rate_url = f"{base_url.rstrip('/')}/rate/{rating_token}" if rating_token else ''

        body = (template
            .replace('{salon_name}', salon_name)
            .replace('{client_name}', client_first)
            .replace('{date}', appt_date_fmt)
            .replace('{time}', start_time)
            .replace('{services}', service_names)
            .replace('{hours_before}', str(hours_before))
            .replace('{confirm_url}', confirm_url if msg_type['include_confirm_link'] else '')
            .replace('{cancel_url}', cancel_url if msg_type.get('include_cancel_link') else '')
            .replace('{rate_url}', rate_url if msg_type.get('include_rate_link') else '')
            .replace('{booking_url}', booking_url if msg_type.get('include_booking_link') else '')
        )

        if msg_type['include_confirm_link'] and not has_confirm_placeholder:
            body = body.rstrip() + '\n' + confirm_url

        if msg_type.get('include_cancel_link') and not has_cancel_placeholder:
            body = body.rstrip() + '\n' + cancel_url

        if msg_type.get('include_rate_link') and not has_rate_placeholder and rate_url:
            body = body.rstrip() + '\n' + rate_url

        if msg_type.get('include_booking_link') and not has_booking_placeholder and booking_url:
            body = body.rstrip() + '\n' + booking_url

        return body.strip()
