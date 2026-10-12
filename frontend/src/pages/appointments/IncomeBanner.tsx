import type { DayIncome } from '../../lib/appointments/useIncomeSummary';
import { formatPLN, formatZl } from '../../lib/format';

interface IncomeBannerProps {
  income: DayIncome;
  /** Push the banner to the right end of the nav row (calendar views: flush with the
   * grid's right edge). Off on the list, where it sits between the employee filter and
   * the search field. */
  alignEnd?: boolean;
}

/** Share of the period's visits already completed, as a whole percent (0 when there are none). */
export function completedPercent(income: DayIncome): number {
  return income.total > 0 ? Math.round((income.completed / income.total) * 100) : 0;
}

/** Desktop "Suma przychodu: actual / expected zł" banner that sits in the date-nav row of
 * the Wizyty pages (list, day, week, month). Recorded income of completed visits over the
 * expected total (completed + still planned) for the whole period on screen — which period
 * is whatever the page shows, so the caption stays the same everywhere. Two lines: the sums,
 * then "wg % zakończonych" — completed visits / all visits counted into `expected`, as a
 * whole percent and a slim progress bar. At least the nav row's shared control height
 * (Appointments.css), so it never sits shorter than the buttons beside it. */
export function IncomeBanner({ income, alignEnd = false }: IncomeBannerProps) {
  const pct = completedPercent(income);
  return (
    <div
      className={`inc-banner${alignEnd ? ' inc-banner--end' : ''}`}
      role="group"
      aria-label={`Suma przychodu: ${formatZl(income.actual)} zł z ${formatZl(income.expected)} zł oczekiwanych`}
      title={`Zapisany: ${formatPLN(income.actual)} · oczekiwany: ${formatPLN(income.expected)}`}
    >
      <span className="inc-banner-row">
        <span className="inc-banner-label">Suma przychodu</span>
        <span className="inc-banner-values">
          <strong className="inc-banner-actual">{formatZl(income.actual)}</strong> / {formatZl(income.expected)} zł
        </span>
      </span>
      <span className="inc-banner-row inc-banner-progress" title={`Zakończone wizyty: ${income.completed} z ${income.total}`}>
        <span className="inc-banner-pct-label">wg % zakończonych:</span>
        <strong className="inc-banner-pct">{pct}%</strong>
        <span className="inc-banner-bar" role="progressbar" aria-label="Wizyty zakończone" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
          <span className="inc-banner-bar-fill" style={{ width: `${pct}%` }} />
        </span>
      </span>
    </div>
  );
}
