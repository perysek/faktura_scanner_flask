import { useEffect, useRef, useState } from 'react';
import type { ImportRunStatus, ImportStats } from '../../types/dataImport';

/** Mirrors routes/import_routes.py's SESSION_MAX_AGE_DAYS — the session file
 * counts as 'expired' once its mtime is this many days old. */
export const SESSION_MAX_AGE_DAYS = 30;

export function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return isoOf(d);
}

export function isoOf(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Inclusive day count of a YYYY-MM-DD range, or null when it isn't a valid range. */
export function rangeDays(start: string, end: string): number | null {
  if (!start || !end || start > end) return null;
  const a = new Date(`${start}T00:00:00`);
  const b = new Date(`${end}T00:00:00`);
  return Math.round((b.getTime() - a.getTime()) / 86_400_000) + 1;
}

export function skippedTotal(s: ImportStats): number {
  return (s.skipped_zero ?? 0) + (s.skipped_no_client ?? 0) + (s.skipped_no_employee ?? 0) + (s.skipped_duplicate ?? 0);
}

export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m} min ${String(s).padStart(2, '0')} s` : `${s} s`;
}

export function formatDateTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' }) : '—';
}

export function formatDay(isoDate: string | null): string {
  if (!isoDate) return '—';
  const [y, m, d] = isoDate.slice(0, 10).split('-');
  return `${d}.${m}.${y}`;
}

export const RUN_STATUS: Record<ImportRunStatus, { label: string; tone: 'ok' | 'live' | 'bad' | 'muted' }> = {
  completed: { label: 'Ukończony', tone: 'ok' },
  running: { label: 'W toku', tone: 'live' },
  failed: { label: 'Błąd', tone: 'bad' },
  cancelled: { label: 'Anulowany', tone: 'muted' },
  unknown: { label: 'Nieznany', tone: 'muted' },
};

/** The five result counters shown both live and in the final summary. */
export const STAT_TILES: { key: 'inserted' | 'clients' | 'duplicates' | 'skipped' | 'errors'; label: string; tone: string; pick: (s: ImportStats) => number }[] = [
  { key: 'inserted', label: 'Wstawiono', tone: 'ok', pick: (s) => s.inserted ?? 0 },
  { key: 'clients', label: 'Nowi klienci', tone: 'info', pick: (s) => s.clients_created ?? 0 },
  { key: 'duplicates', label: 'Duplikaty', tone: 'warn', pick: (s) => s.skipped_duplicate ?? 0 },
  { key: 'skipped', label: 'Pominięto', tone: 'muted', pick: (s) => skippedTotal(s) - (s.skipped_duplicate ?? 0) },
  { key: 'errors', label: 'Błędy', tone: 'bad', pick: (s) => s.errors ?? 0 },
];

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Eases a displayed number toward `target` (ease-out-quart) so live counters
 * roll instead of jumping. Interruptible: a new target continues from whatever
 * value is currently on screen. Instant under prefers-reduced-motion. */
export function useCountUp(target: number, duration = 650): number {
  const [shown, setShown] = useState(target);
  const shownRef = useRef(target);

  useEffect(() => {
    const from = shownRef.current;
    if (from === target) return;
    if (prefersReducedMotion()) {
      shownRef.current = target;
      setShown(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 4);
      const v = Math.round(from + (target - from) * eased);
      shownRef.current = v;
      setShown(v);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return shown;
}
