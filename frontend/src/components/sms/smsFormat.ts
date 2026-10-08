import type { SmsDeliveryStatus } from '../../types/sms';

/** "2026-10-07T04:20:53" -> "07.10.2026 04:20". The server already sends Warsaw wall-clock, so this is
 * plain string slicing — a Date round-trip would re-interpret it in the BROWSER's zone. */
export function fmtWhen(iso: string | null | undefined): string {
  if (!iso || iso.length < 16) return '—';
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)} ${iso.slice(11, 16)}`;
}

/** Same minute-precision time with the seconds, for a tooltip ("04:20:53"). */
export function fmtWhenExact(iso: string | null | undefined): string {
  if (!iso || iso.length < 19) return fmtWhen(iso);
  return `${fmtWhen(iso)}:${iso.slice(17, 19)}`;
}

/** "2026-10-10" + "08:00:00" -> "10.10.2026 08:00". */
export function fmtVisit(date: string | null | undefined, time: string | null | undefined): string {
  if (!date) return '—';
  const [y, m, d] = date.slice(0, 10).split('-');
  return `${d}.${m}.${y}${time ? ` ${time.slice(0, 5)}` : ''}`;
}

export const SMS_STATUS: Record<SmsDeliveryStatus, { label: string; className: string }> = {
  pending: { label: 'Oczekuje', className: 'sms-pill--pending' },
  sent: { label: 'Wysłany', className: 'sms-pill--sent' },
  delivered: { label: 'Dostarczony', className: 'sms-pill--delivered' },
  failed: { label: 'Błąd', className: 'sms-pill--failed' },
};

export function smsStatus(status: string | null | undefined): { label: string; className: string } {
  return SMS_STATUS[(status ?? 'pending') as SmsDeliveryStatus] ?? SMS_STATUS.pending;
}

/** "+48500100200" -> "+48 500 100 200": digits in groups of three counted from the right, so whatever is
 * left over at the front is the country code. Text that is not a number (the sender refused it, staff must be
 * able to read what is stored) comes back untouched. `plus: false` drops the leading "+" (the Wysłane table
 * saves the width: "48 500 100 200"). */
export function fmtPhone(raw: string | null | undefined, { plus = true }: { plus?: boolean } = {}): string {
  const text = (raw ?? '').trim();
  if (!text) return '—';
  const compact = text.replace(/[\s()-]/g, '');
  if (!/^\+?\d+$/.test(compact)) return text;
  const digits = compact.replace('+', '');
  const groups: string[] = [];
  for (let end = digits.length; end > 0; end -= 3) groups.unshift(digits.slice(Math.max(0, end - 3), end));
  return `${plus && compact.startsWith('+') ? '+' : ''}${groups.join(' ')}`;
}

// ── Months ("YYYY-MM"): the value of the month picker on Wysyłki SMS and of `?month=` on its endpoints ──────────

/** The server accepts 2000-01 … 2100-12 (utils.timezone.parse_year_month); the picker never leaves that range. */
export const MIN_MONTH = '2000-01';
export const MAX_MONTH = '2100-12';

const MONTH_NAMES = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
export const MONTH_ABBR = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

/** This month on the salon's clock (Warsaw), not the browser's: around midnight they can disagree. */
export function currentMonthWarsaw(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit' }).formatToParts(now);
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}`;
}

export function clampMonth(ym: string): string {
  return ym < MIN_MONTH ? MIN_MONTH : ym > MAX_MONTH ? MAX_MONTH : ym;
}

/** "2026-12" + 1 -> "2027-01", clamped to the supported range. */
export function shiftMonth(ym: string, delta: number): string {
  const [year, month] = ym.split('-').map(Number);
  const index = year * 12 + (month - 1) + delta;
  return clampMonth(`${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`);
}

export function monthOf(year: number, monthIndex: number): string {
  return clampMonth(`${year}-${String(monthIndex + 1).padStart(2, '0')}`);
}

/** "2026-10" -> "październik 2026". */
export function fmtMonthYear(ym: string): string {
  const [year, month] = ym.split('-').map(Number);
  return `${MONTH_NAMES[month - 1] ?? ''} ${year}`;
}
