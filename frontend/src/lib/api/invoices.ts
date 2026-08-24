import { api } from './client';
import type { InvoiceStatistics } from '../../types/dashboard';
import type { Invoice, InvoiceSaveSuccess, InvoiceSyncItem } from '../../types/invoice';

interface StatisticsResponse {
  success: true;
  statistics: InvoiceStatistics;
}

interface InvoicesListResponse {
  success: true;
  invoices: Invoice[];
  count: number;
}

interface InvoiceResponse {
  success: true;
  invoice: Invoice;
}

interface SyncCheckResponse {
  success: true;
  unlinked: InvoiceSyncItem[];
  wrong_link: InvoiceSyncItem[];
  total: number;
}

interface SyncApplyResponse {
  success: true;
  message: string;
  updated_count: number;
}

/**
 * Client-side wrapper over routes/api_routes.py's invoice endpoints
 * (module-inventory.md: piąty moduł Fazy 2). `create`/`confirmSeller` cover
 * the seller-conflict resubmit dance (409 → user decides → resubmit with
 * `seller_action`/`confirm-seller`) 1:1 z templates/invoices/{create,edit}.html —
 * patrz FakturaFormPage.tsx dla przepływu.
 */
export const invoicesApi = {
  statistics: () => api.get<StatisticsResponse>('/api/invoices/statistics').then((r) => r.statistics),

  list: (search?: string) => api.get<InvoicesListResponse>('/api/invoices', { search }),

  get: (id: number) => api.get<InvoiceResponse>(`/api/invoices/${id}`).then((r) => r.invoice),

  /** POST /api/invoices — always multipart (FormData), even with no file
   * selected, so `seller_action`/`existing_seller_id` (appended on a 409
   * resubmit, see FakturaFormPage.tsx) travel the exact same way the
   * original create.html's fetch() did. A seller conflict comes back as a
   * genuine HTTP 409 (routes/api_routes.py:423-442) — `api`'s wrapper throws
   * an `ApiError` for that, so the caller catches it and reads the
   * structured payload off `err.data as InvoiceConflictResponse` (client.ts's
   * `ApiError.data`), not off a resolved value. */
  create: (formData: FormData) => api.post<InvoiceSaveSuccess>('/api/invoices', formData),

  /** PUT /api/invoices/<id> — plain JSON (edit.html never re-uploads the
   * PDF; only create.html has a file input). Same 409-as-`ApiError.data`
   * contract as `create`. */
  update: (id: number, values: Record<string, unknown>) => api.put<InvoiceSaveSuccess>(`/api/invoices/${id}`, values),

  /** PUT /api/invoices/<id>/confirm-seller — the resubmit step after a PUT
   * above returned 409 (routes/api_routes.py:724-832). */
  confirmSeller: (id: number, action: 'create_new' | 'use_existing' | 'update_seller', invoiceData: Record<string, unknown>, existingSellerId?: number) =>
    api.put<InvoiceSaveSuccess>(`/api/invoices/${id}/confirm-seller`, { action, invoice_data: invoiceData, existing_seller_id: existingSellerId }),

  delete: (id: number) => api.del<{ success: true; message?: string }>(`/api/invoices/${id}`),

  restore: (id: number) => api.post<{ success: true; message?: string }>(`/api/invoices/${id}/restore`),

  sellerSyncCheck: () => api.get<SyncCheckResponse>('/api/invoices/seller-sync-check'),

  sellerSyncApply: (updates: Array<{ invoice_id: number; seller_id: number }>) =>
    api.post<SyncApplyResponse>('/api/invoices/seller-sync-apply', { updates }),

  /** GET /api/export/<format> — plain file download, no fetch/blob dance
   * needed (routes/api_routes.py:1292-1327 returns `send_file(...,
   * as_attachment=True)`); the browser handles the Content-Disposition
   * itself. Not routed through the `api` wrapper (that always expects a
   * JSON response body) — a direct navigation, 1:1 with the original
   * `API.export.toExcel()`'s `window.location.href` assignment. */
  exportUrl: (format: 'excel' | 'csv') => `/api/export/${format}`,

  /** GET /api/pdf/<id> — streams the stored PDF/image inline (same-origin
   * session cookie covers auth; no wrapper needed, this is a plain link
   * target for `<a target="_blank">`/`<iframe src>`, never fetched as JSON). */
  pdfUrl: (id: number) => `/api/pdf/${id}`,
};
