import { api } from './client';
import type { ConflictApplyResult, ConflictScanResult, ImportHistoryRow, SessionStatusResponse } from '../../types/dataImport';

/** `/api/import/*` (routes/import_routes.py, import_bp mounted under /api —
 * already fully JSON, no backend changes needed). The SSE stream
 * (`/api/import/<id>/stream`) isn't wrapped here — it's consumed directly via
 * the native `EventSource` in DataImportPage, same as the original page. */
export const dataImportApi = {
  sessionStatus: () => api.get<SessionStatusResponse>('/api/import/session-status'),

  reconnectSession: () => api.post<{ status: 'active' }>('/api/import/reconnect-session'),

  start: (payload: { date_start: string; date_end: string; dry_run: boolean; keep_xlsx: boolean }) =>
    api.post<{ success: true; import_id: number }>('/api/import/start', payload),

  history: () => api.get<{ success: true; history: ImportHistoryRow[]; count: number }>('/api/import/history').then((r) => r.history),

  conflictScan: (dateStart: string, dateEnd: string) => api.get<ConflictScanResult>('/api/import/conflict-scan', { date_start: dateStart, date_end: dateEnd }),

  conflictScanApply: (dateStart: string, dateEnd: string) => api.post<ConflictApplyResult>('/api/import/conflict-scan/apply', { date_start: dateStart, date_end: dateEnd }),
};
