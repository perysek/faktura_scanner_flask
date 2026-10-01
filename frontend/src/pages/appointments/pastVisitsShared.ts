import type { PastResolutionStatus } from '../../types/appointment';

/** Pure helpers shared by the desktop modal (PastVisitsScanner.tsx) and the
 * phone page (PastVisitsPage.tsx) — formatting only, no behaviour of either
 * surface lives here. */

export const RESOLUTIONS: PastResolutionStatus[] = ['completed', 'cancelled', 'no_show'];

export const MONTHS_PL = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

export function fmtDateMonth(dateStr: string): string {
  const [, m, d] = dateStr.split('-').map(Number);
  return `${d} ${MONTHS_PL[m - 1] ?? ''}`.trim();
}

export function fmtTime(t: string): string {
  return t.slice(0, 5);
}

export function durationMinutes(start: string, end: string): number | null {
  const toMin = (t: string) => {
    const [h, m] = t.split(':').map(Number);
    return Number.isNaN(h) || Number.isNaN(m) ? null : h * 60 + m;
  };
  const a = toMin(start);
  const b = toMin(end);
  if (a == null || b == null) return null;
  let diff = b - a;
  if (diff < 0) diff += 24 * 60;
  return diff;
}

export function fmtHours(minutes: number): string {
  return String(Math.round((minutes / 60) * 100) / 100).replace('.', ',');
}

export function initials(name: string | null): string {
  if (!name) return '—';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Polish plural for the accusative "wizytę / wizyty / wizyt" after a count. */
export function pluralVisits(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (n === 1) return 'wizytę';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'wizyty';
  return 'wizyt';
}
