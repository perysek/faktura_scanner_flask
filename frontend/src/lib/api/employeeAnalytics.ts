import { api } from './client';
import type {
  EmployeeAnalyticsSummary,
  EmployeeClientSplitPoint,
  EmployeeCommissionTrendPoint,
  EmployeePeakHourCell,
  EmployeeRevenueTrendPoint,
  EmployeeSatisfactionStats,
  EmployeeServiceMixItem,
} from '../../types/employeeAnalytics';

/** `routes/analytics_routes.py`'s per-employee endpoints (PER-EMPLOYEE
 * ANALYTICS ENDPOINTS section) — data for EmployeeDetailPage's "Analizy i
 * wyniki" tabs. Each accepts an optional `months` window (backend defaults
 * to 12 when omitted). */
export const employeeAnalyticsApi = {
  summary: (employeeId: number, months = 12) =>
    api.get<{ success: true; data: EmployeeAnalyticsSummary }>(`/api/employees/${employeeId}/analytics/summary`, { months }).then((r) => r.data),

  revenueTrend: (employeeId: number, months = 12) =>
    api.get<{ success: true; data: EmployeeRevenueTrendPoint[] }>(`/api/employees/${employeeId}/analytics/revenue-trend`, { months }).then((r) => r.data),

  servicesMix: (employeeId: number) =>
    api.get<{ success: true; data: EmployeeServiceMixItem[] }>(`/api/employees/${employeeId}/analytics/services-mix`).then((r) => r.data),

  peakHours: (employeeId: number) =>
    api.get<{ success: true; data: EmployeePeakHourCell[] }>(`/api/employees/${employeeId}/analytics/peak-hours`).then((r) => r.data),

  clientSplit: (employeeId: number, months = 12) =>
    api.get<{ success: true; data: EmployeeClientSplitPoint[] }>(`/api/employees/${employeeId}/analytics/client-split`, { months }).then((r) => r.data),

  commissionTrend: (employeeId: number, months = 12) =>
    api.get<{ success: true; data: EmployeeCommissionTrendPoint[] }>(`/api/employees/${employeeId}/analytics/commission-trend`, { months }).then((r) => r.data),

  satisfaction: (employeeId: number, months = 12) =>
    api.get<{ success: true; data: EmployeeSatisfactionStats }>(`/api/employees/${employeeId}/analytics/satisfaction`, { months }).then((r) => r.data),
};
