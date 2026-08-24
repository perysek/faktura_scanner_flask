import { api } from './client';
import type { SellerPdfPassword, SellerPdfPasswordFormValues } from '../../types/seller';

/** Client-side wrapper over `/api/seller-passwords*` (routes/api_routes.py:2431-2556) —
 * already had @login_required + @module_permission_required('invoices') on
 * every endpoint before this port (unlike sellers/dashboard — no gap here). */
export const sellerPasswordsApi = {
  getAll: () => api.get<{ success: true; passwords: SellerPdfPassword[] }>('/api/seller-passwords'),

  getForSeller: (sellerId: number) => api.get<{ success: true; password: SellerPdfPassword | null }>(`/api/seller-passwords/for-seller/${sellerId}`),

  create: (values: SellerPdfPasswordFormValues) => api.post<{ success: true; id: number }>('/api/seller-passwords', values),

  update: (id: number, values: SellerPdfPasswordFormValues) => api.put<{ success: true }>(`/api/seller-passwords/${id}`, values),

  delete: (id: number) => api.del<{ success: true }>(`/api/seller-passwords/${id}`),
};
