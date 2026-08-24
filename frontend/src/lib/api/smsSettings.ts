import { api } from './client';
import type { SmsLogEntry, SmsMessageType, SmsSettings, SmsSettingsBundle } from '../../types/settings';

export interface MessageTypeSaveValues {
  name: string;
  is_enabled: boolean;
  send_hours_before: number;
  send_delay_minutes: number;
  template_text: string;
  include_confirm_link: boolean;
  include_cancel_link: boolean;
  include_rate_link: boolean;
  include_booking_link: boolean;
  send_only_if_confirmed: boolean;
}

export interface MessageTypeCreateValues {
  name: string;
  send_hours_before: number;
  template_text: string;
  include_confirm_link: boolean;
  include_cancel_link: boolean;
  include_booking_link: boolean;
}

/** `/api/sms/*` — `stats`/`send`/`bulk-send`/appointment-log already existed
 * (routes/sms_routes.py); the settings/credentials/message-type/log endpoints
 * below are new JSON siblings of the form-POST routes the legacy Jinja page
 * (templates/settings/sms.html) still uses — additive, that page untouched. */
export const smsSettingsApi = {
  get: () => api.get<{ success: true } & SmsSettingsBundle>('/api/sms/settings'),

  saveCredentials: (values: Partial<SmsSettings>) => api.put<{ success: true; message: string }>('/api/sms/credentials', values),

  test: (values: { account_sid: string; auth_token: string; from_number: string; to_number: string; messaging_service_sid?: string | null }) =>
    api.post<{ success: boolean; result: string }>('/settings/sms/test', values),

  saveMessageType: (id: number, values: MessageTypeSaveValues) => api.put<{ success: true; message: string }>(`/api/sms/message-types/${id}`, values),

  createMessageType: (values: MessageTypeCreateValues) => api.post<{ success: true; id: number }>('/api/sms/message-types', values),

  deleteMessageType: (id: number) => api.del<{ success: boolean; message?: string }>(`/api/sms/message-types/${id}`),

  log: (offset = 0, limit = 100) => api.get<{ success: true; rows: SmsLogEntry[]; offset: number; limit: number }>('/api/sms/log', { offset, limit }),
};

export type { SmsMessageType };
