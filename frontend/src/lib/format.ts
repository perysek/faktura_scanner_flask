/**
 * Formatting helpers ported 1:1 from templates/clients/list.html's inline
 * <script> (phase-01-pilot-clients.md §1.4) — same logic, not reimplemented
 * from memory.
 */

const PL_MONTHS_SHORT = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

/** Parses a YYYY-MM-DD string as LOCAL time (avoids the UTC off-by-one a
 * bare `new Date(str)` would introduce). */
function parseLocalDate(dateString: string): Date {
  const [y, m, d] = dateString.split('-').map(Number);
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
