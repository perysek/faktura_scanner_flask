/**
 * Formatting helpers ported 1:1 from templates/clients/list.html's inline
 * <script> (phase-01-pilot-clients.md §1.4) — same logic, not reimplemented
 * from memory.
 */

const PL_MONTHS_SHORT = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

/** Parses a YYYY-MM-DD string as LOCAL time (avoids the UTC off-by-one a
 * bare `new Date(str)` would introduce) — exported so callers doing their own
 * date-diff math (e.g. DashboardPage's "days overdue/until") don't fall into
 * the same bug the original vanilla-JS dashboard has (Decyzja D18 fixed this
 * class of bug once already for ClientDetailPage; not reintroducing it here).
 *
 * Takes only the first 10 characters before splitting, so a full ISO
 * datetime string (`"2026-08-18T12:34:56.789"` — e.g. Sellers' `first_seen`/
 * `last_updated`, TIMESTAMP columns serialized via Python's
 * `datetime.isoformat()`, unlike the plain DATE columns — `invoice_date`,
 * `hire_date`, … — this was originally written for) still parses instead of
 * producing "Invalid Date": splitting the whole string on `-` picks up the
 * time portion as a bogus 3rd/4th segment (`"18T12:34:56.789"` → `NaN` when
 * `Number()`-coerced). Matches the original Jinja template's own
 * `seller.first_seen.strftime('%d.%m.%Y')` — day-level granularity, time
 * of day was never shown here either. */
export function parseLocalDate(dateString: string): Date {
  const [y, m, d] = dateString.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  return parseLocalDate(dateString).toLocaleDateString('pl-PL');
}

export function parseDateForSort(dateString: string | null | undefined): number {
  if (!dateString) return 0;
  return parseLocalDate(dateString).getTime();
}

/** "23 cze 12:30" style compact line for the next-visit cell. */
export function formatNextVisitLine1(dateString: string, timeString?: string | null): string {
  const [, m, d] = dateString.split('-').map(Number);
  const month = PL_MONTHS_SHORT[m - 1] ?? '';
  let line1 = `${d} ${month}`;
  if (timeString) line1 += ` ${timeString}`;
  return line1;
}

/**
 * Format a stored Polish phone number for display as "48 XXX XXX XXX".
 * Ported from static/js/utils.js's formatPhone. Display-only — never mutates
 * the stored value.
 */
/**
 * Canonical PLN money format → "1 234,56 zł" (F-003, static/js/utils.js's
 * formatPLN). Single source of truth for known-PLN amounts.
 */
export function formatPLN(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return '—';
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: 'PLN',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/** Multi-currency variant (static/js/utils.js's formatCurrency) — used where
 * an invoice's own `currency` field (not always PLN) must be respected. */
export function formatCurrency(amount: number | null | undefined, currency = 'PLN'): string {
  if (amount === null || amount === undefined) return '';
  return new Intl.NumberFormat('pl-PL', { style: 'currency', currency }).format(amount);
}

export function formatPhone(raw: string | null | undefined): string {
  if (!raw) return '';
  const digits = String(raw).replace(/\D/g, '');
  let national: string;
  if (digits.length === 11 && digits.startsWith('48')) {
    national = digits.slice(2);
  } else if (digits.length === 9) {
    national = digits;
  } else {
    return String(raw);
  }
  return `48 ${national.slice(0, 3)} ${national.slice(3, 6)} ${national.slice(6, 9)}`;
}
