import { api } from './client';
import type { DashboardInvoice, MonthlyTotals, TopSeller } from '../../types/dashboard';

interface InvoicesResponse {
  success: true;
  invoices: DashboardInvoice[];
  count: number;
}

interface TopSellersResponse {
  success: true;
  sellers: TopSeller[];
  count: number;
}

/**
 * Client-side wrapper over the five `/api/dashboard/*` widget endpoints
 * (routes/api_routes.py:937-1093). All five now require
 * `@login_required` + `@module_permission_required('invoices')` — added
 * 2026-08-17 during this port, see implementation-log.md (they had NO auth
 * decorator at all before that; a real, pre-existing gap unrelated to React).
 */
export const dashboardApi = {
  recentInvoices: (limit = 5) => api.get<InvoicesResponse>('/api/dashboard/recent-invoices', { limit }).then((r) => r.invoices),

  upcomingPayments: (limit = 5) => api.get<InvoicesResponse>('/api/dashboard/upcoming-payments', { limit }).then((r) => r.invoices),

  overduePayments: (limit = 5) => api.get<InvoicesResponse>('/api/dashboard/overdue-payments', { limit }).then((r) => r.invoices),

  topSellers: (limit = 5) => api.get<TopSellersResponse>('/api/dashboard/top-sellers', { limit }).then((r) => r.sellers),

  monthlyTotals: () => api.get<MonthlyTotals & { success: true }>('/api/dashboard/monthly-totals'),
};
