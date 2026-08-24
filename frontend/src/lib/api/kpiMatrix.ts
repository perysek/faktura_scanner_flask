import { api } from './client';
import type { KpiMatrixResponse } from '../../types/kpiMatrix';

/** `/api/analytics/kpi-matrix` (routes/analytics_routes.py, analytics_bp
 * mounted under /api — already fully JSON, error responses included, no
 * backend changes needed). */
export const kpiMatrixApi = {
  get: (year?: number) => api.get<KpiMatrixResponse>('/api/analytics/kpi-matrix', year ? { year } : undefined),
};
