import { fmtMonthYear } from './smsFormat';
import './sms.css';

export interface SmsMonthCostProps {
  /** "YYYY-MM" — the month the tab's picker shows. */
  month: string;
  /** `sent`: what went out in that month. `pending`: what the scheduler will still send in it. */
  kind: 'sent' | 'pending';
}

const LABEL: Record<SmsMonthCostProps['kind'], string> = {
  sent: 'Koszt wysłanych SMS za',
  pending: 'Szacowany koszt oczekujących SMS za',
};

/**
 * PLACEHOLDER above each table of Wysyłki SMS: the selected month's total SMS cost.
 *
 * TODO(sms-cost): shows "— zł" until two things exist, then render `count × unitPrice` here:
 *   1. a unit price per SMS in the SMS settings table (Ustawienia SMS) — not there yet;
 *   2. a count for the month ALONE — `/api/sms/log` and `/api/sms/pending` only return the running total up to the
 *      end of the month (`?month=` is an exclusive upper bound), so they need a lower bound (or a stats endpoint).
 */
export function SmsMonthCost({ month, kind }: SmsMonthCostProps) {
  return (
    <p className="sms-cost" title="Kwota pojawi się po dodaniu ceny jednostkowej SMS w ustawieniach (liczba SMS × cena)">
      <span className="sms-cost-label">
        {LABEL[kind]} {fmtMonthYear(month)}:
      </span>{' '}
      <strong className="sms-cost-value">— zł</strong>
    </p>
  );
}
