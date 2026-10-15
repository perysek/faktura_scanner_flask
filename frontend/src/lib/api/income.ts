import { api } from './client';
import type { IncomeLedgerResponse, IncomeSummaryResponse } from '../../types/income';

/** `/api/income/summary` (routes/income_routes.py, income_bp mounted under
 * /api — already fully JSON, error responses included, no backend changes
 * needed). Server defaults year/month to "today" when omitted, but the page
 * always passes both explicitly (mirrors the legacy page's own behaviour —
 * it always sends both query params too). */
export const incomeApi = {
  summary: (year: number, month: number) => api.get<IncomeSummaryResponse>('/api/income/summary', { year, month }),

  /** `/api/income/ledger` — Finanse → Przychody: rekordy przychodu z okresu (wg
   * daty wpływu) + karty statystyk. Gated by the 'income' module. */
  ledger: (startDate: string, endDate: string) => api.get<IncomeLedgerResponse>('/api/income/ledger', { start_date: startDate, end_date: endDate }),
};
