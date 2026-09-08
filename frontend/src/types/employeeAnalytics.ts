/** Types for the employee "Analizy i wyniki" tabs — ported from
 * `templates/employees/view.html` + `static/js/employees/analytics.js` on
 * the `invoices-app` branch (Flask/Jinja original). Field names mirror
 * `repositories/employees/employee_analytics_repository.py` and
 * `EmployeeServiceRepository.get_services_with_dual_ratings` exactly —
 * both repos are shared, unchanged, between that branch and this one. */

export interface EmployeeAnalyticsSummary {
  total_appointments: number;
  total_revenue: number;
  employer_cost: number;
  net_profit: number;
  avg_ticket: number;
}

export interface EmployeeRevenueTrendPoint {
  month: string;
  month_label: string;
  revenue: number;
  commission: number;
  appointments: number;
}

export interface EmployeeServiceMixItem {
  service_name: string;
  appointment_count: number;
  revenue: number;
}

/** day_of_week: 1=Mon..7=Sun (ISODOW). hour_of_day: 0-23. */
export interface EmployeePeakHourCell {
  day_of_week: number;
  hour_of_day: number;
  appointment_count: number;
}

export interface EmployeeClientSplitPoint {
  month: string;
  month_label: string;
  new_clients: number;
  returning_clients: number;
}

export interface EmployeeCommissionTrendPoint {
  month: string;
  month_label: string;
  base_salary: number;
  commission_earned: number;
  gross_salary: number;
}

/** GET /api/employees/<id>/services-with-ratings — dual rating (manual vs.
 * client-average) per assigned service. Manual `skill_rating` is edited
 * in-place via `employeeServicesApi.update(employeeId, es_id, { skill_rating })`. */
export interface EmployeeServiceRating {
  es_id: number;
  service_id: number;
  service_name: string;
  service_category: string | null;
  service_type: string;
  skill_rating: number | null;
  avg_client_rating: number | null;
  scored_visits: number;
}

export interface EmployeeSatisfactionCategory {
  category: string;
  avg_score: number | null;
  count: number;
}

export interface EmployeeSatisfactionTrendPoint {
  month: string;
  month_label: string;
  avg_score: number | null;
  count: number;
}

export interface EmployeeSatisfactionStats {
  avg_score: number | null;
  total_scored: number;
  /** Keys are '1'..'5' (JSON object keys are always strings). */
  distribution: Record<string, number>;
  by_service_category: EmployeeSatisfactionCategory[];
  monthly_trend: EmployeeSatisfactionTrendPoint[];
}
