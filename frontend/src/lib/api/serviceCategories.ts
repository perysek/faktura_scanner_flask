import { api } from './client';
import type { CategoryServiceRow, ServiceCategory } from '../../types/service';

interface DeleteConflict {
  success: false;
  requires_confirmation: true;
  service_count: number;
  error: string;
}

/** `/api/services/categories*` (routes/api_routes.py:3537-3773). */
export const serviceCategoriesApi = {
  list: () => api.get<{ success: true; categories: ServiceCategory[] }>('/api/services/categories').then((r) => r.categories),

  get: (id: number) => api.get<{ success: true; category: ServiceCategory }>(`/api/services/categories/${id}`).then((r) => r.category),

  create: (values: { name: string; additional_description: string | null }) => api.post<{ success: true; id: number; message: string }>('/api/services/categories', values),

  update: (id: number, values: { name: string; additional_description: string | null }) => api.put<{ success: true; message: string }>(`/api/services/categories/${id}`, values),

  /** 409 (`requires_confirmation`) when the category still has linked
   * services and neither `force` nor `categoryOnly` was passed — caller must
   * re-issue with one of them, exactly like the original's two-button dialog. */
  delete: (id: number, opts: { force?: boolean; categoryOnly?: boolean } = {}) =>
    api.del<{ success: true; message: string } | DeleteConflict>(`/api/services/categories/${id}${opts.force ? '?force=true' : opts.categoryOnly ? '?category_only=true' : ''}`),

  servicesInCategory: (id: number) => api.get<{ success: true; services: CategoryServiceRow[]; category_name: string }>(`/api/services/categories/${id}/services`).then((r) => r.services),
};
