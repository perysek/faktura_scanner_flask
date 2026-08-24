/** Types for Wskaźniki biznesowe (KPI Matrix) — module-inventory.md's
 * "Analityka / KPI / Przychody" audit. Mirrors config/kpi_indicators.py +
 * repositories/analytics/kpi_matrix_repository.py field names. */

export type KpiDirection = '>' | '<' | '=';
export type KpiKind = 'eff' | 'effic';

export interface KpiIndicator {
  key: string;
  name: string;
  kind: KpiKind;
  unit: string;
  direction: KpiDirection;
  target: number;
  description?: string;
  unavailable_note?: string;
  months: Record<string, number | null>;
  y_current: number | null;
  y_prior: number | null;
}

export interface KpiProcess {
  id: string;
  name: string;
  indicators: KpiIndicator[];
}

export interface KpiMatrixResponse {
  success: true;
  year: number;
  min_year: number;
  max_year: number;
  processes: KpiProcess[];
}
