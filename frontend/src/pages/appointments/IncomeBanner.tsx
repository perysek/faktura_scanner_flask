import type { DayIncome } from '../../lib/appointments/useIncomeSummary';
import { formatPLN, formatZl } from '../../lib/format';

interface IncomeBannerProps {
  /** What the totals cover: "Przychód miesiąca" / "tygodnia" / "dnia" … */
  label: string;
  income: DayIncome;
}

/** Desktop "Przychód: actual / expected zł" banner that sits in the date-nav row of the
 * Wizyty pages (list, day, week, month). Recorded income of completed visits over the
 * expected total (completed + still planned) for the whole period on screen. One line,
 * fixed height: `.inc-banner` takes the nav row's shared control height (Appointments.css),
 * so it lines up with the buttons and the employee selector next to it. */
export function IncomeBanner({ label, income }: IncomeBannerProps) {
  return (
    <div
      className="inc-banner"
      role="group"
      aria-label={`${label}: ${formatZl(income.actual)} zł z ${formatZl(income.expected)} zł oczekiwanych`}
      title={`Zapisany: ${formatPLN(income.actual)} · oczekiwany: ${formatPLN(income.expected)}`}
    >
      <span className="inc-banner-label">{label}</span>
      <span className="inc-banner-values">
        <strong className="inc-banner-actual">{formatZl(income.actual)}</strong> / {formatZl(income.expected)} zł
      </span>
    </div>
  );
}
