/**
 * What the phone Wizyty list was showing (selected day + employee), remembered
 * across the unmount that every route change causes.
 *
 * Why this exists: WizytyListPage remounts whenever you come back to /wizyty
 * (Powrót from a visit, Anuluj/Zapisz on the form, browser back), and a fresh
 * mount always lands on "today" + the logged-in user's own employee. So a
 * receptionist who picked a colleague and another day lost both on every
 * round trip to a visit. The page now writes the selection here as it
 * changes and reads it back synchronously on mount.
 *
 * Scope on purpose:
 * - sessionStorage (per tab, gone when the tab closes), never localStorage.
 * - Only valid for the SAME local calendar day it was saved: a tab left open
 *   overnight must come back on today, not on yesterday's schedule.
 * - Cleared on login/logout (AuthContext) so one user's selection can never
 *   leak into the next user's session in the same tab.
 * - Every access is try/catch'd: storage can throw (private mode, blocked
 *   site data) and the page must work identically without it.
 */
const KEY = 'wizyty-list-view-state';

export interface WizytyListViewState {
  /** The selected day, YYYY-MM-DD (the strip's active day). Always chain[0]. */
  date: string;
  /** The selected day plus every day appended below it by "Pokaż kolejny dzień",
   * in order. Restored so a round trip to a visit doesn't collapse the list. */
  chain: string[];
  /** The employee selector's value; null = nobody picked / "all". */
  employeeId: number | null;
}

interface StoredState extends WizytyListViewState {
  /** Local calendar day this was saved on, YYYY-MM-DD. */
  savedOn: string;
}

function localIsoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function readWizytyListState(): WizytyListViewState | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<StoredState>;
    if (typeof value.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value.date)) return null;
    if (value.employeeId !== null && typeof value.employeeId !== 'number') return null;
    if (value.savedOn !== localIsoToday()) return null;
    // `chain` arrived after the first version of this state: older saves only
    // have `date`, which is a chain of one.
    const isIso = (d: unknown): d is string => typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d);
    const chain = Array.isArray(value.chain) && value.chain.length > 0 && value.chain.every(isIso) && value.chain[0] === value.date ? value.chain : [value.date];
    return { date: value.date, chain, employeeId: value.employeeId };
  } catch {
    return null;
  }
}

export function writeWizytyListState(state: WizytyListViewState): void {
  try {
    const stored: StoredState = { ...state, savedOn: localIsoToday() };
    sessionStorage.setItem(KEY, JSON.stringify(stored));
  } catch {
    /* storage unavailable: the page just forgets, exactly as before */
  }
}

export function clearWizytyListState(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}
