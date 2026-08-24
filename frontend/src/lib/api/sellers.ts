import { api } from './client';
import type {
  DuplicateCheckResult,
  Seller,
  SellerConflictEntry,
  SellerGlobalStats,
  SellerInvoice,
  SyncResult,
} from '../../types/seller';

interface SellersListResponse {
  success: true;
  sellers: Seller[];
  count: number;
  global_stats: SellerGlobalStats;
}

interface SellerResponse {
  success: true;
  seller: Seller;
  invoices: SellerInvoice[];
  invoice_count: number;
}

export interface SellerFormValues {
  seller_nip: string;
  seller_name: string;
  address: string | null;
}

interface CreateSellerResponse {
  success: true;
  message: string;
  seller: Seller;
  already_exists?: boolean;
}

interface CreateSellerConflict {
  success: false;
  error: string;
  conflict_type: 'nip_exists_different_name' | 'name_exists_different_nip';
  existing_seller: { id: number; seller_nip: string; seller_name: string };
  proposed_name?: string;
  proposed_nip?: string;
  message: string;
}

/** Client-side wrapper over routes/api_routes.py's `/api/sellers/*` endpoints
 * (routes/api_routes.py:1716-2425). All now require @login_required +
 * @module_permission_required('invoices') — 11 of them had NO auth decorator
 * at all before this port (Odkrycie D-Sec2, implementation-log.md), including
 * `delete` — fixed alongside this build, not a pre-existing intentional gap. */
export const sellersApi = {
  list: (search?: string) => api.get<SellersListResponse>('/api/sellers', { search }),

  get: (id: number) => api.get<SellerResponse>(`/api/sellers/${id}`),

  create: (values: SellerFormValues) => api.post<CreateSellerResponse | CreateSellerConflict>('/api/sellers', values),

  update: (id: number, values: Partial<SellerFormValues>) => api.put<{ success: true; message: string; seller: Seller; changes: string[] }>(`/api/sellers/${id}`, values),

  delete: (id: number) =>
    api.del<{ success: true; message: string; deleted_invoices: Array<{ id: number; invoice_number: string }>; invoice_count: number }>(`/api/sellers/${id}`),

  bulkUpdate: (id: number) => api.post<{ success: true; message: string; updated_count: number; total_invoices: number }>(`/api/sellers/${id}/bulk-update`),

  getInvoices: (id: number) => api.get<{ success: true; seller: Seller; invoices: SellerInvoice[]; count: number }>(`/api/sellers/${id}/invoices`),

  conflicts: () => api.get<{ success: true; conflicts: SellerConflictEntry[]; count: number }>('/api/sellers/conflicts'),

  checkDuplicate: (nip: string, name: string) => api.post<DuplicateCheckResult & { success: true }>('/api/sellers/check-duplicate', { nip, name }),

  sync: () => api.post<SyncResult & { success: true }>('/api/sellers/sync'),

  addMissing: (nip: string, name: string) => api.post<{ success: true; message: string; seller_id: number; linked_invoices: number }>('/api/sellers/sync/add-missing', { nip, name }),

  fixDiscrepancy: (action: 'use_seller_name' | 'use_invoice_name', invoiceId: number, sellerId: number) =>
    api.post<{ success: true; message: string }>('/api/sellers/sync/fix-discrepancy', { action, invoice_id: invoiceId, seller_id: sellerId }),

  syncInvoiceCounts: () => api.post<{ success: true; message: string; linked_count: number; updated_count: number }>('/api/sellers/sync/invoice-counts'),
};
