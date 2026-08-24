/** Types for the Bilanse urlopowe module — Faza 2, "Wymaga audytu" list.
 * Mirrors routes/absence_balance_routes.py + services/absence_balance_service.py
 * field names exactly (net_used/limit/unit/pct/status/warning_threshold_pct),
 * ported from templates/absences/balances.html's inline JS. */

export type BalanceStatus = 'ok' | 'warning' | 'exceeded' | 'unlimited';

export interface AbsenceCategory {
  id: number;
  name: string;
  absence_full_day?: boolean;
}

export interface EmployeeAbsenceBalance {
  category_id: number;
  category_name: string;
  period_label: string | null;
  net_used: number;
  limit: number;
  unit: 'hours' | 'days';
  pct: number;
  status: BalanceStatus;
  warning_threshold_pct: number;
}

/** One (employee, category) row on the balances table — flattened from
 * `EmployeeAbsenceBalance` + the employee it belongs to, matching
 * `buildDetailedRows()`'s flattening in the original page. */
export interface AbsenceBalanceRow extends EmployeeAbsenceBalance {
  employee_id: number;
  employee_name: string;
}

export interface AbsenceAdjustment {
  id: number;
  category_name: string;
  delta_value: number;
  reason: string;
  period_label: string | null;
  created_at: string;
  created_by_name: string;
}
