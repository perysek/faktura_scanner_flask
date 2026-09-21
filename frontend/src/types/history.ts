/** Types for Historia zdarzeń (audit log) — module-inventory.md's deferred
 * Faktury piece, `/historia`. Mirrors AuditRepository.get_all()'s SQL SELECT
 * column names exactly (routes/api_routes.py's GET /api/history returns the
 * row dict unmodified). */

export type HistoryEntityType =
  | 'invoice' | 'import' | 'appointment' | 'client' | 'client_preference' | 'employee' | 'employee_service'
  | 'service' | 'service_category' | 'seller' | 'seller_password' | 'login'
  | 'absence' | 'absence_limit' | 'absence_adjustment' | 'absence_category'
  | 'user' | 'role' | 'sms';

export type HistoryAction =
  | 'CREATE' | 'CREATE_MANUAL' | 'UPDATE' | 'DELETE' | 'DELETE_PERMANENT' | 'RESTORE' | 'IMPORT'
  | 'LOGIN' | 'LOGIN_FAILED' | 'LOGOUT' | 'PASSWORD_RESET_REQUESTED' | 'PASSWORD_RESET'
  | 'STATUS_CHANGE' | 'STATUS_CHANGED' | 'COMPLETE' | 'PRICE_CHANGE'
  | 'APPROVE' | 'APPROVE_FORCED' | 'REJECT' | 'CANCEL' | 'CANCEL_APPROVED' | 'CANCEL_APPROVED_OWN'
  | 'SMS_SENT' | 'CLIENT_RATING' | 'CLIENT_CONFIRMATION';

export interface HistoryEntry {
  id: number;
  entity_type: HistoryEntityType | string;
  entity_id: number | null;
  entity_label: string | null;
  invoice_id: number | null;
  action: HistoryAction | string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  user_id: number | null;
  user_name: string | null;
  /** DB column is `changed_at`, but AuditRepository.get_all() renames it to
   * `timestamp` in the row dict it returns (repositories/audit_repository.py)
   * — the API response key is `timestamp`, not `changed_at`. A prior version
   * of this port read `entry.changed_at`, a field this response has never
   * had, which silently rendered "—" for every row's date/time. */
  timestamp: string | null;
  invoice_number: string | null;
}
