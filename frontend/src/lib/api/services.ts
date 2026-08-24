import { api } from './client';
import type { AddonRule, CompatibleAddon, Service, ServiceFormValues, ServicePriceHistoryEntry, ServiceStatistics } from '../../types/service';

interface ServicesListResponse {
  success: true;
  services: Service[];
  count: number;
}

interface ServiceResponse {
  success: true;
  service: Service;
}

/** `/api/services*` (routes/api_routes.py:3126-3773) + service-addon
 * compatibility endpoints, which live in a SEPARATE blueprint
 * (routes/service_addon_routes.py, mounted under the same /api/services/*
 * prefix) — not mentioned anywhere in module-inventory.md's audit. */
export const servicesApi = {
  list: (params: { search?: string; type?: string; activeOnly?: boolean } = {}) =>
    api
      .get<ServicesListResponse>('/api/services', {
        search: params.search,
        type: params.type,
        active_only: params.activeOnly === undefined ? undefined : String(params.activeOnly),
      })
      .then((r) => r.services),

  get: (id: number) => api.get<ServiceResponse>(`/api/services/${id}`).then((r) => r.service),

  create: (values: ServiceFormValues) => api.post<{ success: true }>('/api/services', values),

  update: (id: number, values: ServiceFormValues) => api.put<{ success: true; message: string }>(`/api/services/${id}`, values),

  delete: (id: number) => api.del<{ success: true; message: string; restore_url: string }>(`/api/services/${id}`),

  restore: (id: number) => api.post<{ success: true; message: string }>(`/api/services/${id}/restore`),

  statistics: () => api.get<{ success: true; statistics: ServiceStatistics }>('/api/services/statistics').then((r) => r.statistics),

  priceHistory: (id: number) => api.get<{ success: true; history: ServicePriceHistoryEntry[] }>(`/api/services/${id}/price-history`).then((r) => r.history),

  deletePriceHistoryEntry: (serviceId: number, entryId: number) =>
    api.del<{ success: true; message: string; reopened: boolean; new_price?: number; currency?: string }>(`/api/services/${serviceId}/price-history/${entryId}`),

  // service_addon_routes.py
  compatibleAddons: (serviceId: number, explicitOnly = false) =>
    api.get<{ success: true; addons: CompatibleAddon[]; count: number }>(`/api/services/${serviceId}/compatible-addons`, { explicit_only: explicitOnly ? 'true' : undefined }).then((r) => r.addons),

  allAddonServices: () => api.get<{ success: true; addons: CompatibleAddon[] }>('/api/services/addons').then((r) => r.addons),

  addonRules: (addonServiceId: number) => api.get<{ success: true; rules: AddonRule[] }>(`/api/services/${addonServiceId}/addon-rules`).then((r) => r.rules),

  setCompatibility: (addonServiceId: number, mainServiceIds: number[]) =>
    api.put<{ success: true }>(`/api/services/${addonServiceId}/compatibility`, { main_service_ids: mainServiceIds }),
};
