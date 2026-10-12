import type { CSSProperties } from 'react';
import type { DayIncome } from '../../lib/appointments/useIncomeSummary';
import { formatPLN, formatZl } from '../../lib/format';
import { completedPercent } from './IncomeBanner';

interface IncomeFooterProps {
  income: DayIncome | null;
  /** Week/day footers are a fixed row: show "—" for an empty day instead of
   * collapsing, so the row keeps its height. Month cells just omit the footer. */
  dashWhenEmpty?: boolean;
}

/** "Przychód: 1 200 / 1 500 zł" — recorded income of completed visits / expected
 * total for the day (completed + still planned). Right-aligned, wraps to a second
 * line in a narrow column rather than clipping. */
export function IncomeFooter({ income, dashWhenEmpty = false }: IncomeFooterProps) {
  const empty = !income || (income.actual === 0 && income.expected === 0);
  if (empty) {
    return dashWhenEmpty ? (
      <div className="inc-footer inc-footer--none" aria-label="Przychód: brak">
        —
      </div>
    ) : null;
  }
  return (
    <div className="inc-footer" title={`Przychód zapisany: ${formatPLN(income.actual)} · oczekiwany: ${formatPLN(income.expected)}`}>
      <span className="inc-label">Przychód:</span>
      <span className="inc-values">
        <strong className="inc-actual">{formatZl(income.actual)}</strong> / {formatZl(income.expected)} zł
      </span>
    </div>
  );
}

/** Month-cell variant: a compact capsule in the day-number header row, right-aligned.
 * A small ring shows the share of the day's visits already completed (same measure as
 * the banner's "wg % zakończonych"), then "actual / expected". Three tones: nothing
 * recorded yet (neutral), partly recorded (accent), everything recorded (success). The
 * "Przychód" label lives in the tooltip/aria-label — the cell has no room for it. */
export function IncomePill({ income }: { income: DayIncome | null }) {
  if (!income || (income.actual === 0 && income.expected === 0)) return null;
  const pct = completedPercent(income);
  const tone = income.actual <= 0 ? 'pending' : income.actual >= income.expected ? 'done' : 'partial';
  return (
    <span
      className={`inc-pill inc-pill--${tone}`}
      aria-label={`Przychód: ${formatZl(income.actual)} zł z ${formatZl(income.expected)} zł oczekiwanych`}
      title={`Przychód zapisany: ${formatPLN(income.actual)} · oczekiwany: ${formatPLN(income.expected)} · zakończone wizyty: ${income.completed} z ${income.total}`}
    >
      <span className="inc-pill-ring" style={{ '--pct': pct } as CSSProperties} aria-hidden="true" />
      <span className="inc-pill-values">
        <strong className="inc-pill-actual">{formatZl(income.actual)}</strong>
        <span className="inc-pill-sep">/</span>
        {formatZl(income.expected)}
      </span>
    </span>
  );
}
