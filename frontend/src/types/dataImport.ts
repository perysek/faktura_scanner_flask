/** Types for Import danych (caldis.pl Playwright import) — module-inventory.md's
 * "Import danych / historia / OCR upload" audit. Mirrors routes/import_routes.py +
 * services/visit_conflict_scan_service.py field names. Not invoice OCR (that's a
 * separate, already-deferred concern under the Faktury module) — this is an
 * admin-only tool that scrapes appointment bookings from caldis.pl. */

export interface ImportStats {
  inserted?: number;
  clients_created?: number;
  skipped_duplicate?: number;
  skipped_zero?: number;
  skipped_no_client?: number;
  skipped_no_employee?: number;
  errors?: number;
}

export type ImportRunStatus = 'completed' | 'running' | 'failed' | 'cancelled' | 'unknown';

export interface ImportHistoryRow {
  id: number;
  status: ImportRunStatus;
  stats: ImportStats;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  dry_run: boolean;
  triggered_by_user_id: number | null;
  triggered_by_name: string | null;
  session_status: string | null;
}

export type SessionStatus = 'active' | 'expired' | 'missing';

export interface SessionStatusResponse {
  status: SessionStatus;
  age_days: number | null;
}

export type SseEvent =
  | { type: 'log'; message: string; level?: 'info' | 'warning' | 'error' | 'progress' }
  | { type: 'stats'; stats: ImportStats }
  | { type: 'status'; status: ImportRunStatus }
  | { type: 'done'; status?: ImportRunStatus; stats?: ImportStats; error_message?: string };

export type ConflictReason = 'time_overlap' | 'same_day_different_stylist';

export interface ConflictAppointment {
  id: number;
  appointment_date: string;
  start_time: string;
  end_time: string;
  employee_name: string;
  status: string;
  total_price: number;
  is_keeper: boolean;
  planned_action: 'cancel' | 'soft_delete';
}

export interface ConflictGroup {
  client_name: string;
  service_name: string;
  keeper_id: number;
  reasons: ConflictReason[];
  appointments: ConflictAppointment[];
}

export interface ConflictScanResult {
  success: true;
  candidate_count: number;
  group_count: number;
  superseded_count: number;
  groups: ConflictGroup[];
}

export interface ConflictApplyResult {
  success: true;
  removed_count: number;
  cancelled_count: number;
  soft_deleted_count: number;
  group_count: number;
}
