import { useEffect, useMemo, useRef, useState } from 'react';
import { appointmentsApi } from '../../lib/api/appointments';
import { Icon } from '../../lib/icons/Icon';

const COLLAPSE_KEY = 'wizyty.sidebar.collapsed';
const WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];
const MONTH_NAMES = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export interface CalendarMonthSidebarProps {
  /** The date the host view currently considers "active" — gets the ring
   * highlight (calendar-sidebar-redesign-prompt.md's "selected" state,
   * separate from and combinable with "today"). */
  selectedDate: string;
  onDayClick: (date: string) => void;
}

/**
 * Collapsible month-cards sidebar — calendar-sidebar-redesign-prompt.md, built
 * alongside the day-view and list-view pages that host it (user instruction,
 * not an independent later pass). Purely presentational: it reports which day
 * was clicked via `onDayClick`; the host page decides what that means (simple
 * retarget on the day-view, progressive day-chain loading on the list-view —
 * spec §"Day-view click behavior" vs §"List-view click behavior").
 *
 * **Update (fix #2, react-ui-corrections_19080026.txt):** the 3-month window
 * is no longer permanently fixed at mount — prev/next buttons (visible only
 * when expanded, inside the collapse/expand topbar) shift it by a full
 * 3-month step. `anchorMonth` (the first of the 3 shown) starts at the real
 * current month on mount, same starting point as before; it just isn't
 * frozen there anymore. Every shift re-fetches `daysWithAppointments` for the
 * NEW window and — once that resolves — auto-selects (via the same
 * `onDayClick` callback a real click uses) the first day-with-visits in the
 * new MIDDLE month, falling back to that month's 1st if it has none. `today`
 * is still computed once (unaffected by navigation — it's "which cell IS
 * today", not "which months are shown").
 */
export function CalendarMonthSidebar({ selectedDate, onDayClick }: CalendarMonthSidebarProps) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1';
    } catch {
      return false;
    }
  });
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const base = new Date();
    base.setHours(0, 0, 0, 0);
    base.setDate(1);
    return base;
  });
  const months = useMemo(() => [addMonths(anchorMonth, 0), addMonths(anchorMonth, 1), addMonths(anchorMonth, 2)], [anchorMonth]);
  const [today] = useState(() => iso(new Date()));
  const [daysWithAppointments, setDaysWithAppointments] = useState<Set<string> | null>(null);
  // Distinguishes "fetch triggered by mount/initial render" (don't touch the
  // host's selection) from "fetch triggered by a prev/next click" (DO
  // auto-select once the new window's data is in) — both paths share the
  // same effect/fetch below, only the post-fetch behaviour differs.
  const navigatedRef = useRef(false);

  useEffect(() => {
    const start = iso(months[0]);
    const lastMonth = months[2];
    const end = iso(new Date(lastMonth.getFullYear(), lastMonth.getMonth() + 1, 0));
    appointmentsApi
      .list({ start_date: start, end_date: end })
      .then((res) => {
        const set = new Set<string>();
        for (const a of res.appointments) {
          if (a.status === 'cancelled' || a.status === 'no_show') continue;
          set.add(a.appointment_date);
        }
        setDaysWithAppointments(set);
        if (navigatedRef.current) {
          navigatedRef.current = false;
          const middle = months[1];
          const middleKey = `${middle.getFullYear()}-${String(middle.getMonth() + 1).padStart(2, '0')}-`;
          const firstInMiddle = [...set].filter((d) => d.startsWith(middleKey)).sort()[0];
          onDayClick(firstInMiddle ?? iso(middle));
        }
      })
      .catch(() => {
        setDaysWithAppointments(new Set());
        navigatedRef.current = false;
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchorMonth]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        if (next) localStorage.setItem(COLLAPSE_KEY, '1');
        else localStorage.removeItem(COLLAPSE_KEY);
      } catch {
        /* private browsing / storage disabled — just won't persist */
      }
      return next;
    });
  }

  function shiftMonths(n: number) {
    navigatedRef.current = true;
    setAnchorMonth((cur) => addMonths(cur, n));
  }

  return (
    <div className={`cal-sidebar-col${collapsed ? ' collapsed' : ''}`}>
      <div className="cal-sidebar-topbar">
        {!collapsed && (
          <button type="button" className="cal-sidebar-nav-btn" onClick={() => shiftMonths(-3)} aria-label="Poprzednie 3 miesiące" title="Poprzednie 3 miesiące">
            <Icon name="expand_more" className="icon-flip" />
          </button>
        )}
        <button type="button" className="cal-sidebar-toggle" onClick={toggleCollapsed} aria-label={collapsed ? 'Rozwiń pasek boczny' : 'Zwiń pasek boczny'} title={collapsed ? 'Rozwiń' : 'Zwiń'}>
          <Icon name="chevron_left" />
        </button>
        {!collapsed && (
          <button type="button" className="cal-sidebar-nav-btn" onClick={() => shiftMonths(3)} aria-label="Następne 3 miesiące" title="Następne 3 miesiące">
            <Icon name="expand_more" />
          </button>
        )}
      </div>
      {!collapsed && (
        <div className="cal-sidebar-body">
          {months.map((m) => (
            <MonthCard key={`${m.getFullYear()}-${m.getMonth()}`} month={m} today={today} selectedDate={selectedDate} daysWithAppointments={daysWithAppointments} onDayClick={onDayClick} />
          ))}
        </div>
      )}
    </div>
  );
}

function MonthCard({
  month,
  today,
  selectedDate,
  daysWithAppointments,
  onDayClick,
}: {
  month: Date;
  today: string;
  selectedDate: string;
  daysWithAppointments: Set<string> | null;
  onDayClick: (date: string) => void;
}) {
  const year = month.getFullYear();
  const monthIdx = month.getMonth();
  const total = daysInMonth(year, monthIdx);
  // No leading/trailing filler (spec) — but the weekday row still needs the
  // 1st's weekday to line the grid up under the right column.
  const firstWeekday = (new Date(year, monthIdx, 1).getDay() + 6) % 7; // 0=Mon

  const cells: Array<{ day: number; dateStr: string } | null> = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (let d = 1; d <= total; d++) {
    cells.push({ day: d, dateStr: `${year}-${String(monthIdx + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}` });
  }

  return (
    <div className="month-card">
      <div className="month-card-header">
        {MONTH_NAMES[monthIdx]} {year}
      </div>
      <div className="month-card-weekdays">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="month-card-days">
        {cells.map((cell, i) =>
          cell === null ? (
            <span key={`e${i}`} className="month-card-day empty" />
          ) : (
            <button
              key={cell.dateStr}
              type="button"
              className={[
                'month-card-day',
                daysWithAppointments?.has(cell.dateStr) ? 'has-appointments' : '',
                cell.dateStr === today ? 'today' : '',
                cell.dateStr === selectedDate ? 'selected' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => onDayClick(cell.dateStr)}
              title={cell.dateStr}
            >
              {cell.day}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
