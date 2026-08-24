/**
 * Types for the dashboard widgets (`/api/dashboard/*`, `/api/invoices/statistics`)
 * — Faza 2, moduł Dashboard/Pulpit. Only the fields the widgets actually read;
 * `database.models.Invoice` has more (pdf_path, ocr_confidence, …) not needed here.
 */
export interface DashboardInvoice {
  id: number;
  seller_name: string | null;
  invoice_number: string | null;
  amount: number | null;
  currency: string | null;
  status: string | null;
  payment_due_date: string | null;
}

export interface InvoiceStatistics {
  total_invoices?: number;
  paid_invoices?: number;
  unpaid_invoices?: number;
  totals?: { total_amount?: number };
}

export interface TopSeller {
  id: number;
  seller_nip: string | null;
  seller_name: string | null;
  invoice_count: number;
  total_amount: number;
}

export interface MonthlyTotals {
  labels: string[];
  data: number[];
  months: string[];
}
