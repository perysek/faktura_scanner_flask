/** Types for the Pracownicy module — Faza 2. Największy moduł dotąd:
 * lista, create/edit (z mobile-pin i pickerem podwładnych), szczegóły
 * (dane + bilanse nieobecności + umiejętności/specjalizacje + harmonogram +
 * przypisane usługi — zakładki Analizy i wyniki ŚWIADOMIE odłożone, patrz
 * implementation-log.md), formy zatrudnienia. */

export type EmploymentStatus = 'active' | 'on_leave' | 'terminated';

export interface Employee {
  id: number;
  user_id: number | null;
  forma_zatrudnienia_id: number | null;
  full_name: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  position: string | null;
  employment_status: EmploymentStatus;
  hire_date: string | null;
  termination_date: string | null;
  base_salary: number | null;
  commission_rate: number | null;
  employer_cost_rate: number;
  skills: Record<string, number> | null;
  specializations: string[] | null;
  work_schedule: Record<string, string> | null;
  max_appointments_per_day: number;
  notes: string | null;
  photo_path: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** Row shape from GET /api/employees (list) — a different, wider projection
 * than GET /api/employees/<id> (adds satisfaction/monthly-coverage stats,
 * drops skills/specializations/work_schedule/notes). */
export interface EmployeeListRow {
  id: number;
  user_id: number | null;
  full_name: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  position: string | null;
  employment_status: EmploymentStatus;
  hire_date: string | null;
  termination_date: string | null;
  base_salary: number | null;
  commission_rate: number | null;
  is_active: boolean;
  created_at: string | null;
  avg_satisfaction: number | null;
  rated_count: number;
  scheduled_this_month: number;
  completed_this_month: number;
  schedule_coverage_pct: number | null;
}

export interface EmployeeFormValues {
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  position: string | null;
  hire_date: string | null;
  employment_status: EmploymentStatus;
  forma_zatrudnienia_id: number | null;
  user_id: number | null;
  photo_path: string | null;
  base_salary: number | null;
  commission_rate: number | null;
  employer_cost_rate: number;
  max_appointments_per_day: number;
  work_schedule: Record<string, string> | null;
  notes: string | null;
  is_active?: boolean;
  skills?: Record<string, number> | null;
  specializations?: string[] | null;
}

export interface EmployeeStatistics {
  total_employees?: number;
  active_employees?: number;
  avg_salary?: number;
}

export interface UserOption {
  id: number;
  full_name: string;
  email: string;
}

export interface FormaZatrudnienia {
  id: number;
  nazwa: string;
  opis?: string | null;
}

export interface MobilePinStatus {
  has_pin: boolean;
  pin_set_at: string | null;
  last_login_at: string | null;
}

export interface DirectReportsOption {
  id: number;
  first_name: string;
  last_name: string;
  position: string | null;
}

export interface DirectReportsData {
  other_employees: DirectReportsOption[];
  current_direct_report_ids: number[];
  my_supervisor_ids: number[];
}

/** GET /api/absence-balances/summary — keyed by employee id (string keys in
 * the raw JSON object). */
export interface BalanceSummaryEntry {
  status: 'ok' | 'warning' | 'exceeded' | 'unlimited';
  used: number;
  limit?: number;
  unit: 'days' | 'hours';
}

export interface EmployeeBalance {
  category_id: number;
  category_name: string;
  unit: 'days' | 'hours';
  has_limit: boolean;
  limit: number | null;
  net_used: number;
  pct: number;
  status: 'ok' | 'warning' | 'exceeded' | 'unlimited';
  period_start: string | null;
}

export interface BalanceAdjustment {
  id: number;
  category_name: string;
  delta_value: number;
  reason: string;
  created_by_name: string | null;
  created_at: string | null;
}

/** GET /api/employees/<id>/services — dual pricing (custom vs default). */
export interface EmployeeServiceAssignment {
  id: number;
  service_id: number;
  service_name: string;
  service_category: string | null;
  custom_price: number | null;
  commission_rate: number | null;
  duration_override: number | null;
  effective_price: number | null;
  effective_commission: number | null;
  effective_duration: number | null;
  skill_rating?: number | null;
  is_active?: boolean;
}
