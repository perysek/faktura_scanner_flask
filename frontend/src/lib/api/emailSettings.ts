import { api } from './client';
import type { EmailSettings } from '../../types/settings';

/** `/api/email/*` (routes/api_routes.py:1493-1601) — already fully JSON
 * before this migration, no backend changes needed. */
export const emailSettingsApi = {
  get: () => api.get<{ success: true; settings: EmailSettings }>('/api/email/settings').then((r) => r.settings),

  save: (values: EmailSettings) => api.post<{ success: true; message: string }>('/api/email/settings', values),

  test: (values: EmailSettings) => api.post<{ success: boolean; error?: string; message?: string }>('/api/email/test', values),
};
