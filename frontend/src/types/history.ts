/** Types for Historia zdarzeń (audit log) — module-inventory.md's deferred
 * Faktury piece, `/historia`. Mirrors AuditRepository.get_all()'s SQL SELECT
 * column names exactly (routes/api_routes.py's GET /api/history returns the
 * row dict unmodified). */

export type HistoryEntityType = 'invoice' | 'import' | 'appointment' | 'client' | 'employee' | 'service' | 'seller' | 'login';

export type HistoryAction = 'CREATE' | 'UPDATE' | 'DELETE' | 'IMPORT' | 'LOGIN' | 'LOGIN_FAILED' | 'LOGOUT' | 'STATUS_CHANGE' | 'COMPLETE' | 'PRICE_CHANGE';

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
  /** DB column is `changed_at`, NOT `timestamp` — the original page's JS read
   * `entry.timestamp` (a field that has never existed in this response),
   * which silently rendered "—" for every row's date/time. Fixed here rather
   * than ported forward; see implementation-log.md. */
  changed_at: string | null;
  invoice_number: string | null;
}
