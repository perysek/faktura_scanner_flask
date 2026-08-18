import { useEffect, useState } from 'react';
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
 * The 3 months shown are the REAL current month +0/+1/+2 — fixed at mount,
 * never re-derived from `selectedDate` or re-fetched on host navigation (spec:
 * "This 3-month window is fixed and never follows navigation in the main
 * view"). `today` is likewise computed once, not on every render, so the
 * "today" highlight can't silently drift if the tab is left open across
 * midnight — matches the spec's intent (a fixed reference point) more than it
 * matters in practice.
 */
export function CalendarMonthSidebar({ selectedDate, onDayClick }: CalendarMonthSidebarProps) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1';
    } catch {
      return false;
    }
  });
  const [months] = useState(() => {
    const base = new Date();
    base.setHours(0, 0, 0, 0);
    return [addMonths(base, 0), addMonths(base, 1), addMonths(base, 2)];
  });
  const [today] = useState(() => iso(new Date()));
  const [daysWithAppointments, setDaysWithAppointments] = useState<Set<string> | null>(null);

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
      })
      .catch(() => setDaysWithAppointments(new Set()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  return (
    <div className={`cal-sidebar-col${collapsed ? ' collapsed' : ''}`}>
      <button type="button" className="cal-sidebar-toggle" onClick={toggleCollapsed} aria-label={collapsed ? 'Rozwiń pasek boczny' : 'Zwiń pasek boczny'} title={collapsed ? 'Rozwiń' : 'Zwiń'}>
        <Icon name="chevron_left" />
      </button>
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
