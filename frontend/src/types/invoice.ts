/** Types for the Faktury module — Faza 2 (module-inventory.md: piąty moduł,
 * najwyższa dotąd złożoność — patrz decyzja o zakresie w implementation-log.md).
 * Ported from `database.models.Invoice` (the full server-side dataclass) +
 * what `templates/invoices/{list_refined,create,edit}.html` actually read/write. */

export interface Invoice {
  id: number;
  invoice_number: string | null;
  seller_name: string | null;
  seller_nip: string | null;
  seller_id?: number | null;
  invoice_date: string | null;
  amount: number | null;
  currency: string | null;
  status: string | null;
  payment_due_date: string | null;
  payment_term: string | null;
  bank_account: string | null;
  pdf_path: string | null;
  pdf_filename?: string | null;
  ocr_confidence: number | null;
  is_duplicate?: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** Values collected by FakturaFormPage — both create and edit share this
 * shape; `seller_address` only exists on the wire for `create` (see
 * `Dane sprzedawcy` card in create.html — edit.html has no address field). */
export interface InvoiceFormValues {
  invoice_number: string;
  status: string;
  invoice_date: string;
  payment_due_date: string;
  payment_term: string;
  seller_name: string;
  seller_nip: string;
  bank_account: string;
  seller_address: string;
  amount: string;
  currency: string;
}

/** 409 shape from POST /api/invoices and PUT /api/invoices/<id> when the NIP
 * on the form already exists in `sellers` under a DIFFERENT name. */
export interface SellerConflict {
  existing_seller: { id: number; seller_nip: string; seller_name: string };
  proposed_name: string;
  conflict_type: 'name_mismatch';
  message: string;
}

/** 409 shape when the NIP on the form doesn't exist in `sellers` at all yet. */
export interface NewSellerInfo {
  new_seller: true;
  seller_nip: string;
  seller_name: string;
}

export interface InvoiceConflictResponse {
  success: false;
  error: string;
  message: string;
  seller_conflict?: SellerConflict;
  seller_info?: NewSellerInfo;
  validation_errors?: { errors?: string[]; warnings?: string[] };
}

export interface InvoiceSaveSuccess {
  success: true;
  message: string;
  invoice_id?: number;
  invoice?: Invoice;
  warnings?: string[];
  seller_id?: number;
}

/** GET /api/invoices/seller-sync-check item — one invoice needing a
 * seller_id link created or corrected (routes/api_routes.py:108-245). Not
 * the same feature as Sprzedawcy's own `/api/sellers/sync` (SyncResult,
 * types/seller.ts) — this one only ever proposes linking to an EXISTING
 * seller, never creating one, so it's a strictly simpler checkbox-apply flow. */
export interface InvoiceSyncItem {
  invoice_id: number;
  invoice_number: string | null;
  invoice_seller_name: string;
  invoice_nip: string;
  invoice_date: string | null;
  amount: number;
  currency: string | null;
  type: 'unlinked' | 'wrong_link';
  suggested_seller_id: number;
  suggested_seller_name: string;
  suggested_seller_nip: string;
  match_reason: 'NIP' | 'nazwa';
  current_seller_id?: number;
  current_seller_name?: string;
}
