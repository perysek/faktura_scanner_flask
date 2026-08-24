/** Types for the Ustawienia e-mail/SMS module — Faza 2, "Wymaga audytu" list
 * (module-inventory.md). Two independent settings pages ported together:
 * IMAP email import config (routes/api_routes.py, fully JSON already) and
 * Twilio SMS config + message-type templates + send log (routes/sms_routes.py,
 * form-POST originally — new /api/sms/* JSON siblings added alongside it). */

export interface EmailSettings {
  imap_server: string;
  imap_port: number;
  email: string;
  password: string;
}

export interface SmsSettings {
  account_sid: string | null;
  auth_token: string | null;
  from_number: string | null;
  messaging_service_sid: string | null;
  is_active: boolean;
}

export interface SmsMessageType {
  id: number;
  type_key: string;
  name: string;
  is_enabled: boolean;
  is_custom: boolean;
  is_event_triggered: boolean;
  trigger_on_status: string | null;
  send_hours_before: number;
  send_delay_minutes: number | null;
  template_text: string;
  include_confirm_link: boolean;
  include_cancel_link: boolean;
  include_rate_link: boolean;
  include_booking_link: boolean;
  send_only_if_confirmed: boolean;
  sort_order: number;
}

export interface SmsStats {
  mtd1_total: number;
  mtd1_sent: number;
  mtd1_failed: number;
  mtd1_confirm_requests: number;
  mtd1_confirmed: number;
  mtd1_declined: number;
  mtd3_total: number;
  mtd3_sent: number;
  mtd3_failed: number;
  mtd3_confirm_requests: number;
  mtd3_confirmed: number;
  mtd3_declined: number;
}

export interface SmsSettingsBundle {
  settings: SmsSettings;
  message_types: SmsMessageType[];
  stats: SmsStats;
}

export interface SmsLogEntry {
  id: number;
  sent_at: string | null;
  status: 'pending' | 'sent' | 'delivered' | 'failed';
  type_name: string | null;
  message_type_key: string;
  client_name: string;
  phone_number: string;
  appointment_date: string;
  start_time: string;
  appt_confirmation_status: string | null;
  twilio_sid: string | null;
  created_by_name: string | null;
  error_message: string | null;
}
