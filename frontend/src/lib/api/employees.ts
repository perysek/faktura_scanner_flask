import { api } from './client';
import type {
  BalanceAdjustment,
  BalanceSummaryEntry,
  DirectReportsData,
  Employee,
  EmployeeBalance,
  EmployeeFormValues,
  EmployeeListRow,
  EmployeeStatistics,
  MobilePinStatus,
  UserOption,
} from '../../types/employee';

/** `/api/employees*` (routes/api_routes.py:3780-4560). Two new endpoints
 * added 2026-08-17 for this port — `direct-reports` GET and `user-options` —
 * see their docstrings in api_routes.py for why (no JSON equivalent existed
 * for data the Jinja edit page computed inline). */
export const employeesApi = {
  list: (params: { position?: string; activeOnly?: boolean } = {}) =>
    api
      .get<{ success: true; employees: EmployeeListRow[]; count: number }>('/api/employees', {
        position: params.position,
        active_only: params.activeOnly === undefined ? 'false' : String(params.activeOnly),
      })
      .then((r) => r.employees),

  get: (id: number) => api.get<{ success: true; employee: Employee }>(`/api/employees/${id}`).then((r) => r.employee),

  create: (values: EmployeeFormValues) => api.post<{ success: true; employee_id: number; message: string }>('/api/employees', values),

  update: (id: number, values: EmployeeFormValues) => api.put<{ success: true; message: string }>(`/api/employees/${id}`, values),

  deactivate: (id: number) => api.del<{ success: true; message: string }>(`/api/employees/${id}`),

  hardDelete: (id: number) => api.del<{ success: true; user_deleted: boolean; message: string }>(`/api/employees/${id}/permanent`),

  statistics: () => api.get<{ success: true; statistics: EmployeeStatistics }>('/api/employees/statistics').then((r) => r.statistics),

  positions: () => api.get<{ success: true; positions: string[] }>('/api/employees/positions').then((r) => r.positions),

  userOptions: () => api.get<{ success: true; users: UserOption[] }>('/api/employees/user-options').then((r) => r.users),

  bulkUpdateServices: () => api.post<{ success: true; updated_count: number; total_count: number; message: string }>('/api/employees/bulk-update-services'),

  getMobilePin: (id: number) => api.get<{ success: true } & MobilePinStatus>(`/api/employees/${id}/mobile-pin`),

  resetMobilePin: (id: number) => api.post<{ success: true; message: string }>(`/api/employees/${id}/mobile-pin/reset`),

  changeMobilePin: (id: number, pin: string) => api.put<{ success: true; message: string }>(`/api/employees/${id}/mobile-pin`, { pin }),

  getDirectReportsData: (id: number) => api.get<{ success: true } & DirectReportsData>(`/api/employees/${id}/direct-reports`),

  setDirectReports: (id: number, directReportIds: number[]) =>
    api.post<{ success: true; direct_report_ids: number[]; message: string } | { success: false; error: string; conflict_ids: number[] }>(`/api/employees/${id}/direct-reports`, {
      direct_report_ids: directReportIds,
    }),

  // absence_balance_routes.py — employee-scoped subset consumed by the detail page
  getBalances: (id: number) => api.get<{ success: true; balances: EmployeeBalance[]; employee_name: string }>(`/api/employees/${id}/absence-balances`).then((r) => r.balances),

  getBalanceAdjustments: (id: number) => api.get<{ success: true; adjustments: BalanceAdjustment[] }>(`/api/employees/${id}/absence-adjustments`).then((r) => r.adjustments),

  getBalanceSummary: () => api.get<{ success: true; balances: Record<string, BalanceSummaryEntry> }>('/api/absence-balances/summary').then((r) => r.balances),
};
