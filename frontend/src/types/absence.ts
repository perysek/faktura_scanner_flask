/** Types for the Nieobecności (wnioski) module — Faza 2, "Wymaga audytu" list.
 * Mirrors routes/absence_routes.py field names. Scope note: this module ships
 * the self-service request flow (/moje-nieobecnosci) and the supervisor
 * "Wnioski" + "L4/Manualne" tabs (/nieobecnosci) — the "Kategorie" tab, the
 * per-conflict reassign/reschedule steps in the approve-conflict modal, the
 * read-only resolution-history view, and superuser hard-delete are
 * deliberately deferred (see implementation-log.md), same pattern as the
 * already-deferred absence↔Wizyty integration. */

export type AbsenceStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';

export interface AbsenceCategory {
  id: number;
  name: string;
  description: string | null;
  absence_full_day: boolean;
  is_tracked: boolean;
  count_period: string;
  resets_at: number | null;
  rolling_days: number | null;
  default_max_value: number;
  warning_threshold_pct: number;
  is_deleted?: boolean;
}

export interface AbsenceSupervisor {
  id: number;
  first_name: string;
  last_name: string;
  position: string | null;
}

export interface AbsenceRecord {
  id: number;
  employee_id: number;
  employee_name?: string;
  category_id: number;
  category_name: string;
  absence_full_day?: boolean;
  date_from: string;
  date_to: string;
  time_from: string | null;
  time_to: string | null;
  status: AbsenceStatus;
  source?: 'request' | 'manual';
  approver_name?: string;
  rejection_reason?: string | null;
  requested_at: string | null;
  responded_at?: string | null;
  notes?: string | null;
}

export interface AppointmentConflict {
  appointment_id: number;
  date: string;
  start_time: string;
  end_time: string;
  client_name: string | null;
  service_name: string | null;
}

export interface ApproveResult {
  status: 'approved' | 'conflict';
  conflicts?: AppointmentConflict[];
  employee_id?: number;
}

export interface BalanceCheckResult {
  ok: boolean;
  warning: boolean;
  message?: string;
  balance?: { has_limit: boolean; net_used: number; limit: number };
}
