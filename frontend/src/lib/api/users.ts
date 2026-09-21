import { api } from './client';
import type { AssignableRole, AvailableEmployee, LinkedEmployee, RolePermissionFlags, UserDetail, UserListRow } from '../../types/rbac';

export interface UserCreatePayload {
  email: string;
  full_name: string;
  password: string;
  role: string;
  employee_id: number;
  is_active: boolean;
}

export interface UserUpdatePayload {
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  /** `null` unlinks the employee; omitting the key leaves the link untouched. */
  employee_id?: number | null;
}

export interface UserDetailResponse {
  success: true;
  user: UserDetail;
  linked_employee: LinkedEmployee | null;
  /** The user's role, as module → flags (empty when the role row is gone). */
  permissions: Record<string, RolePermissionFlags>;
  module_display_names: Record<string, string>;
}

export interface UserFormOptions {
  success: true;
  available_employees: AvailableEmployee[];
  roles: AssignableRole[];
  module_display_names: Record<string, string>;
}

/** `/system/users/api*` (routes/users/routes.py) — CRUD already JSON;
 * `form-options`/single-`GET` are siblings added for the React forms.
 *
 * All failure paths raise an `AppError` subclass (ValidationError/
 * ConflictError/PermissionDeniedError/NotFoundError) rather than returning
 * `{success: false}` with a 200. Callers catch `ApiError` (thrown by the shared
 * `api.*` wrapper on any non-2xx response); `ApiError.message` carries the
 * precise Polish reason, e.g. the self-lockout and last-superuser refusals. */
export const usersApi = {
  list: () => api.get<{ users: UserListRow[]; count: number }>('/system/users/api').then((r) => r.users),

  get: (id: number) => api.get<UserDetailResponse>(`/system/users/api/${id}`),

  formOptions: () => api.get<UserFormOptions>('/system/users/api/form-options'),

  create: (payload: UserCreatePayload) => api.post<{ success: true; user_id: number }>('/system/users/api', payload),

  update: (id: number, payload: UserUpdatePayload) => api.put<{ success: true }>(`/system/users/api/${id}`, payload),

  changePassword: (id: number, newPassword: string) => api.put<{ success: true }>(`/system/users/api/${id}`, { new_password: newPassword }),

  delete: (id: number) => api.del<{ success: true }>(`/system/users/api/${id}`),

  toggleActive: (id: number) => api.put<{ success: true; is_active: boolean }>(`/system/users/api/${id}/toggle-active`),
};
