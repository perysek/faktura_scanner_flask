import type { DayIncome } from '../../lib/appointments/useIncomeSummary';
import { formatPLN, formatZl } from '../../lib/format';

/** "Przychód dnia" card right under a day's weekday/date label (above its first visit) on the phone list — recorded income
 * of completed visits over the day's expected total (completed + still planned).
 * The bar is purely decorative (aria-hidden): the same numbers are in the group's
 * accessible name, so a screen reader hears them once instead of a bare percentage. */
export function MobileIncomeCard({ income }: { income: DayIncome }) {
  const pct = income.expected > 0 ? Math.min(100, Math.round((income.actual / income.expected) * 100)) : 0;
  return (
    <section
      className="mob-income"
      role="group"
      aria-label={`Przychód dnia: ${formatZl(income.actual)} zł z ${formatZl(income.expected)} zł oczekiwanych`}
      title={`Zapisany: ${formatPLN(income.actual)} · oczekiwany: ${formatPLN(income.expected)}`}
    >
      <div className="mob-income-head">
        <span className="mob-income-label">Przychód dnia</span>
        <span className="mob-income-pct">{pct}%</span>
      </div>
      <div className="mob-income-figures">
        <strong className="mob-income-actual">{formatZl(income.actual)} zł</strong>
        <span className="mob-income-expected">z {formatZl(income.expected)} zł</span>
      </div>
      <div className="mob-income-bar" aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </div>
    </section>
  );
}
