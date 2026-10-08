/** SMS shapes shared by Historia SMS (Oczekujące tab) and the visit page's "Wiadomości SMS" card.
 * Server: services/sms_queue_service.py. Every timestamp is Warsaw wall-clock ISO — render as is,
 * no client-side timezone maths (same contract as StatusHistoryResponse). */

export type SmsDeliveryStatus = 'pending' | 'sent' | 'delivered' | 'failed';

/** One message the scheduler will still send. */
export interface SmsPendingEntry {
  key: string;
  /** `before_visit`: derived every tick from the visit's start time. `queued_event`: an sms_events row. */
  kind: 'before_visit' | 'queued_event';
  type_key: string;
  type_name: string;
  /** The scheduler TICK that will carry the message (not the nominal due moment). */
  will_be_sent_at: string;
  /** True when the serving process has no scheduler anchor, so the time is rounded to a quarter hour. */
  estimated: boolean;
  /** False when the scheduler will NOT actually deliver this one (a phone number the sender refuses, a
   * disabled type, a deleted visit...). Such a row is still listed so staff can fix the cause, but its
   * time is not a promise and `note` says why. */
  deliverable: boolean;
  recipient_kind: 'client' | 'employee';
  recipient_name: string;
  /** The number the sender uses (E.164), or what is stored when it cannot be parsed. */
  phone_number: string | null;
  /** Why the number is unusable: nothing stored, or text the sender cannot parse. Absent from an older backend. */
  phone_problem?: 'missing' | 'invalid' | null;
  appointment_id: number | null;
  appointment_date: string | null;
  start_time: string | null;
  note: string | null;
}

/** GET /api/sms/pending */
export interface SmsPendingResponse {
  success: true;
  rows: SmsPendingEntry[];
  /** Every queued row, deliverable or not (paging is over this). */
  total: number;
  /** How many of `total` the scheduler will not deliver (`deliverable: false`). */
  undeliverable: number;
  offset: number;
  limit: number;
  /** False -> SMS are switched off, the scheduler's job returns at once and nothing is queued. */
  sms_active: boolean;
  next_tick_at: string | null;
  estimated: boolean;
}

/** One sent (or attempted) message of a single visit. */
export interface SmsSentEntry {
  id: number;
  sent_at: string | null;
  type_key: string;
  type_name: string;
  status: SmsDeliveryStatus;
  /** Staff member, or "System (auto)" for the scheduler. */
  sent_by: string | null;
  automatic: boolean;
  error_message: string | null;
}

/** One entry of the "Wyślij SMS" dropdown. */
export interface SmsSendType {
  type_key: string;
  name: string;
  available: boolean;
  /** Why it is greyed out (shown as a tooltip and under the label). */
  reason: string | null;
  already_sent: boolean;
}

/** GET /api/sms/appointment/<id>/overview */
export interface VisitSmsOverview {
  success: true;
  sent: SmsSentEntry[];
  pending: SmsPendingEntry[];
  pending_estimated: boolean;
  sms_active: boolean;
  /** The caller's role carries the `can_send_sms` flag. */
  can_send: boolean;
  send_types: SmsSendType[];
}
