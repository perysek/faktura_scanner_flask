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

/** `GET /api/income/ledger` — strona Finanse → Przychody (routes/income_routes.py
 * `get_income_ledger`, repositories/appointments/income_repository.py `get_ledger`
 * / `get_lost_summary`). `gross_amount` = kwota zapłacona przez klienta (po
 * rabacie); `net_amount` = brutto − `employee_share` (prowizja pracownika). */
export interface IncomeLedgerRecord {
  id: number;
  appointment_id: number;
  /** Data wpływu, YYYY-MM-DD. */
  payment_date: string;
  appointment_date: string;
  client_id: number;
  client_name: string;
  employee_id: number;
  employee_name: string;
  gross_amount: number;
  employee_share: number;
  net_amount: number;
  payment_method: string | null;
  is_new_client: boolean;
}

export interface IncomeLostBucket {
  visits: number;
  amount: number;
}

export interface IncomeLedgerStats {
  count: number;
  total_gross: number;
  total_net: number;
  avg_gross: number;
  new_client_gross: number;
  new_client_visits: number;
  new_client_pct: number;
  lost: {
    client_cancel: IncomeLostBucket;
    no_show: IncomeLostBucket;
    salon_cancel: IncomeLostBucket;
    visits: number;
    amount: number;
  };
}

export interface IncomeLedgerResponse {
  success: true;
  start_date: string;
  end_date: string;
  records: IncomeLedgerRecord[];
  stats: IncomeLedgerStats;
}
