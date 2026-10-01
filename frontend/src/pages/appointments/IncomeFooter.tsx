import type { DayIncome } from '../../lib/appointments/useIncomeSummary';
import { formatPLN, formatZl } from '../../lib/format';

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
