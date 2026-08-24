import { api } from './client';
import type { EmployeeServiceAssignment } from '../../types/employee';

/** `routes/employee_service_routes.py` — per-employee service pricing. */
export const employeeServicesApi = {
  list: (employeeId: number, activeOnly = true) =>
    api.get<{ success: true; services: EmployeeServiceAssignment[]; count: number }>(`/api/employees/${employeeId}/services`, { active_only: activeOnly }).then((r) => r.services),

  assign: (employeeId: number, values: { service_id: number; custom_price?: number; commission_rate?: number; duration_override?: number }) =>
    api.post<{ success: true; id: number }>(`/api/employees/${employeeId}/services`, values),

  update: (employeeId: number, esId: number, values: Partial<{ custom_price: number | null; commission_rate: number | null; duration_override: number | null; skill_rating: number | null; is_active: boolean }>) =>
    api.put<{ success: boolean }>(`/api/employees/${employeeId}/services/${esId}`, values),

  remove: (employeeId: number, esId: number) => api.del<{ success: true }>(`/api/employees/${employeeId}/services/${esId}`),
};
