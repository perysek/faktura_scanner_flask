import type { DayIncome } from '../../lib/appointments/useIncomeSummary';
import { formatPLN, formatZl } from '../../lib/format';

interface IncomeBannerProps {
  income: DayIncome;
  /** Push the banner to the right end of the nav row (calendar views: flush with the
   * grid's right edge). Off on the list, where it sits between the employee filter and
   * the search field. */
  alignEnd?: boolean;
}

/** Desktop "Suma przychodu: actual / expected zł" banner that sits in the date-nav row of
 * the Wizyty pages (list, day, week, month). Recorded income of completed visits over the
 * expected total (completed + still planned) for the whole period on screen — which period
 * is whatever the page shows, so the caption stays the same everywhere. One line, fixed
 * height: `.inc-banner` takes the nav row's shared control height (Appointments.css), so it
 * lines up with the buttons and the employee selector next to it. */
export function IncomeBanner({ income, alignEnd = false }: IncomeBannerProps) {
  return (
    <div
      className={`inc-banner${alignEnd ? ' inc-banner--end' : ''}`}
      role="group"
      aria-label={`Suma przychodu: ${formatZl(income.actual)} zł z ${formatZl(income.expected)} zł oczekiwanych`}
      title={`Zapisany: ${formatPLN(income.actual)} · oczekiwany: ${formatPLN(income.expected)}`}
    >
      <span className="inc-banner-label">Suma przychodu</span>
      <span className="inc-banner-values">
        <strong className="inc-banner-actual">{formatZl(income.actual)}</strong> / {formatZl(income.expected)} zł
      </span>
    </div>
  );
}
