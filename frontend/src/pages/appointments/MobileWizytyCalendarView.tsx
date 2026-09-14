import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent, TouchEvent } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../../lib/icons/Icon';
import { formatPhone } from '../../lib/format';
import { empColor } from '../../lib/appointments/employeeColor';
import { Modal } from '../../components/ui/Modal';
import { Switch } from '../../components/ui/Switch';
import { useAuth } from '../../contexts/AuthContext';
import { EmployeeFilter } from './EmployeeFilter';
import { RescheduleSheet } from './RescheduleSheet';
import { StatusDropdown } from './StatusDropdown';
import type { AppointmentListItem, EmployeeOption } from '../../types/appointment';

/** Swipe-left threshold (px) to arm/trigger the reschedule sheet (TASK5) —
 * horizontal movement must also clearly dominate vertical (1.5x) so an
 * ordinary vertical scroll gesture starting on a card never gets mistaken
 * for a swipe. */
const SWIPE_TRIGGER_PX = -64;
const SWIPE_MAX_PX = -96;

const MONTH_WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];
/** Strip is Mon–Sat only (mod #1) — the salon doesn't book Sundays. */
const STRIP_WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So'];
const MONTH_NAMES = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
const WEEKDAY_LABELS = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota'];

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}
function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}
function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}
function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = (day === 0 ? -6 : 1) - day;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}
function formatDateShort(dateStr: string): string {
  const [y, m, d] = dateStr.split('-');
  return `${d}.${m}.${y}`;
}
function formatDateLong(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  const weekday = WEEKDAY_LABELS[date.getDay()];
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)}, ${d} ${MONTH_NAMES[m - 1]} ${y}`;
}
/** "(hh)h (mm)min" / "(mm)min" — shorter format, replaces the old spelled-out
 * "hh godzin mm minut" (mobile card only, per redesign request). */
function formatDuration(startTime: string, endTime: string): string {
  const [sh, sm] = startTime.slice(0, 5).split(':').map(Number);
  const [eh, em] = endTime.slice(0, 5).split(':').map(Number);
  const minutes = eh * 60 + em - (sh * 60 + sm);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}min` : `${m}min`;
}
/** Local-time minutes remaining until the visit's scheduled start —
 * `${date}T${time}` (no timezone designator) parses as browser-local per the
 * Date constructor's spec, same assumption WizytaDetailPage's isNoShowAllowed
 * already makes. `null` once the countdown stops being meaningful: the visit
 * already started/resolved (in_progress/completed/cancelled/no_show), or its
 * start time has already passed. `nowMs` comes from the card list's shared
 * 60s tick so every card updates together instead of each on its own timer. */
function minutesUntilStart(appt: AppointmentListItem, nowMs: number): number | null {
  if (!(appt.status === 'scheduled' || appt.status === 'pending' || appt.status === 'confirmed')) return null;
  const startMs = new Date(`${appt.appointment_date}T${appt.start_time}`).getTime();
  const diffMin = Math.round((startMs - nowMs) / 60000);
  return diffMin >= 0 ? diffMin : null;
}
/** Ticks once a minute so the mobile card list's "start za Nmin" countdowns
 * stay live without a per-card timer. Initialised to Date.now() (not a fixed
 * value) so the first render already shows the correct countdown. */
function useNowTick(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
/** mod #4: direct-dial `tel:` href instead of clipboard-copy — raw digits,
 * `+48` prefix assumed for bare 9-digit national numbers (same assumption
 * `formatPhone` in lib/format.ts already makes for display). */
function telHref(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 9) return `tel:+48${digits}`;
  if (digits.length === 11 && digits.startsWith('48')) return `tel:+${digits}`;
  return `tel:${digits}`;
}

/**
 * Custom hook, local to this file — the codebase is otherwise entirely
 * CSS-breakpoint driven (no JS media queries anywhere else), but this
 * component's mount itself has a side effect (auto-selecting "today", which
 * flips the shared `mode`/`chainDates` state also read by the desktop
 * table). A CSS-only `display:none` would still mount it on desktop and fire
 * that effect there too, silently knocking the desktop view out of its
 * default week view. Gating the mount in JS avoids that; same 640px cutoff
 * as Appointments.css's existing mobile breakpoint.
 */
function useIsMobile(breakpointPx: number): boolean {
  const [isMobile, setIsMobile] = useState(() => (typeof window !== 'undefined' ? window.innerWidth <= breakpointPx : false));
  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpointPx}px)`);
    const onChange = () => setIsMobile(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [breakpointPx]);
  return isMobile;
}

export { useIsMobile };

export interface MobileWizytyCalendarViewProps {
  /** Currently-active date — `chainDates[0] ?? iso(weekStart)` from the host page. */
  selectedDate: string;
  mode: 'week' | 'chain';
  monthCache: { key: string; byDate: Map<string, AppointmentListItem[]> } | null;
  ensureMonthLoaded: (dateStr: string) => Promise<Map<string, AppointmentListItem[]>>;
  onDayClick: (dateStr: string) => void;
  appointments: AppointmentListItem[];
  loading: boolean;
  chainHasMore: boolean;
  onShowNextDay: () => void;
  onRowClick: (appt: AppointmentListItem, event: MouseEvent) => void;
  employees: EmployeeOption[];
  employeeId: number | null;
  onSelectEmployee: (id: number | null) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  canWrite: boolean;
  /** Refresh the host page's data after a successful reschedule (TASK5) —
   * same callback StatusChangeModal's `onSuccess` already uses. */
  onDataChanged: () => void;
}

/**
 * Proposal 3 (week-strip + cards), picked over proposal 1's month-first
 * layout — mods per user: 6-day strip (no Sunday), strip+month moved below
 * the card list instead of above it, no price on the card, `tel:` direct-dial
 * instead of clipboard-copy.
 */
export function MobileWizytyCalendarView({
  selectedDate,
  mode,
  monthCache,
  ensureMonthLoaded,
  onDayClick,
  appointments,
  loading,
  chainHasMore,
  onShowNextDay,
  onRowClick,
  employees,
  employeeId,
  onSelectEmployee,
  searchQuery,
  onSearchChange,
  canWrite,
  onDataChanged,
}: MobileWizytyCalendarViewProps) {
  const auth = useAuth();
  const [today] = useState(() => iso(new Date()));
  const nowTick = useNowTick(60_000);
  const [swipeState, setSwipeState] = useState<{ id: number; dx: number } | null>(null);
  const [rescheduleAppt, setRescheduleAppt] = useState<AppointmentListItem | null>(null);
  const touchStartRef = useRef<{ x: number; y: number; id: number } | null>(null);
  const suppressClickRef = useRef<number | null>(null);
  const [weekAnchor, setWeekAnchor] = useState(() => {
    const [y, m, d] = selectedDate.split('-').map(Number);
    return getMonday(new Date(y, m - 1, d));
  });
  const [monthAnchor, setMonthAnchor] = useState(() => {
    const [y, m] = selectedDate.slice(0, 7).split('-').map(Number);
    return new Date(y, m - 1, 1);
  });
  const [monthExpanded, setMonthExpanded] = useState(false);
  const [filterModalOpen, setFilterModalOpen] = useState(false);
  // Filter popup is staged: Pracownik/search and both admin toggles edit local
  // draft state while the popup is open, and only commit — onSelectEmployee /
  // onSearchChange, plus the admin-view POST(s) + reload — once the popup
  // actually closes. Flipping a switch mid-review no longer slams it shut.
  const [draftEmployeeId, setDraftEmployeeId] = useState<number | null>(employeeId);
  const [draftSearchQuery, setDraftSearchQuery] = useState(searchQuery);
  const [draftAdminView, setDraftAdminView] = useState(auth.adminViewActive);
  const [draftOwnData, setDraftOwnData] = useState(auth.ownDataActive);
  // "Widok administratora" / "Dane własne" (config/admin_view.py — mirrors
  // the Jinja sidebar toggle). Both POST to a Flask session flag and reload
  // the page, so this only needs to block a double-submit mid round-trip —
  // there's no client-side state to reconcile once the reload lands.
  const [scopeTogglePending, setScopeTogglePending] = useState(false);

  function openFilterModal() {
    setDraftEmployeeId(employeeId);
    setDraftSearchQuery(searchQuery);
    setDraftAdminView(auth.adminViewActive);
    setDraftOwnData(auth.ownDataActive);
    setFilterModalOpen(true);
  }

  function closeFilterModal() {
    setFilterModalOpen(false);
    onSelectEmployee(draftEmployeeId);
    onSearchChange(draftSearchQuery);
    if (draftAdminView !== auth.adminViewActive || draftOwnData !== auth.ownDataActive) {
      setScopeTogglePending(true);
      auth.applyScopeToggles(draftAdminView, draftOwnData).catch(() => setScopeTogglePending(false));
    }
  }
  const autoSelectedRef = useRef(false);
  const selectedDateMountedRef = useRef(false);
  const listRef = useRef<HTMLDivElement>(null);

  // Scroll the card list back to top on every user-driven day change (strip
  // tap, month-grid tap, "pokaż następny dzień") — skips the very first
  // selectedDate this component sees (the auto-select-today below), since
  // scroll position is already 0 at initial page load and animating it
  // would just be unwanted motion.
  //
  // `window.scrollTo` would be a no-op here: AppShell (components.css
  // `.app-shell-content{flex:1;overflow:auto}`) makes `<main>` the actual
  // scroll container, not the window — the whole shell frame is fixed-height
  // and never scrolls itself. Walk up to that real scroll container instead.
  useEffect(() => {
    if (!selectedDateMountedRef.current) {
      selectedDateMountedRef.current = true;
      return;
    }
    listRef.current?.closest('.app-shell-content')?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [selectedDate]);

  // `monthAnchor` is the single source of truth for which month's data is
  // loaded (the host page's `monthCache` only ever holds one month at a
  // time) — the week strip just keeps it in sync with whichever month its
  // Monday falls in, so both the strip's dots and the expandable grid read
  // the same cache instead of two `ensureMonthLoaded` calls racing each
  // other and thrashing the shared cache between two different months.
  useEffect(() => {
    const y = weekAnchor.getFullYear();
    const m = weekAnchor.getMonth();
    setMonthAnchor((cur) => (cur.getFullYear() === y && cur.getMonth() === m ? cur : new Date(y, m, 1)));
  }, [weekAnchor]);

  useEffect(() => {
    ensureMonthLoaded(iso(monthAnchor));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monthAnchor]);

  useEffect(() => {
    if (autoSelectedRef.current) return;
    autoSelectedRef.current = true;
    if (mode !== 'chain') onDayClick(today);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const monthKey = `${monthAnchor.getFullYear()}-${String(monthAnchor.getMonth() + 1).padStart(2, '0')}`;
  const daysWithAppointments = useMemo(() => {
    const set = new Set<string>();
    if (monthCache?.key !== monthKey) return set;
    for (const [dateStr, appts] of monthCache.byDate) {
      if (appts.some((a) => a.status !== 'cancelled' && a.status !== 'no_show')) set.add(dateStr);
    }
    return set;
  }, [monthCache, monthKey]);

  function handleDayTap(dateStr: string) {
    // Bug fix: a month-grid pick outside the currently-shown week used to
    // leave the strip pointing at the old week — resync it to the picked
    // day's own week. No-op for a strip tap itself (already that week).
    const [y, m, d] = dateStr.split('-').map(Number);
    setWeekAnchor(getMonday(new Date(y, m - 1, d)));
    onDayClick(dateStr);
  }

  // TASK5 — card swipe-left opens the reschedule sheet. Hand-rolled (no
  // gesture library in this project's deps): track the touch start point,
  // and only treat the drag as a horizontal swipe once it clearly dominates
  // vertical movement, so an ordinary scroll starting on a card is never
  // hijacked. `suppressClickRef` stops the synthetic click mobile browsers
  // fire after touchend from also triggering the card's normal
  // navigate-to-detail `onClick`.
  function handleCardTouchStart(apptId: number, e: TouchEvent<HTMLDivElement>) {
    const t = e.touches[0];
    touchStartRef.current = { x: t.clientX, y: t.clientY, id: apptId };
  }
  function handleCardTouchMove(apptId: number, e: TouchEvent<HTMLDivElement>) {
    const start = touchStartRef.current;
    if (!start || start.id !== apptId) return;
    const t = e.touches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (dx < 0 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      setSwipeState({ id: apptId, dx: Math.max(dx, SWIPE_MAX_PX) });
    }
  }
  function handleCardTouchEnd(apptId: number, appt: AppointmentListItem) {
    touchStartRef.current = null;
    const triggered = swipeState?.id === apptId && swipeState.dx <= SWIPE_TRIGGER_PX;
    setSwipeState(null);
    if (triggered) {
      suppressClickRef.current = apptId;
      setRescheduleAppt(appt);
    }
  }
  function handleCardClick(appt: AppointmentListItem, e: MouseEvent) {
    if (suppressClickRef.current === appt.id) {
      suppressClickRef.current = null;
      return;
    }
    onRowClick(appt, e);
  }

  const stripDays = useMemo(() => Array.from({ length: 6 }, (_, i) => addDays(weekAnchor, i)), [weekAnchor]);

  const totalDays = daysInMonth(monthAnchor.getFullYear(), monthAnchor.getMonth());
  const firstWeekday = (new Date(monthAnchor.getFullYear(), monthAnchor.getMonth(), 1).getDay() + 6) % 7;
  const monthCells: Array<{ day: number; dateStr: string } | null> = [];
  for (let i = 0; i < firstWeekday; i++) monthCells.push(null);
  for (let d = 1; d <= totalDays; d++) monthCells.push({ day: d, dateStr: `${monthKey}-${String(d).padStart(2, '0')}` });

  return (
    <div className="mob-cal-view">
      <div className="mob-appt-list" ref={listRef}>
        {selectedDate && <div className="mob-selected-date-label">{formatDateLong(selectedDate)}</div>}
        {loading ? (
          <p className="empty-text">Ładowanie wizyt...</p>
        ) : appointments.length === 0 ? (
          <div className="empty-state">
            <Icon name="calendar_today" className="empty-icon" />
            <p className="empty-text">Brak wizyt tego dnia.</p>
          </div>
        ) : (
          // `transition: 'none'` while actively dragging (below) — the card's
          // own CSS class carries a 0.2s snap-back transition, which would
          // otherwise smooth (lag behind) every touchmove update too, instead
          // of tracking the finger 1:1. Dropping the inline style entirely on
          // release (swipeState → null) lets that CSS transition take back
          // over for the snap.
          appointments.map((appt) => {
            const startsInMin = minutesUntilStart(appt, nowTick);
            return (
            <div
              key={appt.id}
              className={[
                'mob-appt-card',
                appt.status === 'cancelled' || appt.status === 'no_show' ? 'mob-appt-card--muted' : '',
                swipeState?.id === appt.id && swipeState.dx <= SWIPE_TRIGGER_PX ? 'mob-appt-card--swipe-armed' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              style={swipeState?.id === appt.id ? { transform: `translateX(${swipeState.dx}px)`, transition: 'none' } : undefined}
              onClick={(e) => handleCardClick(appt, e)}
              onTouchStart={(e) => handleCardTouchStart(appt.id, e)}
              onTouchMove={(e) => handleCardTouchMove(appt.id, e)}
              onTouchEnd={() => handleCardTouchEnd(appt.id, appt)}
            >
              <div className="mob-appt-top">
                {/* End time dropped, duration forced to its own line (not
                    just wrap) — user's explicit format. */}
                <span className="mob-appt-datetime">
                  <span className="mob-appt-datetime-line1">
                    {formatDateShort(appt.appointment_date)} <span className="mob-appt-at">@</span> {appt.start_time.slice(0, 5)}
                  </span>
                  <span className="mob-appt-duration">
                    ({formatDuration(appt.start_time, appt.end_time)}
                    {startsInMin !== null ? `, start za ${startsInMin}min` : ''})
                  </span>
                </span>
                <StatusDropdown
                  appointmentId={appt.id}
                  currentStatus={appt.status}
                  appointmentDate={appt.appointment_date}
                  startTime={appt.start_time}
                  canWrite={canWrite}
                  onSuccess={onDataChanged}
                />
              </div>

              {/* Klient/Tel. — labels in one row, values in the row below
                  (fix2), not a single "Klient: X  Tel.: Y" line. */}
              <div className="mob-appt-kv-grid">
                <span className="mob-appt-label">Klient</span>
                <span className="mob-appt-label">Tel.</span>
                <span className="mob-appt-kv-value">{appt.client_name || '—'}</span>
                {appt.client_phone ? (
                  <a className="mob-appt-tel mob-appt-kv-value" href={telHref(appt.client_phone)} onClick={(e) => e.stopPropagation()}>
                    {formatPhone(appt.client_phone)}
                  </a>
                ) : (
                  <span className="mob-appt-kv-value">—</span>
                )}
              </div>

              <div className="mob-appt-row mob-appt-2col">
                <span>
                  <span className="mob-appt-label">Pracownik:</span>{' '}
                  <span className="emp-cell">
                    <span className="emp-dot" style={{ background: empColor(appt.employee_id) }} />
                    {appt.employee_name || '—'}
                  </span>
                </span>
                <span>
                  <span className="mob-appt-label">Usługa:</span> {appt.service_name || '—'}
                </span>
              </div>

              {/* Minimal "this is tappable" hint (TASK3). */}
              <Icon name="chevron_right" className="mob-appt-tap-hint" />
            </div>
            );
          })
        )}
        {mode === 'chain' && chainHasMore && (
          <button type="button" className="list-chain-more" onClick={onShowNextDay}>
            <Icon name="expand_more" /> Pokaż następny dzień
          </button>
        )}
      </div>

      {/* Fixed to the viewport bottom (user's follow-up ask) — strip is the
          2nd element from the bottom edge, the expand toggle is the 1st
          (bottom-most); the month grid, when open, stacks above the strip
          as a 3rd tier rather than pushing into document flow, since a
          `position: fixed` sibling can no longer sit "between" the cards
          and the strip. `.mob-appt-list` carries matching bottom padding
          (ui-ux-pro-max `fixed-element-offset`) so the last card is never
          hidden under this bar, and the bar itself adds
          `env(safe-area-inset-bottom)` (`safe-area-awareness`) so it clears
          the iOS home-indicator instead of sitting under it. */}
      <div className="mob-fixed-nav">
        {monthExpanded && (
          <div className="mob-cal-grid-wrap">
            <div className="mob-cal-topbar">
              <button type="button" className="mob-cal-nav-btn" onClick={() => setMonthAnchor((cur) => addMonths(cur, -1))} aria-label="Poprzedni miesiąc">
                <Icon name="chevron_left" />
              </button>
              <span className="mob-cal-month-label">
                {MONTH_NAMES[monthAnchor.getMonth()]} {monthAnchor.getFullYear()}
              </span>
              <button type="button" className="mob-cal-nav-btn" onClick={() => setMonthAnchor((cur) => addMonths(cur, 1))} aria-label="Następny miesiąc">
                <Icon name="chevron_right" />
              </button>
            </div>
            <div className="mob-cal-weekdays">
              {MONTH_WEEKDAYS.map((w) => (
                <span key={w}>{w}</span>
              ))}
            </div>
            <div className="mob-cal-days">
              {monthCells.map((cell, i) =>
                cell === null ? (
                  <span key={`e${i}`} className="mob-cal-day empty" />
                ) : (
                  <button
                    key={cell.dateStr}
                    type="button"
                    className={[
                      'mob-cal-day',
                      daysWithAppointments.has(cell.dateStr) ? 'has-appointments' : '',
                      cell.dateStr === today ? 'today' : '',
                      cell.dateStr === selectedDate ? 'selected' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    onClick={() => {
                      setMonthExpanded(false);
                      handleDayTap(cell.dateStr);
                    }}
                  >
                    {cell.day}
                  </button>
                ),
              )}
            </div>
          </div>
        )}

        <div className="mob-strip-wrap">
          <button type="button" className="mob-cal-nav-btn" onClick={() => setWeekAnchor((cur) => addDays(cur, -7))} aria-label="Poprzedni tydzień">
            <Icon name="chevron_left" />
          </button>
          <div className="mob-week-strip">
            {stripDays.map((d, i) => {
              const dateStr = iso(d);
              return (
                <button
                  key={dateStr}
                  type="button"
                  className={[
                    'mob-strip-day',
                    daysWithAppointments.has(dateStr) ? 'has-appointments' : '',
                    dateStr === today ? 'today' : '',
                    dateStr === selectedDate ? 'selected' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => handleDayTap(dateStr)}
                >
                  <span className="wd">{STRIP_WEEKDAYS[i]}</span>
                  <span className="num">{d.getDate()}</span>
                </button>
              );
            })}
          </div>
          <button type="button" className="mob-cal-nav-btn" onClick={() => setWeekAnchor((cur) => addDays(cur, 7))} aria-label="Następny tydzień">
            <Icon name="chevron_right" />
          </button>
        </div>

        {/* Bottom-most row (TASK4/5): "+" fixed-width on the left, month
            toggle taking the rest of the width in the center, filter
            fixed-width on the right — all icon-only, `.mob-cal-nav-btn`'s
            1px border / 2px radius / token colors. */}
        <div className="mob-fixed-nav-actions">
          {canWrite && (
            <Link to="/wizyty/nowa" className="mob-cal-nav-btn primary" aria-label="Nowa wizyta" title="Nowa wizyta">
              <Icon name="add" />
            </Link>
          )}
          <button type="button" className="mob-cal-nav-btn mob-month-toggle-btn" onClick={() => setMonthExpanded((v) => !v)} aria-pressed={monthExpanded} aria-label={monthExpanded ? 'Ukryj pełny miesiąc' : 'Pokaż pełny miesiąc'} title={monthExpanded ? 'Ukryj pełny miesiąc' : 'Pokaż pełny miesiąc'}>
            <Icon name="calendar_today" />
          </button>
          <button
            type="button"
            className={`mob-cal-nav-btn${employeeId !== null || searchQuery.trim() !== '' ? ' has-active-filter' : ''}`}
            onClick={openFilterModal}
            aria-label="Filtry: pracownik, szukaj"
            title="Filtry"
          >
            <Icon name="filter_list" />
          </button>
        </div>
      </div>

      <Modal isOpen={filterModalOpen} onClose={closeFilterModal} title="Filtry">
        <div className="mob-filter-modal-body">
          <div>
            <span className="empf-label">Pracownik:</span>
            <EmployeeFilter employees={employees} selectedId={draftEmployeeId} onSelect={setDraftEmployeeId} allowAll />
          </div>
          <div className="list-search">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input type="text" placeholder="Szukaj klienta, usługi..." value={draftSearchQuery} onChange={(e) => setDraftSearchQuery(e.target.value)} />
          </div>

          {auth.isSuperuser && (
            <div className="mob-scope-toggles">
              <Switch
                id="mob-admin-view-toggle"
                label="Widok administratora"
                hint="Pokaż moje własne wizyty na liście"
                checked={draftAdminView}
                disabled={scopeTogglePending}
                onChange={(enabled) => {
                  setDraftAdminView(enabled);
                  if (!enabled) setDraftOwnData(false);
                }}
              />
              <Switch
                id="mob-own-data-toggle"
                label="Dane własne"
                hint="Pokaż wyłącznie moje wizyty"
                checked={draftOwnData}
                disabled={scopeTogglePending || !draftAdminView}
                onChange={setDraftOwnData}
              />
            </div>
          )}
        </div>
      </Modal>

      <RescheduleSheet
        appointment={rescheduleAppt}
        isOpen={rescheduleAppt !== null}
        onClose={() => setRescheduleAppt(null)}
        employees={employees}
        onRescheduled={onDataChanged}
      />
    </div>
  );
}
