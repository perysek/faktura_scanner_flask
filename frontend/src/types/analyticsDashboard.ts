/** Types for the "Analiza biznesowa" dashboard (/analiza-biznesowa) — ported from
 * `templates/analytics/dashboard.html` + `static/js/analytics/dashboard.js` on the
 * `invoices-app` branch. Field names mirror `repositories/analytics/analytics_repository.py`
 * exactly. Backend (`routes/analytics_routes.py`, blueprint mounted under `/api`) is already
 * fully JSON — no server changes for this page. */

export type AnalyticsPeriod = 'current_month' | 'last_month' | 'current_year' | 'custom';

export interface PeriodParams {
  period: AnalyticsPeriod;
  startDate: string | null;
  endDate: string | null;
}

export interface AnalyticsSummaryCurrent {
  start_date: string;
  end_date: string;
  total_appointments: number;
  unique_clients: number;
  total_revenue: number;
  avg_ticket: number;
  total_commissions: number;
}

export interface AnalyticsSummaryChange {
  revenue_pct: number;
  appointments_pct: number;
  clients_pct: number;
  avg_ticket_pct: number;
  commissions_pct: number;
}

export interface AnalyticsSummaryResponse {
  success: true;
  period: string;
  current: AnalyticsSummaryCurrent;
  previous: (AnalyticsSummaryCurrent & { start_date: string | null; end_date: string | null }) | null;
  change: AnalyticsSummaryChange | null;
}

export interface RevenueTrendPoint {
  date: string;
  revenue: number;
}

export interface RevenueTrendResponse {
  success: true;
  data: RevenueTrendPoint[];
  summary: { total: number; avg_daily: number };
}

export interface EmployeePerformance {
  id: number;
  employee_name: string;
  base_salary: number;
  cost_rate: number;
  appointments_count: number;
  revenue_generated: number;
  commission_earned: number;
  gross_salary: number;
  total_employer_cost: number;
  net_profit: number;
  avg_satisfaction: number | null;
}

export interface ServiceBreakdown {
  service_name: string;
  category: string | null;
  times_booked: number;
  revenue_generated: number;
}

export interface AtRiskClient {
  id: number;
  client_name: string;
  last_visit_date: string;
  days_since_visit: number;
}

export interface ClientMetrics {
  new_clients: number;
  returning_clients: number;
  retention_rate: number | null;
  at_risk_clients: AtRiskClient[];
}

export interface ProfitBreakdown {
  success: true;
  revenue: number;
  employee_costs: number;
  invoice_costs: number;
  gross_profit: number;
  net_profit: number;
  profit_margin_pct: number;
  invoice_details: { invoice_count: number; unpaid_count: number; unpaid_amount: number };
  change: { net_profit_pct: number } | null;
}

export interface OccupancyStats {
  success: true;
  completed: number;
  cancelled: number;
  no_shows: number;
  total_scheduled: number;
  booked_hours: number;
  theoretical_capacity: number;
  occupancy_rate: number;
  cancellation_rate: number;
  no_show_rate: number;
}

/** day_of_week: 0=Nd(Sun)..6=Sb(Sat) — Postgres EXTRACT(DOW), matches legacy heatmap. */
export interface PeakHourCell {
  day_of_week: number;
  hour_of_day: number;
  appointment_count: number;
  revenue: number;
}

export interface ServicePriceAnalysis {
  service_name: string;
  category: string | null;
  catalogue_price: number;
  bookings: number;
  avg_charged: number;
  min_charged: number;
  total_revenue: number;
  avg_discount_pct: number;
  last_price_change: string | null;
  price_at_period_start: number | null;
}

export interface MonthlyTrendPoint {
  month_start: string;
  revenue: number;
  employee_costs: number;
  invoice_costs: number;
  profit: number;
}

export interface TopClient {
  client_name: string;
  visits: number;
  revenue: number;
  score: number;
}

export interface BusinessInsight {
  type: 'alert' | 'warning' | 'success' | 'info';
  title: string;
  message: string;
}

export interface RollingNewClientsPoint {
  month_start: string;
  new_clients: number;
}

export interface RollingCancellationPoint {
  month_start: string;
  total: number;
  cancelled_count: number;
  noshow_count: number;
  cancellation_pct: number;
  noshow_pct: number;
}

export interface RollingAvgTicketPoint {
  month_start: string;
  avg_ticket: number;
}

export interface RollingCategoryMixRow {
  month_start: string;
  category: string;
  revenue: number;
}

export interface RollingCostRatioPoint {
  month_start: string;
  revenue: number;
  invoice_costs: number;
  ratio_pct: number;
}

/** utilisation_pct is null where available_hours is 0 (not yet hired / already left
 * / fully absent that month) — row still emitted so the month×employee grid stays complete. */
export interface RollingEmployeeUtilisationRow {
  month_start: string;
  employee_name: string;
  booked_hours: number;
  available_hours: number;
  utilisation_pct: number | null;
}

export interface RollingVisitFrequencyPoint {
  visit_count: number;
  client_count: number;
}

export interface RollingSatisfactionOverallPoint {
  month_start: string;
  avg_score: number | null;
  scored_count: number;
}

export interface RollingSatisfactionByEmployeePoint {
  month_start: string;
  employee_name: string;
  avg_score: number | null;
  scored_count: number;
}

export interface RollingSatisfactionResponse {
  success: true;
  overall: RollingSatisfactionOverallPoint[];
  by_employee: RollingSatisfactionByEmployeePoint[];
}
