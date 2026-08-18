import { api } from './client';
import type { FormaZatrudnienia } from '../../types/employee';

interface FormaRow {
  id: number;
  nazwa: string;
  uwagi: string | null;
  min_salary_required: boolean;
  granted_salary: boolean;
  commision_included: boolean; // sic — matches the backend's field name 1:1
}

/** `/api/formy-zatrudnienia*` (routes/api_routes.py:4613-…). */
export const formyZatrudnieniaApi = {
  list: (): Promise<FormaZatrudnienia[]> => api.get<{ success: true; formy: FormaRow[] }>('/api/formy-zatrudnienia').then((r) => r.formy.map((f) => ({ id: f.id, nazwa: f.nazwa, opis: f.uwagi }))),

  listFull: () => api.get<{ success: true; formy: FormaRow[] }>('/api/formy-zatrudnienia').then((r) => r.formy),

  get: (id: number) => api.get<{ success: true; forma: FormaRow }>(`/api/formy-zatrudnienia/${id}`).then((r) => r.forma),

  create: (values: Omit<FormaRow, 'id'>) => api.post<{ success: true; id: number; message: string }>('/api/formy-zatrudnienia', values),

  update: (id: number, values: Omit<FormaRow, 'id'>) => api.put<{ success: true; message: string }>(`/api/formy-zatrudnienia/${id}`, values),

  delete: (id: number) => api.del<{ success: true; message: string }>(`/api/formy-zatrudnienia/${id}`),
};
