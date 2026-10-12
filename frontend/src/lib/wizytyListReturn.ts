/**
 * Desktop Wizyty list → client page ("Więcej >" under a visit note) → back.
 *
 * The list remounts on the way back, and a fresh mount lands on the current
 * week, the default employee and scrollTop 0. Clicking "Więcej >" snapshots
 * what the list was showing here; the client page's "Powrót" (or the browser's
 * Back) returns with a history POP, and the list restores the snapshot once,
 * synchronously on mount, then puts the scroll position back after its data
 * has loaded.
 *
 * - sessionStorage (per tab), every access try/catch'd: storage can throw and
 *   the page must work identically without it (it just forgets).
 * - Taken (read + removed) by the first list mount after it is written, so it
 *   can never leak into a later, unrelated visit to the list.
 * - Expires after 30 minutes: a tab left on the client page for hours comes
 *   back to a fresh list.
 */
const KEY = 'wizyty-list-return';
const MAX_AGE_MS = 30 * 60 * 1000;

export interface WizytyListReturnState {
  /** Monday of the week shown, YYYY-MM-DD. */
  weekStart: string;
  mode: 'week' | 'chain';
  chainDates: string[];
  employeeId: number | null;
  searchQuery: string;
  sort: { column: string; dir: 'asc' | 'desc' };
  /** The list's own scroll box and the app's main scroll region. */
  tableScrollTop: number;
  mainScrollTop: number;
}

interface Stored extends WizytyListReturnState {
  savedAt: number;
}

export function saveWizytyListReturn(state: WizytyListReturnState): void {
  try {
    const stored: Stored = { ...state, savedAt: Date.now() };
    sessionStorage.setItem(KEY, JSON.stringify(stored));
  } catch {
    /* storage unavailable: the way back just lands on a fresh list */
  }
}

/** The snapshot, if one was saved recently; always removes it. */
export function takeWizytyListReturn(): WizytyListReturnState | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<Stored>;
    if (typeof v.savedAt !== 'number' || Date.now() - v.savedAt > MAX_AGE_MS) return null;
    const isIso = (d: unknown): d is string => typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d);
    if (!isIso(v.weekStart) || (v.mode !== 'week' && v.mode !== 'chain')) return null;
    const chainDates = Array.isArray(v.chainDates) && v.chainDates.every(isIso) ? v.chainDates : [];
    if (v.mode === 'chain' && chainDates.length === 0) return null;
    return {
      weekStart: v.weekStart,
      mode: v.mode,
      chainDates,
      employeeId: typeof v.employeeId === 'number' ? v.employeeId : null,
      searchQuery: typeof v.searchQuery === 'string' ? v.searchQuery : '',
      sort: v.sort && typeof v.sort.column === 'string' && (v.sort.dir === 'asc' || v.sort.dir === 'desc') ? v.sort : { column: 'appointment_date', dir: 'asc' },
      tableScrollTop: Number(v.tableScrollTop) || 0,
      mainScrollTop: Number(v.mainScrollTop) || 0,
    };
  } catch {
    return null;
  }
}
