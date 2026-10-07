import { api } from './client';
import type { VisitSmsOverview } from '../../types/sms';

/** The visit page's SMS card — routes/sms_routes.py. Sending reuses the long-standing
 * `POST /api/sms/send` (role flag `can_send_sms`, `SmsService.send`: a disabled type, a missing phone
 * or an "only confirmed" type on an unconfirmed visit is refused with a readable message). */
export const visitSmsApi = {
  overview: (appointmentId: number) => api.get<VisitSmsOverview>(`/api/sms/appointment/${appointmentId}/overview`),

  send: (appointmentId: number, messageTypeKey: string) =>
    api.post<{ success: boolean; message: string; reminder_id?: number }>('/api/sms/send', {
      appointment_id: appointmentId,
      message_type_key: messageTypeKey,
    }),
};
