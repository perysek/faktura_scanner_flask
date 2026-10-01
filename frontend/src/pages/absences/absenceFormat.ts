import type { AbsenceRecord } from '../../types/absence';

// Hardcoded, not Intl: the phone cards must read the same on every device
// locale, and Intl's short-month output differs between engines.
const MONTHS_SHORT = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

function parseYmd(ymd: string) {
  const [y, m, d] = ymd.split('-').map(Number);
  return { y, m, d };
}

/** "12–16 paź 2026", "28 wrz – 3 paź 2026", "5 paź 2026, 14:00–16:30" — the
 * phone card's headline, so it has to be scannable at a glance. */
export function formatPeriodPhone(a: Pick<AbsenceRecord, 'date_from' | 'date_to' | 'time_from' | 'time_to'>) {
  const from = parseYmd(a.date_from);
  const to = parseYmd(a.date_to);
  const day = (p: typeof from, withYear: boolean) => `${p.d} ${MONTHS_SHORT[p.m - 1]}${withYear ? ` ${p.y}` : ''}`;
  if (a.time_from) return `${day(from, true)}, ${a.time_from}–${a.time_to}`;
  if (a.date_from === a.date_to) return day(from, true);
  if (from.y === to.y && from.m === to.m) return `${from.d}–${to.d} ${MONTHS_SHORT[to.m - 1]} ${to.y}`;
  if (from.y === to.y) return `${day(from, false)} – ${day(to, true)}`;
  return `${day(from, true)} – ${day(to, true)}`;
}

/** "1 paź, 08:14" (year only when it isn't the current one) from an ISO
 * "YYYY-MM-DDTHH:MM…" timestamp; "—" when absent. */
export function formatStampPhone(ts: string | null | undefined) {
  if (!ts) return '—';
  const { y, m, d } = parseYmd(ts.slice(0, 10));
  const year = y === new Date().getFullYear() ? '' : ` ${y}`;
  return `${d} ${MONTHS_SHORT[m - 1]}${year}, ${ts.slice(11, 16)}`;
}
