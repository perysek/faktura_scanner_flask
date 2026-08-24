import type { KpiDirection, KpiIndicator } from '../../types/kpiMatrix';

/** Ported 1:1 from static/js/analytics/kpi_matrix.js — the single place that
 * decides "how to print this indicator's numbers," shared by the table row
 * and its expanded chart so both always agree. */

export function kpiMetTarget(value: number | null, direction: KpiDirection, target: number): boolean | null {
  if (value === null || value === undefined) return null;
  if (direction === '>') return value >= target;
  if (direction === '<') return value <= target;
  if (direction === '=') return value === target;
  return null;
}

export function kpiStatusClass(value: number | null, direction: KpiDirection, target: number): string {
  const met = kpiMetTarget(value, direction, target);
  if (met === null) return '';
  return met ? 'status-good' : 'status-bad';
}

function fmtValue(value: number | null, unit: string): string {
  if (value === null || value === undefined) return '–';
  if (unit === '1-5' || unit === 'wizyt/kl.' || unit === 'min') return value.toFixed(1);
  if (unit === 'PLN/h' || unit === 'PLN/wiz.') return Math.round(value).toLocaleString('pl-PL');
  return value.toFixed(1);
}

const PLN_THOUSANDS_THRESHOLD = 10000;

function plnNeedsThousands(ind: KpiIndicator): boolean {
  let max = 0;
  for (let m = 1; m <= 12; m++) {
    const v = ind.months[String(m)];
    if (v !== null && v !== undefined) max = Math.max(max, Math.abs(v));
  }
  if (ind.y_prior !== null) max = Math.max(max, Math.abs(ind.y_prior));
  if (ind.y_current !== null) max = Math.max(max, Math.abs(ind.y_current));
  return max >= PLN_THOUSANDS_THRESHOLD;
}

function fmtPln(value: number | null, useThousands: boolean): string {
  if (value === null || value === undefined) return '–';
  if (useThousands) return (value / 1000).toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return Math.round(value).toLocaleString('pl-PL');
}

export interface KpiFormatter {
  unitLabel: string;
  fmt: (v: number | null) => string;
}

export function getKpiFormatter(ind: KpiIndicator): KpiFormatter {
  if (ind.unit === 'PLN') {
    const useThousands = plnNeedsThousands(ind);
    return { unitLabel: useThousands ? 'tys. zł' : 'zł', fmt: (v) => fmtPln(v, useThousands) };
  }
  return { unitLabel: ind.unit, fmt: (v) => fmtValue(v, ind.unit) };
}

export function formatKpiValue(ind: KpiIndicator, value: number | null): string {
  return getKpiFormatter(ind).fmt(value);
}
