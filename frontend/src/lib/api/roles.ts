import { api } from './client';
import type { RoleDetail, RoleListRow, RolePermissionFlags } from '../../types/rbac';

export interface RoleCreatePayload {
  name: string;
  display_name: string;
  permissions: Record<string, boolean>;
}

export interface RoleUpdatePayload {
  display_name: string;
  permissions: Record<string, RolePermissionFlags>;
}

/** `/system/roles/api*` (routes/roles/routes.py) — same AppError-throws-on-
 * failure shape as usersApi (see its doc comment); callers catch `ApiError`. */
export const rolesApi = {
  list: () => api.get<{ roles: RoleListRow[]; count: number }>('/system/roles/api').then((r) => r.roles),

  get: (id: number) =>
    api.get<{ success: true; role: RoleDetail; permissions: Record<string, RolePermissionFlags>; all_modules: string[]; module_display_names: Record<string, string> }>(
      `/system/roles/api/${id}`,
    ),

  formOptions: () => api.get<{ success: true; all_modules: string[]; module_display_names: Record<string, string> }>('/system/roles/api/form-options'),

  create: (payload: RoleCreatePayload) => api.post<{ success: true; role_id: number }>('/system/roles/api', payload),

  update: (id: number, payload: RoleUpdatePayload) => api.put<{ success: true }>(`/system/roles/api/${id}`, payload),

  delete: (id: number) => api.del<{ success: true }>(`/system/roles/api/${id}`),
};
