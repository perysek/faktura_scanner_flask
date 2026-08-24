import { api } from './client';
import type { AssignableRole, AvailableEmployee, LinkedEmployee, UserDetail, UserListRow } from '../../types/rbac';

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
  employee_id: number | null;
}

/** `/system/users/api*` (routes/users/routes.py) — CRUD already JSON;
 * `form-options`/single-`GET` are new siblings added for the React
 * create/edit forms (react-migration).
 *
 * All failure paths here raise an `AppError` subclass (ValidationError/
 * ConflictError/PermissionDeniedError/NotFoundError) rather than returning
 * `{success: false}` with a 200 — unlike e.g. absence_routes.py. Callers
 * catch `ApiError` (thrown by the shared `api.*` wrapper on any non-2xx
 * response) instead of checking a `.success` flag. Note: this blueprint's
 * path (`/system/users/api/*`) doesn't start with `/api/`, so app.py's
 * `AppError` handler falls back to an HTML error page instead of JSON —
 * `ApiError.message` degrades to a generic "Błąd serwera (status)" for
 * these specific failures instead of the precise validation text (a
 * pre-existing gap in app.py's error handler, not introduced here; see
 * implementation-log.md). */
export const usersApi = {
  list: () => api.get<{ users: UserListRow[]; count: number }>('/system/users/api').then((r) => r.users),

  get: (id: number) => api.get<{ success: true; user: UserDetail; linked_employee: LinkedEmployee | null }>(`/system/users/api/${id}`),

  formOptions: () => api.get<{ success: true; available_employees: AvailableEmployee[]; roles: AssignableRole[] }>('/system/users/api/form-options'),

  create: (payload: UserCreatePayload) => api.post<{ success: true; user_id: number }>('/system/users/api', payload),

  update: (id: number, payload: UserUpdatePayload) => api.put<{ success: true }>(`/system/users/api/${id}`, payload),

  changePassword: (id: number, newPassword: string) => api.put<{ success: true }>(`/system/users/api/${id}`, { new_password: newPassword }),

  delete: (id: number) => api.del<{ success: true }>(`/system/users/api/${id}`),

  toggleActive: (id: number) => api.put<{ success: true; is_active: boolean }>(`/system/users/api/${id}/toggle-active`),
};
