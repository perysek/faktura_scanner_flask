import { api } from './client';
import type { InvoiceStatistics } from '../../types/dashboard';

interface StatisticsResponse {
  success: true;
  statistics: InvoiceStatistics;
}

/**
 * Client-side wrapper over routes/api_routes.py's invoice endpoints.
 * Only `statistics()` for now (consumed by DashboardPage) — the full
 * CRUD surface gets fleshed out here when the Faktury module itself is
 * built (module-inventory.md: next after Sprzedawcy/Usługi/Pracownicy).
 */
export const invoicesApi = {
  statistics: () => api.get<StatisticsResponse>('/api/invoices/statistics').then((r) => r.statistics),
};
