/** `GET /api/income/summary` — routes/income_routes.py:59-83, already fully
 * JSON (income_bp mounted under /api, no backend changes needed). Field
 * names copied verbatim from repositories/appointments/income_repository.py's
 * `get_monthly_summary`/`get_employee_summary` SQL column aliases — not
 * guessed from the legacy templates/income/dashboard.html JS, which only
 * reads them off the parsed response without ever declaring a shape. */

export interface IncomeMonthlySummary {
  total_appointments: number;
  total_revenue: number;
  total_discounts: number;
  total_net: number;
  total_commissions: number;
  avg_ticket: number;
}

export interface IncomeEmployeeSummary {
  employee_id: number;
  employee_name: string;
  appointment_count: number;
  total_revenue: number;
  net_revenue: number;
  total_commission: number;
}

export interface IncomeSummaryResponse {
  success: boolean;
  summary: IncomeMonthlySummary;
  by_employee: IncomeEmployeeSummary[];
  year: number;
  month: number;
}
