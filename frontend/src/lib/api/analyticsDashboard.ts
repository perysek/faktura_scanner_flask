import { api } from './client';
import type {
  AnalyticsSummaryResponse,
  RevenueTrendResponse,
  EmployeePerformance,
  ServiceBreakdown,
  ClientMetrics,
  ProfitBreakdown,
  OccupancyStats,
  PeakHourCell,
  ServicePriceAnalysis,
  MonthlyTrendPoint,
  TopClient,
  BusinessInsight,
  RollingNewClientsPoint,
  RollingCancellationPoint,
  RollingAvgTicketPoint,
  RollingCategoryMixRow,
  RollingCostRatioPoint,
  RollingEmployeeUtilisationRow,
  RollingVisitFrequencyPoint,
  RollingSatisfactionResponse,
  PeriodParams,
} from '../../types/analyticsDashboard';

/** `/api/analytics/*` (routes/analytics_routes.py, analytics_bp mounted under /api —
 * already fully JSON, no backend changes needed). Period-scoped endpoints take
 * {period, startDate, endDate}; the eight `/rolling/*` endpoints and `monthly-trend`
 * are always the trailing 12 full months, independent of the page's period selector. */
function periodQuery({ period, startDate, endDate }: PeriodParams) {
  return period === 'custom' && startDate && endDate ? { period, start_date: startDate, end_date: endDate } : { period };
}

export const analyticsDashboardApi = {
  summary: (p: PeriodParams) => api.get<AnalyticsSummaryResponse>('/api/analytics/summary', periodQuery(p)),
  revenueTrend: (p: PeriodParams) => api.get<RevenueTrendResponse>('/api/analytics/revenue-trend', periodQuery(p)),
  employees: (p: PeriodParams) => api.get<{ success: true; employees: EmployeePerformance[] }>('/api/analytics/employees', periodQuery(p)),
  services: (p: PeriodParams) => api.get<{ success: true; services: ServiceBreakdown[] }>('/api/analytics/services', periodQuery(p)),
  clients: (p: PeriodParams) => api.get<{ success: true; metrics: ClientMetrics }>('/api/analytics/clients', periodQuery(p)),
  profit: (p: PeriodParams) => api.get<ProfitBreakdown>('/api/analytics/profit', periodQuery(p)),
  occupancy: (p: PeriodParams) => api.get<OccupancyStats>('/api/analytics/occupancy', periodQuery(p)),
  peakHours: (p: PeriodParams) => api.get<{ success: true; data: PeakHourCell[] }>('/api/analytics/peak-hours', periodQuery(p)),
  serviceAnalysis: (p: PeriodParams) => api.get<{ success: true; services: ServicePriceAnalysis[] }>('/api/analytics/service-analysis', periodQuery(p)),
  topClients: (p: PeriodParams) => api.get<{ success: true; clients: TopClient[] }>('/api/analytics/top-clients', periodQuery(p)),
  insights: (p: PeriodParams) => api.get<{ success: true; insights: BusinessInsight[] }>('/api/analytics/insights', periodQuery(p)),

  monthlyTrend: () => api.get<{ success: true; months: MonthlyTrendPoint[] }>('/api/analytics/monthly-trend'),
  rollingNewClients: () => api.get<{ success: true; months: RollingNewClientsPoint[] }>('/api/analytics/rolling/new-clients'),
  rollingCancellationRate: () => api.get<{ success: true; months: RollingCancellationPoint[] }>('/api/analytics/rolling/cancellation-rate'),
  rollingAvgTicket: () => api.get<{ success: true; months: RollingAvgTicketPoint[] }>('/api/analytics/rolling/avg-ticket'),
  rollingCategoryMix: () => api.get<{ success: true; rows: RollingCategoryMixRow[] }>('/api/analytics/rolling/category-mix'),
  rollingCostRatio: () => api.get<{ success: true; months: RollingCostRatioPoint[] }>('/api/analytics/rolling/cost-ratio'),
  rollingEmployeeUtilisation: () => api.get<{ success: true; rows: RollingEmployeeUtilisationRow[] }>('/api/analytics/rolling/employee-utilisation'),
  rollingVisitFrequency: () => api.get<{ success: true; distribution: RollingVisitFrequencyPoint[] }>('/api/analytics/rolling/visit-frequency'),
  rollingSatisfactionRating: () => api.get<RollingSatisfactionResponse>('/api/analytics/rolling/satisfaction-rating'),
};
