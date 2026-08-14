import { api } from './client';
import type {
  Client,
  ClientAppointmentHistoryItem,
  ClientPreference,
  ClientStatistics,
  DuplicateMatch,
  VisitTrends,
} from '../../types/client';

interface ClientsListResponse {
  success: true;
  clients: Client[];
  count: number;
}

interface ClientResponse {
  success: true;
  client: Client;
}

interface DuplicateCheckResponse {
  success: true;
  matches: DuplicateMatch[];
  count: number;
}

interface VisitTrendsResponse {
  success: true;
  trends: Record<string, number[]>;
}

interface StatisticsResponse {
  success: true;
  statistics: ClientStatistics;
}

interface PreferencesResponse {
  success: true;
  preferences: ClientPreference[];
  count: number;
}

interface AppointmentsResponse {
  success: true;
  appointments: ClientAppointmentHistoryItem[];
  count: number;
}

export interface ClientFormValues {
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  date_of_birth: string | null;
  notes: string | null;
  is_active?: boolean;
}

/** Client-side wrapper over routes/api_routes.py's client endpoints
 * (phase-01-pilot-clients.md §1.1) — 1:1, no new backend needed. */
export const clientsApi = {
  list: (params: { search?: string; includeInactive?: boolean } = {}) =>
    api
      .get<ClientsListResponse>('/api/clients', {
        search: params.search,
        include_inactive: params.includeInactive,
      })
      .then((r) => r.clients),

  get: (id: number) => api.get<ClientResponse>(`/api/clients/${id}`).then((r) => r.client),

  duplicateCheck: (params: { firstName: string; lastName: string; phone: string; excludeId?: number }) =>
    api
      .get<DuplicateCheckResponse>('/api/clients/duplicate-check', {
        first_name: params.firstName,
        last_name: params.lastName,
        phone: params.phone,
        exclude_id: params.excludeId,
      })
      .then((r) => r.matches),

  create: (values: ClientFormValues) => api.post<{ success: true; client_id: number }>('/api/clients', values),

  update: (id: number, values: ClientFormValues) => api.put<{ success: true }>(`/api/clients/${id}`, values),

  delete: (id: number) => api.del<{ success: true; restore_url: string }>(`/api/clients/${id}`),

  restore: (id: number) => api.post<{ success: true }>(`/api/clients/${id}/restore`),

  activate: (id: number) => api.post<{ success: true }>(`/api/clients/${id}/activate`),

  deactivate: (id: number) => api.post<{ success: true }>(`/api/clients/${id}/deactivate`),

  bulkUpdatePreferences: () =>
    api.post<{ success: true; updated_count: number; total_count: number }>('/api/clients/bulk-update-preferences'),

  visitTrends: (): Promise<VisitTrends> =>
    api.get<VisitTrendsResponse>('/api/clients/visit-trends').then((r) => {
      const trends: VisitTrends = {};
      for (const [key, value] of Object.entries(r.trends)) {
        trends[Number(key)] = value;
      }
      return trends;
    }),

  statistics: () => api.get<StatisticsResponse>('/api/clients/statistics').then((r) => r.statistics),

  preferences: (clientId: number) =>
    api.get<PreferencesResponse>(`/api/clients/${clientId}/preferences`).then((r) => r.preferences),

  addPreference: (clientId: number, payload: { service_id: number | null; preferred_employee_id: number; notes: string | null }) =>
    api.post<{ success: true; id: number }>(`/api/clients/${clientId}/preferences`, payload),

  removePreference: (clientId: number, prefId: number) =>
    api.del<{ success: true }>(`/api/clients/${clientId}/preferences/${prefId}`),

  appointmentHistory: (clientId: number, limit = 50) =>
    api
      .get<AppointmentsResponse>(`/api/clients/${clientId}/appointments`, { limit })
      .then((r) => r.appointments),
};
