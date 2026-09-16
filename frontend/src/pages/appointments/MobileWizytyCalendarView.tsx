import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent, TouchEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Icon } from '../../lib/icons/Icon';
import { formatPhone } from '../../lib/format';
import { Button } from '../../components/ui/Button';
import { useAuth } from '../../contexts/AuthContext';
import { RescheduleSheet } from './RescheduleSheet';
import { StatusDropdown } from './StatusDropdown';
import type { AppointmentListItem, EmployeeOption } from '../../types/appointment';

/** Swipe-left threshold (px) to arm/trigger the reschedule sheet (TASK5) —
 * horizontal movement must also clearly dominate vertical (1.5x) so an
 * ordinary vertical scroll gesture starting on a card never gets mistaken
 * for a swipe. Widened from the original -64/-96 so the icon+label reveal
 * (.mob-appt-swipe-content, 7.5rem/120px wide) has room to clear the card
 * before arming — the label CANNOT be readable at a max reveal narrower
 * than its own box, that's a hard clip, not a style knob. Narrower than an
 * earlier version of this (-112/-160): wrapping the label to 2 centered
 * lines (below) needs less box width than one long nowrap line did. */
const SWIPE_TRIGGER_PX = -84;
const SWIPE_MAX_PX = -120;
/** Mirror thresholds for swipe-RIGHT → navigate to visit details. */
const SWIPE_TRIGGER_PX_RIGHT = 84;
const SWIPE_MAX_PX_RIGHT = 120;

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
/** mod #4: direct-dial `tel:` href instead of clipboard-copy — raw digits,
 * `+48` prefix assumed for bare 9-digit national numbers (same assumption
 * `formatPhone` in lib/format.ts already makes for display). */
function telHref(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 9) return `tel:+48${digits}`;
  if (digits.length === 11 && digits.startsWith('48')) return `tel:+${digits}`;
  return `tel:${digits}`;
}
/** Same local-time parsing assumption as the rest of this file (backend
 * sends no timezone designator) — a one-shot check at the moment the card
 * list renders, not a live countdown, so no ticking timer is needed for it. */
function isUpcoming(appt: AppointmentListItem, nowMs: number): boolean {
  if (!(appt.status === 'scheduled' || appt.status === 'confirmed')) return false;
  const startMs = new Date(`${appt.appointment_date}T${appt.start_time}`).getTime();
  return startMs >= nowMs;
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
  onRowClick: (appt: AppointmentListItem, event: MouseEvent) => void;
  employees: EmployeeOption[];
  employeeId: number | null;
  onSelectEmployee: (id: number | null) => void;
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
  onRowClick,
  employees,
  employeeId,
  onSelectEmployee,
  canWrite,
  onDataChanged,
}: MobileWizytyCalendarViewProps) {
  const auth = useAuth();
  const navigate = useNavigate();
  const [today] = useState(() => iso(new Date()));
  const [swipeState, setSwipeState] = useState<{ id: number; dx: number } | null>(null);
  const [rescheduleAppt, setRescheduleAppt] = useState<AppointmentListItem | null>(null);
  const touchStartRef = useRef<{ x: number; y: number; id: number } | null>(null);
  const suppressClickRef = useRef<number | null>(null);
  const cardRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const [weekAnchor, setWeekAnchor] = useState(() => {
    const [y, m, d] = selectedDate.split('-').map(Number);
    return getMonday(new Date(y, m - 1, d));
  });
  const [monthAnchor, setMonthAnchor] = useState(() => {
    const [y, m] = selectedDate.slice(0, 7).split('-').map(Number);
    return new Date(y, m - 1, 1);
  });
  const [monthExpanded, setMonthExpanded] = useState(false);

  // Default onload state for a superuser: auto-engage "Widok administratora"
  // ON but "Dane własne" OFF. Own-data ON pins the visible list to the
  // superuser's own linked employee server-side regardless of what's picked
  // in the employee selector below — with it off, the selector's default
  // still lands them on their own employee (WizytyListPage's own
  // default-effect), but they can actually switch to someone else's visits
  // from there, which own-data=true was silently blocking. No mobile UI
  // exposes these toggles any more (the filter modal that used to host them
  // is gone) — superuser control over them lives in the Jinja sidebar.
  //
  // sessionStorage-backed ATTEMPT COUNTER, not a React ref and not a plain
  // one-shot flag. Two failure modes this has to survive at once:
  //   1) `applyScopeToggles` calls `window.location.reload()` when it
  //      changes anything, which wipes every in-memory ref on the next
  //      mount — a ref guard here means "retry forever if the state never
  //      matches", which is exactly what caused the ~0.1s reload loop this
  //      was first built to stop.
  //   2) A single-attempt sessionStorage flag stops the loop but has no
  //      resilience: if that one attempt's second POST (own-data) happens
  //      to get interrupted by a reload racing in from elsewhere before it
  //      completes — which is exactly what happened here, own_data stayed
  //      stuck at true forever after — there's no second try, ever, for
  //      that browser tab.
  // A capped counter gets both: bounded (never loops), but gets a few real
  // shots at actually landing instead of just one. Re-checks the target
  // condition fresh every render (not "did I already try"), so it also
  // naturally stops retrying the moment the state is actually correct.
  useEffect(() => {
    if (auth.isLoading || !auth.isSuperuser) return;
    if (auth.adminViewActive && !auth.ownDataActive) return; // already correct
    const key = 'wizyty-mobile-superuser-scope-default-attempts';
    const attempts = Number(sessionStorage.getItem(key) ?? '0');
    const MAX_ATTEMPTS = 3;
    if (attempts >= MAX_ATTEMPTS) return;
    sessionStorage.setItem(key, String(attempts + 1));
    auth.applyScopeToggles(true, false).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isLoading, auth.isSuperuser, auth.adminViewActive, auth.ownDataActive]);

  // Employee-select popup — "rolls up" from the bottom-actions row and
  // "collapses down" on pick/dismiss. `employeePopupMounted` controls
  // presence in the DOM; `employeePopupOpen` drives the open/closed CSS
  // class, kept as a separate tick (rAF on open) so the transform
  // transition actually has a "from" state to animate away from, and
  // separate from unmount (setTimeout on close) so the 0.2s collapse
  // animation gets to play before the sheet disappears.
  const [employeePopupMounted, setEmployeePopupMounted] = useState(false);
  const [employeePopupOpen, setEmployeePopupOpen] = useState(false);
  function openEmployeePopup() {
    setEmployeePopupMounted(true);
    requestAnimationFrame(() => setEmployeePopupOpen(true));
  }
  function closeEmployeePopup() {
    setEmployeePopupOpen(false);
    setTimeout(() => setEmployeePopupMounted(false), 200);
  }
  const selectedEmployeeName = employees.find((e) => e.id === employeeId)?.full_name ?? '—';

  const autoSelectedRef = useRef(false);
  const listRef = useRef<HTMLDivElement>(null);

  // On every appointments-list update (day change, filter change, a
  // reschedule/status change that reloads the list, etc.) — jump to and
  // highlight the next upcoming visit instead of just resetting scroll to
  // top. Runs on first mount too (not skipped), so opening the list already
  // lands you on what's next. Falls back to scrolling to top when there's no
  // upcoming visit in the current list (a past day, or every visit today has
  // already started) so switching away from a scrolled-down list still lands
  // somewhere sane.
  //
  // `window.scrollTo` would be a no-op here: AppShell (components.css
  // `.app-shell-content{flex:1;overflow:auto}`) makes `<main>` the actual
  // scroll container, not the window — the whole shell frame is fixed-height
  // and never scrolls itself. Walk up to that real scroll container instead.
  useEffect(() => {
    if (appointments.length === 0) return;
    const target = appointments.find((a) => isUpcoming(a, Date.now()));
    const targetEl = target && cardRefs.current.get(target.id);
    if (target && targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightId(target.id);
      const timer = setTimeout(() => setHighlightId(null), 600);
      return () => clearTimeout(timer);
    }
    listRef.current?.closest('.app-shell-content')?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [appointments]);

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
      if (appts.some((a) => a.status !== 'cancelled' && a.status !== 'no_show' && a.status !== 'rescheduled')) set.add(dateStr);
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

  const [findingNextVisit, setFindingNextVisit] = useState(false);
  // Empty-day CTA — scans forward month-by-month (via the same
  // `ensureMonthLoaded` cache the strip/month grid share, unfiltered by
  // employee server-side, so filtered here) for the next day with a
  // qualifying visit for the ACTIVE employee filter, then jumps there. The
  // existing scroll-to-upcoming effect (keyed on `appointments`) takes it
  // from there once that day's data loads — no separate scroll/highlight
  // logic needed here. Capped at 6 months ahead so a genuinely empty future
  // doesn't spin forever. Ignores the free-text search filter (this is
  // about the employee's own schedule, not a client/service lookup).
  async function goToNextVisit() {
    setFindingNextVisit(true);
    try {
      let cursor = new Date(monthAnchor);
      for (let i = 0; i < 6; i++) {
        const cache = await ensureMonthLoaded(iso(cursor));
        const dateStrs = Array.from(cache.keys()).sort();
        for (const dateStr of dateStrs) {
          if (dateStr <= selectedDate) continue;
          const list = cache.get(dateStr) ?? [];
          const hasQualifying = list.some(
            (a) => (employeeId === null || a.employee_id === employeeId) && (a.status === 'scheduled' || a.status === 'confirmed'),
          );
          if (hasQualifying) {
            handleDayTap(dateStr);
            return;
          }
        }
        cursor = addMonths(cursor, 1);
      }
    } finally {
      setFindingNextVisit(false);
    }
  }

  // TASK5 — card swipe-left opens the reschedule sheet. Hand-rolled (no
  // gesture library in this project's deps): track the touch start point,
  // and only treat the drag as a horizontal swipe once it clearly dominates
  // vertical movement, so an ordinary scroll starting on a card is never
  // hijacked. `suppressClickRef` stops the synthetic click mobile browsers
  // fire after touchend from also triggering the card's normal
  // navigate-to-detail `onClick`.
  // Only a scheduled/confirmed visit can be rescheduled (backend eligibility
  // rule, services/appointment_service.py's reschedule_appointment) — never
  // arm the gesture for anything else, so cancelled/no_show/completed/
  // rescheduled cards don't reveal the swipe affordance at all.
  function isReschedulable(status: AppointmentListItem['status']) {
    return status === 'scheduled' || status === 'confirmed';
  }
  // Start tracking for BOTH directions — the reschedulable gate for
  // swipe-left is enforced in the move handler below (TASK3: swipe-right
  // navigates to visit details and is valid for every status).
  function handleCardTouchStart(apptId: number, e: TouchEvent<HTMLDivElement>) {
    const t = e.touches[0];
    touchStartRef.current = { x: t.clientX, y: t.clientY, id: apptId };
  }
  function handleCardTouchMove(apptId: number, status: AppointmentListItem['status'], e: TouchEvent<HTMLDivElement>) {
    const start = touchStartRef.current;
    if (!start || start.id !== apptId) return;
    const t = e.touches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (Math.abs(dx) <= Math.abs(dy) * 1.5) return;
    if (dx < 0 && isReschedulable(status)) {
      setSwipeState({ id: apptId, dx: Math.max(dx, SWIPE_MAX_PX) });
    } else if (dx > 0) {
      setSwipeState({ id: apptId, dx: Math.min(dx, SWIPE_MAX_PX_RIGHT) });
    }
  }
  function handleCardTouchEnd(apptId: number, appt: AppointmentListItem) {
    touchStartRef.current = null;
    const dx = swipeState?.id === apptId ? swipeState.dx : 0;
    const triggeredLeft = dx <= SWIPE_TRIGGER_PX;
    const triggeredRight = dx >= SWIPE_TRIGGER_PX_RIGHT;
    setSwipeState(null);
    if (triggeredLeft) {
      suppressClickRef.current = apptId;
      setRescheduleAppt(appt);
    } else if (triggeredRight) {
      suppressClickRef.current = apptId;
      navigate(`/wizyty/${appt.id}`);
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
            <Button variant="secondary" onClick={goToNextVisit} isLoading={findingNextVisit} loadingText="Szukam...">
              Przejdź do najbliższej umówionej wizyty
            </Button>
          </div>
        ) : (
          // `transition: 'none'` while actively dragging (below) — the card's
          // own CSS class carries a 0.2s snap-back transition, which would
          // otherwise smooth (lag behind) every touchmove update too, instead
          // of tracking the finger 1:1. Dropping the inline style entirely on
          // release (swipeState → null) lets that CSS transition take back
          // over for the snap.
          appointments.map((appt) => {
            const swipeDx = swipeState?.id === appt.id ? swipeState.dx : 0;
            return (
            <div
              key={appt.id}
              className="mob-appt-card-wrap"
              ref={(el) => {
                if (el) cardRefs.current.set(appt.id, el);
                else cardRefs.current.delete(appt.id);
              }}
            >
              {isReschedulable(appt.status) && swipeDx < 0 && (
                <div
                  className={['mob-appt-swipe-reveal', 'mob-appt-swipe-reveal--left', swipeDx <= SWIPE_TRIGGER_PX ? 'mob-appt-swipe-reveal--armed' : ''].filter(Boolean).join(' ')}
                  aria-hidden="true"
                >
                  {/* The whole icon+label unit translates by the SAME dx as
                      the card, so it stays pinned to the card's trailing
                      edge as it slides ("stuck" to the card) — icon sits at
                      the unit's near edge (glued to the card from the first
                      px), label trails behind it, wrapped to 2 lines so it
                      needs less exposed width to read clearly. No opacity
                      fade (removed) — a fast real-world flick covers the
                      whole drag range in under 150ms, so any drag-progress
                      -based fade was already over before it was perceptible. */}
                  <div className="mob-appt-swipe-content mob-appt-swipe-content--left" style={{ transform: `translateX(${swipeDx}px)` }}>
                    <Icon name="calendar_month" />
                    <span className="mob-appt-swipe-label">Zmień termin</span>
                  </div>
                </div>
              )}
              {swipeDx > 0 && (
                <div
                  className={['mob-appt-swipe-reveal', 'mob-appt-swipe-reveal--right', swipeDx >= SWIPE_TRIGGER_PX_RIGHT ? 'mob-appt-swipe-reveal--armed' : ''].filter(Boolean).join(' ')}
                  aria-hidden="true"
                >
                  <div className="mob-appt-swipe-content mob-appt-swipe-content--right" style={{ transform: `translateX(${swipeDx}px)` }}>
                    <span className="mob-appt-swipe-label">Zobacz więcej</span>
                    <Icon name="chevron_right" />
                  </div>
                </div>
              )}
              <div
                className={[
                  'mob-appt-card',
                  appt.status === 'cancelled' || appt.status === 'no_show' || appt.status === 'rescheduled' ? 'mob-appt-card--muted' : '',
                  swipeState?.id === appt.id && swipeState.dx <= SWIPE_TRIGGER_PX ? 'mob-appt-card--swipe-armed' : '',
                  swipeState?.id === appt.id && swipeState.dx >= SWIPE_TRIGGER_PX_RIGHT ? 'mob-appt-card--swipe-armed-right' : '',
                  appt.id === highlightId ? 'mob-appt-card--highlight' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                style={swipeState?.id === appt.id ? { transform: `translateX(${swipeState.dx}px)`, transition: 'none' } : undefined}
                onClick={(e) => handleCardClick(appt, e)}
                onTouchStart={(e) => handleCardTouchStart(appt.id, e)}
                onTouchMove={(e) => handleCardTouchMove(appt.id, appt.status, e)}
                onTouchEnd={() => handleCardTouchEnd(appt.id, appt)}
              >
              <div className="mob-appt-top">
                {/* Date dropped (redesign) — start time + duration only, one
                    line, time bold/duration regular. */}
                <span className="mob-appt-datetime">
                  <span className="mob-appt-time">{appt.start_time.slice(0, 5)}</span>{' '}
                  <span className="mob-appt-duration">({formatDuration(appt.start_time, appt.end_time)})</span>
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

              {/* Client name (no caption) + phone as an icon-only tel: link
                  (redesign — digits/label dropped, same click behavior). */}
              <div className="mob-appt-row mob-appt-client-row">
                <span className="mob-appt-client-name">{appt.client_name || '—'}</span>
                {appt.client_phone && (
                  <a
                    className="mob-appt-phone-btn"
                    href={telHref(appt.client_phone)}
                    title={formatPhone(appt.client_phone)}
                    aria-label={`Zadzwoń: ${formatPhone(appt.client_phone)}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Icon name="call" />
                  </a>
                )}
              </div>

              {/* Employee row dropped entirely (redesign). Service — bare
                  name, no "Usługa:" caption. */}
              <span className="mob-appt-service">{appt.service_name || '—'}</span>

              {/* Minimal "this is tappable" hint (TASK3). */}
              <Icon name="chevron_right" className="mob-appt-tap-hint" />
              </div>
            </div>
            );
          })
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

        {/* Bottom-most row: "+" fixed-width on the left, employee selector
            expanding to fill the remaining width in the center, month toggle
            fixed-width on the right — `.mob-cal-nav-btn`'s 1px border / 2px
            radius / token colors throughout. No filter modal any more — the
            employee selector IS the filter now, there's nothing else to
            configure from mobile (search was dropped along with the modal;
            admin-view/own-data auto-engage for superusers, see the effect
            above). The popup sheet below is `position: fixed` to the real
            viewport bottom (see Appointments.css) rather than anchored to
            this row, so where it sits in the JSX tree doesn't matter. */}
        <div className="mob-fixed-nav-actions-wrap">
          {employeePopupMounted && (
            <div className="mob-emp-popup-overlay" onClick={closeEmployeePopup}>
              {/* `employeePopupOpen` toggles one frame after mount (rAF in
                  openEmployeePopup) so this starts from the closed transform
                  and actually animates in, instead of snapping straight to
                  open. */}
              <div className={`mob-emp-popup-sheet${employeePopupOpen ? ' mob-emp-popup-sheet--open' : ''}`} onClick={(e) => e.stopPropagation()}>
                {employees.map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    className={`mob-emp-popup-item${e.id === employeeId ? ' active' : ''}`}
                    onClick={() => {
                      onSelectEmployee(e.id);
                      closeEmployeePopup();
                    }}
                  >
                    {e.full_name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="mob-fixed-nav-actions">
            {canWrite && (
              <Link to="/wizyty/nowa" className="mob-cal-nav-btn primary" aria-label="Nowa wizyta" title="Nowa wizyta">
                <Icon name="add" />
              </Link>
            )}
            <button type="button" className="mob-cal-nav-btn mob-employee-select-btn" onClick={openEmployeePopup} aria-haspopup="true" aria-expanded={employeePopupOpen} aria-label="Wybierz pracownika" title="Wybierz pracownika">
              <Icon name="person" />
              <span className="mob-employee-select-label">{selectedEmployeeName}</span>
            </button>
            <button type="button" className="mob-cal-nav-btn mob-month-toggle-btn" onClick={() => setMonthExpanded((v) => !v)} aria-pressed={monthExpanded} aria-label={monthExpanded ? 'Ukryj pełny miesiąc' : 'Pokaż pełny miesiąc'} title={monthExpanded ? 'Ukryj pełny miesiąc' : 'Pokaż pełny miesiąc'}>
              <Icon name="calendar_today" />
            </button>
          </div>
        </div>
      </div>

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
