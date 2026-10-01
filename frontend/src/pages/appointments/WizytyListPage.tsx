import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import './Appointments.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { useAuth } from '../../contexts/AuthContext';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { formatPLN } from '../../lib/format';
import { empColor } from '../../lib/appointments/employeeColor';
import { ViewSwitcher } from './ViewSwitcher';
import { EmployeeFilter } from './EmployeeFilter';
import { StatusDropdown } from './StatusDropdown';
import { RescheduleSheet } from './RescheduleSheet';
import { CalendarMonthSidebar } from './CalendarMonthSidebar';
import { PastVisitsScanner } from './PastVisitsScanner';
import { MobileWizytyCalendarView, useIsMobile, OWN_DATA_OFF_FALLBACK_EMPLOYEE_KEY } from './MobileWizytyCalendarView';
import { readWizytyListState, writeWizytyListState } from '../../lib/wizytyListState';
import type { AppointmentListItem, EmployeeOption } from '../../types/appointment';

type SortColumn = 'appointment_date' | 'start_time' | 'client_name' | 'service_name' | 'employee_name' | 'total_price' | 'status' | 'satisfaction_score';

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = (day === 0 ? -6 : 1) - day;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}
function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function formatDateShort(dateStr: string): string {
  const [y, m, d] = dateStr.split('-');
  return `${d}.${m}.${y}`;
}
function isWeekend(dateStr: string): boolean {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dow = new Date(y, m - 1, d).getDay();
  return dow === 0 || dow === 6;
}
function isPast(dateStr: string, endTime: string): boolean {
  return new Date(`${dateStr}T${endTime}`) < new Date();
}
function stars(score: number | null): string {
  if (!score) return '—';
  return '★'.repeat(score) + '☆'.repeat(5 - score);
}

/** How many months ahead "Pokaż kolejny dzień" scans for the next day with visits
 * before giving up (same horizon the old "go to next visit" button used). */
const NEXT_DAY_SCAN_MONTHS = 6;

/**
 * Wizyty — lista. Szósty moduł Fazy 2, ported z templates/appointments/list.html.
 * Domyślnie pokazuje jeden tydzień (pon–nd, jak w oryginale); po kliknięciu dnia
 * na bocznym pasku month-cards (CalendarMonthSidebar) przechodzi w tryb
 * "day-chain" — patrz calendar-sidebar-redesign-prompt.md §"List-view click
 * behavior" i handleSidebarDayClick/appendNextChainDay niżej. Poza zakresem
 * tego przebiegu: "Rozlicz przeszłe wizyty" (past-pending/past-status —
 * osobny mały workflow), status-events polling (globalne powiadomienia,
 * nie specyficzne dla tej strony) — patrz implementation-log.md.
 */
export function WizytyListPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const canWrite = auth.hasModuleWrite('appointments');
  const isMobile = useIsMobile(640);
  // AppShell's persistent logo+title row (<1024px) exposes this empty slot
  // for pages to portal mobile-only chrome into — "Rozlicz przeszłe wizyty"
  // lands there (TASK3) so it stays reachable while the card list scrolls,
  // instead of scrolling away with `.page-header` (which is dropped
  // outright on mobile, TASK4).
  const [mobileHeaderSlot, setMobileHeaderSlot] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setMobileHeaderSlot(document.getElementById('mobile-header-actions'));
  }, []);

  // Phone only: what this list showed the last time it was on screen (selected
  // day + employee). Every way back to /wizyty remounts this page, and a fresh
  // mount used to land on today + the user's own employee, discarding whatever
  // was picked. Read ONCE, synchronously, so the very first render already has
  // the right day/strip/employee (no flash of "today"). See lib/wizytyListState.
  const [restored] = useState(() => (isMobile ? readWizytyListState() : null));
  const [weekStart, setWeekStart] = useState(() => {
    if (!restored) return getMonday(new Date());
    const [y, m, d] = restored.date.split('-').map(Number);
    return getMonday(new Date(y, m - 1, d));
  });
  // The phone's "selected day" IS chain mode with one date (selectedDate =
  // chainDates[0]); starting there also makes the mobile view skip its
  // select-today-on-mount effect.
  const [mode, setMode] = useState<'week' | 'chain'>(restored ? 'chain' : 'week');
  const [chainDates, setChainDates] = useState<string[]>(restored ? restored.chain : []);
  const [monthCache, setMonthCache] = useState<{ key: string; byDate: Map<string, AppointmentListItem[]> } | null>(null);
  // Restored: the month for that day is fetched in the effect below; show the
  // loading state until then instead of a false "Brak wizyt tego dnia".
  const [chainLoading, setChainLoading] = useState(restored !== null);
  // Phone "Pokaż kolejny dzień": days appended BELOW the selected day
  // (chainDates[0]). Their visits live here, not in monthCache, because the
  // next day with visits can be in another month and monthCache only ever holds
  // one. monthFetchRef is a plain fetch cache for scanning forward month by
  // month WITHOUT repointing monthCache (that would blank the strip's dots and
  // the selected day's own data).
  const [extraDayData, setExtraDayData] = useState<Record<string, AppointmentListItem[]>>({});
  const [nextDayLoading, setNextDayLoading] = useState(false);
  const [noMoreDays, setNoMoreDays] = useState(false);
  const monthFetchRef = useRef(new Map<string, Map<string, AppointmentListItem[]>>());

  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState<number | null>(restored ? restored.employeeId : null);
  const [searchQuery, setSearchQuery] = useState('');
  // Default the "Pracownik" filter to the logged-in user's own linked
  // employee (once /auth/me resolves), instead of leaving it on "Wszyscy".
  // Guarded to fire exactly once so it never clobbers a selection the user
  // made themselves on a later auth refetch.
  //
  // The mobile "Dane własne" long-press (MobileWizytyCalendarView.tsx)
  // overrides this default when turning own-data OFF: it writes the employee
  // id that toggle should land on (the first employee with a visit today,
  // not the superuser's own) to sessionStorage BEFORE the reload that
  // follows every own-data flip, since that reload remounts this whole page
  // fresh and would otherwise run this exact effect and clobber it back to
  // `linkedEmployeeId`. Read once and cleared immediately so it never
  // leaks into any later, unrelated mount.
  const employeeDefaultAppliedRef = useRef(false);
  useEffect(() => {
    if (employeeDefaultAppliedRef.current || auth.isLoading) return;
    employeeDefaultAppliedRef.current = true;
    const override = sessionStorage.getItem(OWN_DATA_OFF_FALLBACK_EMPLOYEE_KEY);
    if (override !== null) {
      sessionStorage.removeItem(OWN_DATA_OFF_FALLBACK_EMPLOYEE_KEY);
      setEmployeeId(override === 'null' ? null : Number(override));
      return;
    }
    // A remembered employee wins over the "own employee" default, except in
    // "Dane własne" mode: there the server hard-scopes every query to the
    // superuser's own employee, so any other remembered name would be a lie.
    if (restored && !auth.ownDataActive) return;
    if (auth.linkedEmployeeId !== null) setEmployeeId(auth.linkedEmployeeId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isLoading, auth.linkedEmployeeId, auth.ownDataActive]);
  const [sort, setSort] = useState<{ column: SortColumn; dir: 'asc' | 'desc' }>({ column: 'appointment_date', dir: 'asc' });

  const [rescheduleTarget, setRescheduleTarget] = useState<AppointmentListItem | null>(null);

  const [weekAppointments, setWeekAppointments] = useState<AppointmentListItem[]>([]);
  const [weekLoading, setWeekLoading] = useState(true);
  const [weekError, setWeekError] = useState<Error | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    appointmentsApi.employees().then(setEmployees).catch(() => {});
  }, []);

  // Restored selection: load that day's month (the mobile view also loads one
  // for its strip) and drop the loading flag once it lands. NOT
  // handleSidebarDayClick: that one hops to the next day WITH visits when the
  // tapped day is empty, and a remembered day has to come back exactly as left.
  useEffect(() => {
    if (!restored) return;
    (async () => {
      try {
        await ensureMonthLoaded(restored.date);
        // Days that were appended below it (other months possible), also back.
        if (restored.chain.length > 1) setExtraDayData(await fetchDays(restored.chain.slice(1)));
      } catch {
        /* the list just shows what it could load */
      } finally {
        setChainLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Remember the selection as it changes. Skips week mode (the transient state
  // before the phone's first day is picked, whose "selected day" would be a
  // Monday nobody chose) and anything before auth settles, so the pre-default
  // employee can never overwrite a remembered one.
  useEffect(() => {
    if (!isMobile || auth.isLoading || mode !== 'chain' || chainDates.length === 0) return;
    writeWizytyListState({ date: chainDates[0], chain: chainDates, employeeId });
  }, [isMobile, auth.isLoading, mode, chainDates, employeeId]);

  // A remembered employee can be gone by the time we're back (deactivated). Check
  // once, when the list first arrives, and fall back to the user's own employee
  // rather than filtering the day down to a name that no longer exists.
  const restoredEmployeeCheckedRef = useRef(false);
  useEffect(() => {
    if (restoredEmployeeCheckedRef.current || !restored || employees.length === 0) return;
    restoredEmployeeCheckedRef.current = true;
    if (employeeId !== null && employeeId === restored.employeeId && !employees.some((e) => e.id === employeeId)) {
      setEmployeeId(auth.linkedEmployeeId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employees]);

  const loadWeek = useCallback(() => {
    if (mode !== 'week') return;
    setWeekLoading(true);
    setWeekError(null);
    appointmentsApi
      .list({ start_date: iso(weekStart), end_date: iso(addDays(weekStart, 6)) })
      .then((res) => setWeekAppointments(res.appointments))
      .catch((err: unknown) => setWeekError(err instanceof Error ? err : new Error(String(err))))
      .finally(() => setWeekLoading(false));
  }, [mode, weekStart]);

  useEffect(loadWeek, [loadWeek, reloadToken]);

  function reload() {
    setReloadToken((t) => t + 1);
  }

  function resetChainExtras() {
    setExtraDayData({});
    setNoMoreDays(false);
  }

  function exitChainMode() {
    setMode('week');
    setChainDates([]);
    resetChainExtras();
  }

  async function ensureMonthLoaded(dateStr: string): Promise<Map<string, AppointmentListItem[]>> {
    const key = dateStr.slice(0, 7);
    if (monthCache && monthCache.key === key) return monthCache.byDate;
    const [y, m] = key.split('-').map(Number);
    const start = `${key}-01`;
    const end = iso(new Date(y, m, 0));
    const res = await appointmentsApi.list({ start_date: start, end_date: end });
    const byDate = groupByDate(res.appointments);
    setMonthCache({ key, byDate });
    return byDate;
  }

  function groupByDate(list: AppointmentListItem[]): Map<string, AppointmentListItem[]> {
    const byDate = new Map<string, AppointmentListItem[]>();
    for (const a of list) {
      if (!byDate.has(a.appointment_date)) byDate.set(a.appointment_date, []);
      byDate.get(a.appointment_date)!.push(a);
    }
    return byDate;
  }

  /** One month's visits by day, fetched without touching monthCache and cached
   * in monthFetchRef until the next data change clears it. */
  async function fetchMonthByDate(key: string): Promise<Map<string, AppointmentListItem[]>> {
    const cached = monthFetchRef.current.get(key);
    if (cached) return cached;
    const [y, m] = key.split('-').map(Number);
    const res = await appointmentsApi.list({ start_date: `${key}-01`, end_date: iso(new Date(y, m, 0)) });
    const byDate = groupByDate(res.appointments);
    monthFetchRef.current.set(key, byDate);
    return byDate;
  }

  async function fetchDays(dates: string[]): Promise<Record<string, AppointmentListItem[]>> {
    const out: Record<string, AppointmentListItem[]> = {};
    for (const key of new Set(dates.map((d) => d.slice(0, 7)))) {
      const byDate = await fetchMonthByDate(key);
      for (const d of dates) if (d.startsWith(key)) out[d] = byDate.get(d) ?? [];
    }
    return out;
  }

  /** A day "has visits" for the phone's next-day search when at least one
   * non-cancelled/no-show/rescheduled visit belongs to the selected employee
   * (any employee while none is selected), same notion of "real" as the strip
   * dots and handleSidebarDayClick. */
  function dayHasVisitsFor(items: AppointmentListItem[]): boolean {
    return items.some((a) => a.status !== 'cancelled' && a.status !== 'no_show' && a.status !== 'rescheduled' && (employeeId === null || a.employee_id === employeeId));
  }

  /** "Pokaż kolejny dzień": append the next day (after the last one shown) that has
   * visits for the selected employee, scanning forward month by month. */
  async function loadNextVisitDay() {
    if (nextDayLoading || chainDates.length === 0) return;
    const last = chainDates[chainDates.length - 1];
    setNextDayLoading(true);
    try {
      const [ly, lm] = last.split('-').map(Number);
      let cursor = new Date(ly, lm - 1, 1);
      for (let i = 0; i < NEXT_DAY_SCAN_MONTHS; i++) {
        const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}`;
        const byDate = await fetchMonthByDate(key);
        const next = [...byDate.keys()].filter((d) => d > last && dayHasVisitsFor(byDate.get(d) ?? [])).sort()[0];
        if (next) {
          setExtraDayData((prev) => ({ ...prev, [next]: byDate.get(next) ?? [] }));
          setChainDates((prev) => [...prev, next]);
          return;
        }
        cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
      }
      setNoMoreDays(true);
    } catch (err) {
      console.error('Nie udało się wczytać kolejnego dnia', err);
    } finally {
      setNextDayLoading(false);
    }
  }

  /** Phone employee picker: the days appended below were chosen for the PREVIOUS
   * employee's visits, so a new employee starts again from the selected day. */
  function selectEmployee(id: number | null) {
    setEmployeeId(id);
    setChainDates((prev) => prev.slice(0, 1));
    resetChainExtras();
  }

  function hasReal(byDate: Map<string, AppointmentListItem[]>, dateStr: string): boolean {
    return (byDate.get(dateStr) ?? []).some((a) => a.status !== 'cancelled' && a.status !== 'no_show' && a.status !== 'rescheduled');
  }

  async function handleSidebarDayClick(dateStr: string) {
    setChainLoading(true);
    try {
      const byDate = await ensureMonthLoaded(dateStr);
      const sortedDaysWithData = [...byDate.keys()].filter((d) => hasReal(byDate, d)).sort();

      let target: string | null = hasReal(byDate, dateStr) ? dateStr : null;
      if (!target) {
        target = sortedDaysWithData.find((d) => d > dateStr) ?? null;
      }
      if (!target) {
        target = [...sortedDaysWithData].reverse().find((d) => d < dateStr) ?? null;
      }
      setMode('chain');
      setChainDates(target ? [target] : [dateStr]);
      resetChainExtras();
    } finally {
      setChainLoading(false);
    }
  }

  async function appendNextChainDay() {
    if (!monthCache || chainDates.length === 0) return;
    const last = chainDates[chainDates.length - 1];
    const sortedDaysWithData = [...monthCache.byDate.keys()].filter((d) => hasReal(monthCache.byDate, d)).sort();
    const next = sortedDaysWithData.find((d) => d > last);
    if (next) setChainDates((prev) => [...prev, next]);
  }

  const chainHasMore = useMemo(() => {
    if (mode !== 'chain' || !monthCache || chainDates.length === 0) return false;
    const last = chainDates[chainDates.length - 1];
    return [...monthCache.byDate.keys()].some((d) => hasReal(monthCache.byDate, d) && d > last);
  }, [mode, monthCache, chainDates]);

  const rawAppointments = useMemo(() => {
    if (mode === 'chain' && (monthCache || Object.keys(extraDayData).length > 0)) {
      // Days appended on the phone come from extraDayData (they may be in another
      // month than monthCache); everything else, from monthCache, as before.
      return chainDates.flatMap((d) => extraDayData[d] ?? monthCache?.byDate.get(d) ?? []).sort((a, b) => (a.appointment_date + a.start_time).localeCompare(b.appointment_date + b.start_time));
    }
    return weekAppointments;
  }, [mode, monthCache, chainDates, extraDayData, weekAppointments]);

  const filtered = useMemo(() => {
    let list = rawAppointments;
    if (employeeId) list = list.filter((a) => a.employee_id === employeeId);
    const q = searchQuery.toLowerCase().trim();
    if (q) list = list.filter((a) => [a.client_name, a.service_name].filter(Boolean).join(' ').toLowerCase().includes(q));

    if (mode === 'chain') return list; // ascending date+time, forced — already sorted that way above

    const { column, dir } = sort;
    const sorted = [...list].sort((a, b) => {
      let av: string | number = '';
      let bv: string | number = '';
      if (column === 'total_price' || column === 'satisfaction_score') {
        av = a[column] ?? 0;
        bv = b[column] ?? 0;
      } else if (column === 'appointment_date') {
        av = a.appointment_date + a.start_time;
        bv = b.appointment_date + b.start_time;
      } else {
        av = String(a[column] ?? '').toLowerCase();
        bv = String(b[column] ?? '').toLowerCase();
      }
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : av < bv ? -1 : av > bv ? 1 : 0;
      return dir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [rawAppointments, employeeId, searchQuery, sort, mode]);

  const revenue = useMemo(() => filtered.reduce((sum, a) => sum + (a.total_price || 0), 0), [filtered]);

  function handleSort(column: SortColumn) {
    setSort((cur) => (cur.column === column ? { column, dir: cur.dir === 'asc' ? 'desc' : 'asc' } : { column, dir: 'asc' }));
  }
  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return '↕';
    return sort.dir === 'asc' ? '↑' : '↓';
  }

  function goWeek(offset: number) {
    exitChainMode();
    setWeekStart((cur) => addDays(cur, offset * 7));
  }
  function goToday() {
    exitChainMode();
    setWeekStart(getMonday(new Date()));
  }
  function onDateInputChange(value: string) {
    if (!value) return;
    exitChainMode();
    const [y, m, d] = value.split('-').map(Number);
    setWeekStart(getMonday(new Date(y, m - 1, d)));
  }

  async function handleStatusUpdated() {
    if (isMobile && mode === 'chain' && chainDates.length > 0) {
      // Phone: swap fresh data in WITHOUT blanking the list. The blanking path
      // below would collapse a multi-day list to "Ładowanie…" and throw away
      // the scroll position after every status change or reschedule.
      monthFetchRef.current.clear();
      try {
        const key = chainDates[0].slice(0, 7);
        setMonthCache({ key, byDate: await fetchMonthByDate(key) });
        if (chainDates.length > 1) setExtraDayData(await fetchDays(chainDates.slice(1)));
      } catch {
        /* keep what's on screen; the next interaction retries */
      }
      return;
    }
    if (mode === 'chain' && chainDates.length > 0) {
      // Invalidate + immediately re-fetch (not just null it out) — `mode`
      // stays 'chain' so `rawAppointments` still expects `monthCache` to be
      // populated; nulling it without a re-fetch would silently fall through
      // to the (wrong, unrelated) week data in that memo. `chainLoading`
      // toggled around it so the table shows "Ładowanie..." for that gap
      // instead of a flash of stale/empty data.
      setChainLoading(true);
      setMonthCache(null);
      await ensureMonthLoaded(chainDates[0]);
      setChainLoading(false);
    } else {
      reload();
    }
  }

  function handleRowClick(appt: AppointmentListItem, event: MouseEvent) {
    if ((event.target as HTMLElement).closest('.status-badge') || (event.target as HTMLElement).closest('.action-icon-btn')) return;
    navigate(`/wizyty/${appt.id}`);
  }

  const rangeLabel = mode === 'chain' ? `${chainDates.length} dzień/dni z wizytami` : `${formatDateShort(iso(weekStart))} – ${formatDateShort(iso(addDays(weekStart, 6)))}`;
  const columns: Array<{ column: SortColumn; label: string; align?: 'right' }> = [
    { column: 'appointment_date', label: 'Data' },
    { column: 'start_time', label: 'Godzina' },
    { column: 'client_name', label: 'Klient' },
    { column: 'service_name', label: 'Usługa' },
    { column: 'employee_name', label: 'Pracownik' },
    { column: 'total_price', label: 'Kwota', align: 'right' },
    { column: 'status', label: 'Status' },
    { column: 'satisfaction_score', label: 'Ocena' },
  ];

  const loading = mode === 'chain' ? chainLoading : weekLoading;
  const error = mode === 'week' ? weekError : null;

  return (
    <div className="refined-page page-fills-viewport fade-in">
      {/* Page header lives at the TRUE page root now, spanning the full width
          (main content + sidebar), not just `.cal-main`'s narrower column —
          otherwise its `justify-content: space-between` button row only
          reaches `.cal-main`'s right edge, short of the sidebar's, instead of
          the actual viewport-aligned edge (user clarification, 2026-08-19:
          "page header buttons row był dosunięty do prawej strony viewport",
          same fix applied to CalendarDayPage.tsx). On mobile this whole
          header is dropped (TASK3/4) — title/subtitle text is gone outright,
          "Nowa wizyta" is the "+" in the fixed bottom nav, ViewSwitcher
          already self-hides below 640px (`.view-toggle{display:none}`), and
          "Rozlicz przeszłe wizyty" moves into AppShell's persistent
          logo+title row via a portal (below) so it stays reachable while
          scrolling instead of scrolling away with this header — all to
          reclaim viewport height for the card list. */}
      {!isMobile && (
        <header className="page-header">
          <div>
            <h1 className="page-title">Wizyty</h1>
            <p className="page-subtitle">{mode === 'chain' ? 'Widok dnia z bocznego paska' : 'Tydzień wizyt'}</p>
          </div>
          <div>
            {canWrite && (
              <ButtonLink variant="primary" icon="add" to="/wizyty/nowa">
                Nowa wizyta
              </ButtonLink>
            )}
            <ViewSwitcher active="list" date={iso(weekStart)} employeeId={employeeId} />
            <PastVisitsScanner />
          </div>
        </header>
      )}
      {isMobile && mobileHeaderSlot && createPortal(<PastVisitsScanner />, mobileHeaderSlot)}

      <div className="cal-grid-page">
      <div className="cal-main">
        {/* On mobile, Pracownik filter + search moved into the filter-icon
            modal (MobileWizytyCalendarView, TASK2) — this whole toolbar is
            desktop-only now; the day/week/month navigation is the fixed
            bottom bar instead. */}
        {!isMobile && (
          <div className="date-nav">
            {/* Grouped so mobile can lay these 4 out as a deterministic 2x2
                grid (Appointments.css @max-width:640px) instead of letting
                flex-wrap split them wherever the current viewport width
                happens to land — that produced a different, often-orphaned
                wrap pattern every few pixels of width (audit finding #1,
                mobile-audit-wizyty-list.md). */}
            <div className="date-nav-controls">
              <button type="button" className="nav-btn" onClick={() => goWeek(-1)}>
                ← Poprzedni
              </button>
              <input type="date" className="date-nav-date" aria-label="Wybierz tydzień" value={iso(weekStart)} onChange={(e) => onDateInputChange(e.target.value)} />
              <button type="button" className="nav-btn" onClick={goToday}>
                Dziś
              </button>
              <button type="button" className="nav-btn" onClick={() => goWeek(1)}>
                Następny →
              </button>
            </div>
            <span className="date-nav-range">{rangeLabel}</span>
            <div className="empf-divider" />
            <span className="empf-label">Pracownik:</span>
            <EmployeeFilter employees={employees} selectedId={employeeId} onSelect={setEmployeeId} allowAll />
            <div className="list-search">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input type="text" placeholder="Szukaj klienta, usługi..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </div>
          </div>
        )}

        {isMobile ? (
          <MobileWizytyCalendarView
            selectedDate={mode === 'chain' ? chainDates[0] ?? iso(weekStart) : iso(weekStart)}
            mode={mode}
            monthCache={monthCache}
            ensureMonthLoaded={ensureMonthLoaded}
            onDayClick={handleSidebarDayClick}
            appointments={filtered}
            loading={loading}
            onRowClick={handleRowClick}
            employees={employees}
            employeeId={employeeId}
            onSelectEmployee={selectEmployee}
            canWrite={canWrite}
            onDataChanged={handleStatusUpdated}
            loadedDays={mode === 'chain' && chainDates.length > 0 ? chainDates : []}
            onLoadNextDay={loadNextVisitDay}
            nextDayLoading={nextDayLoading}
            noMoreDays={noMoreDays}
          />
        ) : (
        <div className="table-container stack-cards-wrap">
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.column} className="th-sortable" style={col.align ? { textAlign: col.align } : undefined} aria-sort={mode === 'week' && sort.column === col.column ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    <button type="button" className="th-sort-btn" onClick={() => mode === 'week' && handleSort(col.column)} disabled={mode === 'chain'}>
                      {col.label} <span className="th-sort-icon" aria-hidden="true">{mode === 'week' ? sortIndicator(col.column) : ''}</span>
                    </button>
                  </th>
                ))}
                <th>
                  <span className="sr-only">Akcje</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="empty-state">
                    <p className="empty-text">Ładowanie wizyt...</p>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={9} className="empty-state">
                    <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                      Błąd ładowania wizyt: {error.message}
                    </p>
                    <Button variant="secondary" style={{ marginTop: '0.75rem' }} onClick={reload}>
                      Spróbuj ponownie
                    </Button>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-state">
                    <Icon name="calendar_today" className="empty-icon" />
                    <p className="empty-text">Brak wizyt w tym okresie.</p>
                  </td>
                </tr>
              ) : (
                filtered.map((appt) => {
                  const past = mode === 'chain' && isPast(appt.appointment_date, appt.end_time);
                  return (
                    <tr key={appt.id} className={`row-clickable${isWeekend(appt.appointment_date) ? ' weekend-row' : ''}${past ? ' row-past' : ''}`} onClick={(e) => handleRowClick(appt, e)}>
                      <td className="cell-date cell-name" data-label="Data">
                        {formatDateShort(appt.appointment_date)}
                      </td>
                      <td className="cell-time" data-label="Godzina">
                        {appt.start_time.slice(0, 5)}–{appt.end_time.slice(0, 5)}
                      </td>
                      <td data-label="Klient">{appt.client_name || '—'}</td>
                      <td className="cell-service" data-label="Usługa">
                        {appt.service_name || '—'}
                      </td>
                      <td data-label="Pracownik">
                        <span className="emp-cell">
                          <span className="emp-dot" style={{ background: empColor(appt.employee_id) }} />
                          <span className="emp-name">{appt.employee_name || '—'}</span>
                        </span>
                      </td>
                      <td className="cell-price" data-label="Kwota">
                        {formatPLN(appt.total_price)}
                      </td>
                      <td data-label="Status">
                        <StatusDropdown
                          appointmentId={appt.id}
                          currentStatus={appt.status}
                          appointmentDate={appt.appointment_date}
                          startTime={appt.start_time}
                          canWrite={canWrite}
                          onSuccess={handleStatusUpdated}
                        />
                      </td>
                      <td data-label="Ocena">
                        <span className={appt.satisfaction_score ? 'stars-desktop' : 'stars-none'}>{stars(appt.satisfaction_score)}</span>
                      </td>
                      <td className="cell-actions">
                        <div className="action-icons">
                          {(appt.status === 'scheduled' || appt.status === 'confirmed') && (
                            <button
                              type="button"
                              className="action-icon-btn action-icon-btn--reschedule"
                              title="Przełóż wizytę"
                              aria-label="Przełóż wizytę"
                              onClick={(e) => {
                                e.stopPropagation();
                                setRescheduleTarget(appt);
                              }}
                            >
                              <Icon name="sync" />
                            </button>
                          )}
                          <Link to={`/wizyty/${appt.id}/edytuj`} className="action-icon-btn" title="Edytuj" aria-label="Edytuj" onClick={(e) => e.stopPropagation()}>
                            <Icon name="edit" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {mode === 'chain' && chainHasMore && (
            <button type="button" className="list-chain-more" onClick={appendNextChainDay}>
              <Icon name="expand_more" /> Pokaż następny dzień
            </button>
          )}
          <div className="list-footer">
            <span>
              Wyświetlono <strong>{filtered.length}</strong> wizyt
            </span>
            <span>
              Przychód: <strong>{formatPLN(revenue)}</strong>
            </span>
          </div>
        </div>
        )}
      </div>

      <CalendarMonthSidebar selectedDate={mode === 'chain' ? chainDates[0] ?? iso(weekStart) : iso(weekStart)} onDayClick={handleSidebarDayClick} />
      </div>

      <RescheduleSheet
        appointment={rescheduleTarget}
        isOpen={rescheduleTarget !== null}
        onClose={() => setRescheduleTarget(null)}
        employees={employees}
        onRescheduled={handleStatusUpdated}
      />
    </div>
  );
}
