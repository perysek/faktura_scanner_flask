/** Types for the Sprzedawcy module — Faza 2 (module-inventory.md korekta 2026-08-17:
 * trzy pod-funkcje — lista/CRUD, sync workflow, hasła PDF). */

export interface Seller {
  id: number;
  seller_nip: string;
  seller_name: string;
  address: string | null;
  first_seen: string | null;
  last_updated: string | null;
  invoice_count: number;
  actual_invoice_count?: number;
  total_paid?: number;
  total_unpaid?: number;
}

export interface SellerGlobalStats {
  total_invoices: number;
  total_paid: number;
  total_unpaid: number;
}

/** Invoice shape as embedded in GET /api/sellers/<id> (`invoices` array) —
 * ported from what edit.js's renderInvoicesTable()/list_refined.html actually
 * read off each row; not the full database.models.Invoice surface. */
export interface SellerInvoice {
  id: number;
  invoice_number: string | null;
  amount: number | null;
  currency: string | null;
  invoice_date: string | null;
  status: string | null;
  seller_name?: string | null;
}

export interface SellerConflictEntry {
  seller_id: number;
  seller_nip: string;
  seller_name: string;
  invoice_id: number;
  invoice_number: string;
  invoice_seller_name: string;
  conflict_type: string;
}

export interface MissingSeller {
  nip: string;
  name: string;
  count: number;
  invoices: Array<{ id: number; invoice_number: string }>;
}

export interface NameDiscrepancy {
  seller_id: number;
  seller_nip: string;
  seller_name: string;
  invoice_id: number;
  invoice_number: string;
  invoice_seller_name: string;
}

export interface SyncSummary {
  total_sellers: number;
  total_invoices: number;
  invoices_without_nip: number;
  missing_sellers_count: number;
  discrepancies_count: number;
}

export interface SyncResult {
  missing_sellers: MissingSeller[];
  name_discrepancies: NameDiscrepancy[];
  summary: SyncSummary;
}

export interface DuplicateCheckResult {
  nip_exists: boolean;
  name_exists: boolean;
  existing_by_nip: { id: number; seller_nip: string; seller_name: string } | null;
  existing_by_name: { id: number; seller_nip: string; seller_name: string } | null;
}

export interface SellerPdfPassword {
  id: number;
  seller_id: number | null;
  seller_name?: string | null;
  seller_nip?: string | null;
  email_sender_pattern: string | null;
  pdf_password: string;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SellerPdfPasswordFormValues {
  seller_id: number | null;
  email_sender_pattern: string | null;
  pdf_password: string;
  description: string | null;
}
