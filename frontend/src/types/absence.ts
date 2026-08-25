/** Types for the Nieobecności (wnioski) module — Faza 2, "Wymaga audytu" list.
 * Mirrors routes/absence_routes.py field names. Scope note: this module ships
 * the self-service request flow (/moje-nieobecnosci) and the supervisor
 * "Wnioski" + "L4/Manualne" + "Kategorie" tabs (/nieobecnosci), superuser
 * hard-delete (absences + categories — D37), and — as of 2026-08-25 — the
 * per-conflict reassign/reschedule steps in the approve-conflict modal, the
 * read-only resolution-history view, and inline balance-hint annotations
 * next to employee names (see `pages/absences/ConflictResolutionModal.tsx`
 * and `BalanceSummaryEntry` below). Still out of scope: per-conflict
 * reassign/reschedule triggered from the Wizyty side — there never was a
 * separate entry point for that even in the legacy app; it's the same modal
 * this file now wires up, reachable only from the absence-approval flow. */

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

/** GET /api/absence-balances/summary row (keyed by employee_id in the
 * response) — `AbsenceBalanceService.get_balance_summary_for_list()`. Powers
 * the inline "(2.0/5d)" balance-hint next to an employee's name in the
 * Wnioski/L4-Manualne tables; a row's `category_id` must match the absence's
 * own category before the hint applies (an employee can have balances
 * tracked for more than one category — the summary only carries their
 * "primary" one). */
export interface BalanceSummaryEntry {
  category_id: number;
  category_name: string;
  unit: 'days' | 'hours';
  used: number;
  limit: number;
  pct: number;
  status: 'unlimited' | 'ok' | 'warning' | 'exceeded';
}

/** GET /absences/<id>/conflicts — live, re-fetched after every resolution
 * action; an empty array is the "Zatwierdź" unlock signal (AD-8). */
export interface LiveConflictsResult {
  success: true;
  conflicts: AppointmentConflict[];
}

/** GET /absences/<id>/resolutions row —
 * `AbsenceConflictResolutionRepository.list_for_absence()`. Read-only audit
 * trail shown by the "Historia rozwiązań →" link once any conflict on this
 * absence has been resolved. */
export interface ConflictResolution {
  id: number;
  resolution_type: 'reassigned' | 'rescheduled' | 'cancelled';
  client_name: string | null;
  service_name: string | null;
  previous_employee_name: string | null;
  new_employee_name: string | null;
  previous_date: string | null;
  previous_start_time: string | null;
  previous_end_time: string | null;
  new_date: string | null;
  new_start_time: string | null;
  new_end_time: string | null;
  cancellation_reason: string | null;
  resolved_by_name: string | null;
  /** Pre-formatted `dd.mm.YYYY HH:MM` — the backend formats this server-side,
   * not an ISO string to parse client-side. */
  resolved_at: string | null;
}
