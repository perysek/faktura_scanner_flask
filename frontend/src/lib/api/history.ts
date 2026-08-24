import { api } from './client';
import type { HistoryEntry } from '../../types/history';

/** GET /api/history (routes/api_routes.py, api_bp mounted under /api —
 * already fully JSON, no backend changes needed). No server-side filtering
 * used here (the original page fetches everything once and filters
 * client-side by tab) — same approach kept, entity_type param exists but
 * both the original and this port always call it unfiltered. */
export const historyApi = {
  list: () => api.get<{ success: true; entries: HistoryEntry[]; count: number }>('/api/history').then((r) => r.entries),
};
