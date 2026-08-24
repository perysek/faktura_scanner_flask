import { api } from './client';
import type { AbsenceAdjustment, AbsenceCategory, EmployeeAbsenceBalance } from '../../types/absenceBalance';

/** `/api/absence-balances*`, `/api/employees/<id>/absence-*`,
 * `/api/absence-categories*` (routes/absence_balance_routes.py) — already
 * fully JSON, no backend changes for this module. */
export const absenceBalancesApi = {
  trackedCategories: () => api.get<{ success: true; categories: AbsenceCategory[] }>('/api/absence-categories/tracked').then((r) => r.categories),

  /** Keys are employee IDs with at least one tracked balance — the values
   * aren't consumed by the page (ported 1:1 from the original's
   * `Object.keys(sData.balances)` — it only ever reads the ID list, then
   * re-fetches each employee's full detail below). */
  summaryEmployeeIds: () =>
    api.get<{ success: true; balances: Record<string, unknown> }>('/api/absence-balances/summary').then((r) => Object.keys(r.balances || {}).map(Number)),

  employeeBalances: (employeeId: number) =>
    api.get<{ success: true; balances: EmployeeAbsenceBalance[]; employee_name: string }>(`/api/employees/${employeeId}/absence-balances`),

  setLimit: (employeeId: number, categoryId: number, maxValue: number, notes?: string | null) =>
    api.post<{ success: true; id: number }>(`/api/employees/${employeeId}/absence-limits`, { category_id: categoryId, max_value: maxValue, notes }),

  createAdjustment: (employeeId: number, categoryId: number, deltaValue: number, reason: string, periodLabel?: string | null) =>
    api.post<{ success: true; id: number }>(`/api/employees/${employeeId}/absence-adjustments`, {
      category_id: categoryId,
      delta_value: deltaValue,
      reason,
      period_label: periodLabel || null,
    }),

  listAdjustments: (employeeId: number) =>
    api.get<{ success: true; adjustments: AbsenceAdjustment[] }>(`/api/employees/${employeeId}/absence-adjustments`).then((r) => r.adjustments),
};
