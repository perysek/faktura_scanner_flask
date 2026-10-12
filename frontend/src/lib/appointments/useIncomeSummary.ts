import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { appointmentsApi } from '../api/appointments';
import { useAuth } from '../../contexts/AuthContext';
import { hasFullEmployeesGrant } from '../../components/layout/navConfig';
import type { IncomeSummaryResponse } from '../../types/appointment';
import { useAppointmentsChanged } from './appointmentEvents';

export interface DayIncome {
  actual: number;
  expected: number;
  /** Completed visits / all visits counted into `expected` — the "wg % zakończonych" bar. */
  completed: number;
  total: number;
}

export const EMPTY_INCOME: DayIncome = { actual: 0, expected: 0, completed: 0, total: 0 };

export function addIncome(a: DayIncome, b: DayIncome): DayIncome {
  return { actual: a.actual + b.actual, expected: a.expected + b.expected, completed: a.completed + b.completed, total: a.total + b.total };
}

export interface IncomeSummary {
  /** Whose rows the server sent: 'all' | 'own' | 'none'; null until the first answer. */
  scope: IncomeSummaryResponse['scope'] | null;
  /** May the figures for this employee selection (null = everyone) be shown at all?
   * The server only ever sends permitted rows, so this is presentation logic, not
   * the security boundary: 'all' → anything; 'own' → only the viewer's own employee;
   * "everyone" is never a valid selection for 'own' (it would be a partial total). */
  canShow: (employeeId: number | null) => boolean;
  /** Σ actual / Σ expected for a day, over one employee or (null) all rows sent.
   * `null` when there is nothing for that day. */
  forDay: (date: string, employeeId: number | null) => DayIncome | null;
  /** Σ actual / Σ expected over every day in [startDate, endDate] (inclusive), for one
   * employee or (null) all rows sent. Zeros — never null — when the range is empty, so
   * a banner can show "0 / 0 zł". Only covers days inside the range the hook fetched. */
  forRange: (startDate: string, endDate: string, employeeId: number | null) => DayIncome;
}

function rowIncome(r: IncomeSummaryResponse['rows'][number]): DayIncome {
  // `?? 0`: a server that predates the counts still renders (bar at 0%).
  return { actual: r.actual, expected: r.expected, completed: r.visits_completed ?? 0, total: r.visits_total ?? 0 };
}

/** Live "Przychód: actual / expected" for a date range. One request returns every
 * permitted employee's rows, so switching the Pracownik filter needs no refetch.
 *
 * Re-fetches (keeping the previous numbers on screen — no flicker) whenever the
 * range changes, visits change anywhere (appointmentEvents), or the tab becomes
 * visible again. The request is skipped entirely for viewers who can never see
 * income (no linked employee and no full Employees grant) — and for callers that
 * pass `enabled=false` (e.g. the day view, which is superuser-only). */
export function useIncomeSummary(startDate: string | null, endDate: string | null, enabled = true): IncomeSummary {
  const auth = useAuth();
  const canQuery = enabled && (auth.hasLinkedEmployee || hasFullEmployeesGrant(auth));
  const [data, setData] = useState<IncomeSummaryResponse | null>(null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    if (!canQuery || !startDate || !endDate) return;
    const id = ++requestId.current;
    appointmentsApi
      .incomeSummary(startDate, endDate)
      .then((res) => {
        if (id === requestId.current) setData(res);
      })
      .catch(() => {
        /* non-critical decoration — keep whatever is already shown */
      });
  }, [canQuery, startDate, endDate]);

  useEffect(load, [load]);
  useAppointmentsChanged(load);

  useEffect(() => {
    const onVisible = () => {
      if (!document.hidden) load();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [load]);

  return useMemo<IncomeSummary>(() => {
    const scope = data?.scope ?? null;
    const own = data?.own_employee_id ?? null;
    const byDate = new Map<string, IncomeSummaryResponse['rows']>();
    for (const r of data?.rows ?? []) {
      const bucket = byDate.get(r.date);
      if (bucket) bucket.push(r);
      else byDate.set(r.date, [r]);
    }
    return {
      scope,
      canShow: (employeeId) => scope === 'all' || (scope === 'own' && employeeId !== null && employeeId === own),
      forDay: (date, employeeId) => {
        const rows = (byDate.get(date) ?? []).filter((r) => employeeId === null || r.employee_id === employeeId);
        if (rows.length === 0) return null;
        return rows.reduce<DayIncome>((sum, r) => addIncome(sum, rowIncome(r)), EMPTY_INCOME);
      },
      forRange: (startDate, endDate, employeeId) => {
        let total = EMPTY_INCOME;
        // ISO dates compare correctly as plain strings.
        for (const [date, rows] of byDate) {
          if (date < startDate || date > endDate) continue;
          for (const r of rows) {
            if (employeeId !== null && r.employee_id !== employeeId) continue;
            total = addIncome(total, rowIncome(r));
          }
        }
        return total;
      },
    };
  }, [data]);
}
