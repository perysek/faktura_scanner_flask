import { useMemo, useState } from 'react';
import { formatNextVisitLine1 } from '../../lib/format';
import type { AnalyticsPeriod } from '../../types/analyticsDashboard';

type Granularity = 'month' | 'year' | 'range';

function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/**
 * Period-navigation state machine for the analytics dashboard — ported 1:1 from
 * `static/js/analytics/dashboard.js`'s `selectPeriod`/`navigatePeriod`/`applyCustomRange`
 * (lines ~100-190). Shifts prev/next by whole calendar months/years (not day-counts, which
 * drift across months of different lengths); an arbitrary custom range shifts by its own
 * length. When a month/year shift lands back on today's month/year, folds back into the
 * named preset instead of staying stuck on an equivalent 'custom' range.
 */
export function useAnalyticsPeriod() {
  const [period, setPeriod] = useState<AnalyticsPeriod>('current_month');
  const [customStart, setCustomStart] = useState<string | null>(null);
  const [customEnd, setCustomEnd] = useState<string | null>(null);
  const [granularity, setGranularity] = useState<Granularity>('month');

  function select(next: AnalyticsPeriod) {
    setPeriod(next);
    setCustomStart(null);
    setCustomEnd(null);
    setGranularity(next === 'current_year' ? 'year' : 'month');
  }

  function applyCustom(start: string, end: string) {
    setPeriod('custom');
    setCustomStart(start);
    setCustomEnd(end);
    setGranularity('range');
  }

  function navigate(direction: 1 | -1) {
    const today = new Date();

    if (granularity === 'year') {
      const anchorYear = period === 'current_year' ? today.getFullYear() : new Date(`${customStart}T00:00:00`).getFullYear();
      const targetYear = anchorYear + direction;
      if (targetYear === today.getFullYear()) {
        select('current_year');
        return;
      }
      setPeriod('custom');
      setCustomStart(`${targetYear}-01-01`);
      setCustomEnd(`${targetYear}-12-31`);
      return;
    }

    if (granularity === 'month') {
      let anchor: Date;
      if (period === 'current_month') {
        anchor = new Date(today.getFullYear(), today.getMonth(), 1);
      } else if (period === 'last_month') {
        anchor = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      } else {
        anchor = new Date(`${customStart}T00:00:00`);
      }

      const target = new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
      const lastMonthAnchor = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const isCurrentMonth = target.getFullYear() === today.getFullYear() && target.getMonth() === today.getMonth();
      const isLastMonth = target.getFullYear() === lastMonthAnchor.getFullYear() && target.getMonth() === lastMonthAnchor.getMonth();

      if (isCurrentMonth) {
        select('current_month');
        return;
      }
      if (isLastMonth) {
        select('last_month');
        return;
      }

      const monthEnd = new Date(target.getFullYear(), target.getMonth() + 1, 0);
      setPeriod('custom');
      setCustomStart(toISODate(target));
      setCustomEnd(toISODate(monthEnd));
      return;
    }

    // 'range' — an arbitrary user-picked window (from the custom-range modal), shifted by its own length
    if (!customStart || !customEnd) return;
    const start = new Date(`${customStart}T00:00:00`);
    const end = new Date(`${customEnd}T00:00:00`);
    const rangeDays = Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));

    const newStart = new Date(start);
    newStart.setDate(newStart.getDate() + direction * (rangeDays + 1));
    const newEnd = new Date(newStart);
    newEnd.setDate(newEnd.getDate() + rangeDays);

    setCustomStart(toISODate(newStart));
    setCustomEnd(toISODate(newEnd));
  }

  const description = useMemo(() => {
    switch (period) {
      case 'current_month':
        return 'Ten miesiąc';
      case 'last_month':
        return 'Ostatni miesiąc';
      case 'current_year':
        return 'Rok do daty';
      case 'custom':
        return customStart && customEnd ? `${formatNextVisitLine1(customStart)} – ${formatNextVisitLine1(customEnd)}` : 'Własny zakres';
    }
  }, [period, customStart, customEnd]);

  return {
    period,
    startDate: customStart,
    endDate: customEnd,
    description,
    select,
    navigate,
    applyCustom,
  };
}

export type UseAnalyticsPeriod = ReturnType<typeof useAnalyticsPeriod>;
