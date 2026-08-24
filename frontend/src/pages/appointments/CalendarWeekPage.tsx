import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './Appointments.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { useElementHeight } from '../../lib/useElementHeight';
import { ViewSwitcher } from './ViewSwitcher';
import { PastVisitsScanner } from './PastVisitsScanner';
import { EmployeeFilter } from './EmployeeFilter';
import { STATUS_LABELS } from '../../types/appointment';
import type { AppointmentListItem, CalendarAbsence, EmployeeOption } from '../../types/appointment';

const LANE_START_MIN = 7 * 60;
const LANE_END_MIN = 22 * 60;
// Fallback/mobile lane height in px — was a hardcoded constant the whole
// grid rendered at regardless of viewport (fix #5, implementation-log.md
// 2026-08-19: "kalendarz tydzień — dopasowanie wysokości siatki do
// viewportu"). Now only the seed value for `useElementHeight`; on desktop
// the real available height (measured off the lane row, `page-fills-
// viewport`-bounded) replaces it, so the grid always fits with zero page
// scroll instead of overflowing a fixed 900px.
const LANE_HEIGHT_FALLBACK = 900;
const HOURS = Array.from({ length: 16 }, (_, i) => 7 + i);
const DAY_NAMES = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd'];

function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}
function hourTop(h: number, laneHeight: number): number {
  return ((h * 60 - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * laneHeight;
}
function position(start: string, end: string, laneHeight: number) {
  const s = Math.max(LANE_START_MIN, toMinutes(start));
  const e = Math.min(LANE_END_MIN, toMinutes(end));
  const top = ((s - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * laneHeight;
  const height = Math.max(16, ((e - s) / (LANE_END_MIN - LANE_START_MIN)) * laneHeight);
  return { top, height };
}
function durationMin(start: string, end: string): number {
  return toMinutes(end) - toMinutes(start);
}
function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  date.setDate(date.getDate() + ((day === 0 ? -6 : 1) - day));
  date.setHours(0, 0, 0, 0);
  return date;
}
function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}
function formatDateShort(dateStr: string): string {
  const [, m, d] = dateStr.split('-');
  return `${d}.${m}`;
}

/**
 * Kalendarz — widok tygodnia. Ported z templates/appointments/calendar_week.html.
 * Jeden pracownik naraz (jak oryginał — `selectEmployee`), 7 kolumn dni. BEZ
 * bocznego paska month-cards (spec obejmuje tylko dzień + listę).
 */
export function CalendarWeekPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialDate = searchParams.get('date');
  const [weekStart, setWeekStart] = useState(() => getMonday(initialDate ? new Date(initialDate) : new Date()));
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState<number | null>(searchParams.get('employee_id') ? Number(searchParams.get('employee_id')) : null);
  const [appointments, setAppointments] = useState<AppointmentListItem[]>([]);
  const [absences, setAbsences] = useState<CalendarAbsence[]>([]);
  const [loading, setLoading] = useState(true);
  const [laneRef, laneHeight] = useElementHeight<HTMLDivElement>(LANE_HEIGHT_FALLBACK);

  useEffect(() => {
    appointmentsApi.employees().then((list) => {
      setEmployees(list);
      setEmployeeId((cur) => cur ?? list[0]?.id ?? null);
    });
  }, []);

  useEffect(() => {
    if (!employeeId) return;
    setLoading(true);
    const start = iso(weekStart);
    const end = iso(addDays(weekStart, 6));
    Promise.all([appointmentsApi.list({ start_date: start, end_date: end, employee_id: employeeId }), appointmentsApi.absences(start, end)])
      .then(([apptRes, absRes]) => {
        setAppointments(apptRes.appointments);
        setAbsences(absRes.filter((a) => a.employee_id === employeeId));
      })
      .finally(() => setLoading(false));
  }, [employeeId, weekStart]);

  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  return (
    <div className="refined-page page-fills-viewport fade-in" style={{ display: 'flex', flexDirection: 'column' }}>
      <header className="page-header">
        <div>
          <h1 className="page-title">Wizyty</h1>
          <p className="page-subtitle">Tydzień {formatDateShort(iso(weekStart))} – {formatDateShort(iso(addDays(weekStart, 6)))}</p>
        </div>
        <div>
          <PastVisitsScanner />
          <ViewSwitcher active="week" date={iso(weekStart)} employeeId={employeeId} />
        </div>
      </header>

      <div className="date-nav">
        <button type="button" className="nav-btn" onClick={() => setWeekStart((w) => addDays(w, -7))}>
          ← Poprzedni
        </button>
        <input type="date" className="date-nav-date" value={iso(weekStart)} onChange={(e) => e.target.value && setWeekStart(getMonday(new Date(e.target.value)))} />
        <button type="button" className="nav-btn" onClick={() => setWeekStart(getMonday(new Date()))}>
          Dziś
        </button>
        <button type="button" className="nav-btn" onClick={() => setWeekStart((w) => addDays(w, 7))}>
          Następny →
        </button>
        <div className="empf-divider" />
        <span className="empf-label">Pracownik:</span>
        <EmployeeFilter employees={employees} selectedId={employeeId} onSelect={setEmployeeId} />
      </div>

      {loading ? (
        <p className="empty-text">Ładowanie...</p>
      ) : (
        <div className="table-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
          {/* Day-name header — own row, `flexShrink: 0` so it always keeps its
              natural size; the lane row below gets whatever's left. Splitting
              these into two stacked rows (was one row with each day-column
              carrying its own header above a fixed-height lane) means the
              time-label column can now sit in the SAME row as the lanes and
              line up with their hour-lines exactly, instead of the old `+ 24`
              fudge-offset guessing at the header row's height.
              `cal-grid-header-cell` (fix #3d) gives it a background distinct
              from the grid below — it inherited the same
              `--color-surface-elevated` as `.table-container` before. */}
          <div className="cal-grid-header-cell" style={{ display: 'flex', flexShrink: 0 }}>
            <div style={{ width: '3rem', flexShrink: 0 }} />
            {days.map((day, i) => (
              <div key={iso(day)} style={{ flex: 1, minWidth: 120, padding: '0.5rem', textAlign: 'center', borderLeft: '1px solid var(--color-border-subtle)', borderBottom: '1px solid var(--color-border-subtle)', fontSize: '0.75rem', fontWeight: 600 }}>
                {DAY_NAMES[i]} {day.getDate()}
              </div>
            ))}
          </div>
          {/* Lane row — `flex: 1; minHeight: 0` claims all remaining height
              inside `.table-container` (itself bounded by `.page-fills-
              viewport`, DESIGN.md §20.2, on desktop). `laneHeight` is this
              row's OWN measured pixel height (useElementHeight, ref below) —
              feeding back into every child's `top`/`height` math so the full
              7am–10pm range always exactly fills whatever space is actually
              available, instead of a fixed 900px taller than the viewport. */}
          <div ref={laneRef} style={{ display: 'flex', flex: 1, minHeight: 0 }}>
            <div style={{ width: '3rem', flexShrink: 0, position: 'relative' }}>
              {HOURS.map((h) => (
                <div key={h} className="cal-time-label" style={{ position: 'absolute', top: hourTop(h, laneHeight) }}>
                  {h}:00
                </div>
              ))}
            </div>
            {days.map((day) => {
              const dateStr = iso(day);
              const dayAppts = appointments.filter((a) => a.appointment_date === dateStr);
              const dayAbsences = absences.filter((a) => dateStr >= a.date_from && dateStr <= a.date_to);
              return (
                <div key={dateStr} style={{ flex: 1, minWidth: 120, borderLeft: '1px solid var(--color-border-subtle)' }}>
                  <div className="cal-day-col" style={{ height: laneHeight, position: 'relative' }}>
                    {HOURS.map((h) => (
                      <div key={h} className="cal-hour-line" style={{ top: hourTop(h, laneHeight) }} />
                    ))}
                    {dayAbsences.map((ab, idx) => {
                      const pos = position(ab.time_from ?? '07:00', ab.time_to ?? '22:00', laneHeight);
                      return (
                        <div key={idx} className={`wk-absence${ab.status === 'pending' ? ' wk-absence--pending' : ''}`} style={{ top: pos.top, height: pos.height }}>
                          {ab.category_name}
                        </div>
                      );
                    })}
                    {dayAppts.map((a) => {
                      const pos = position(a.start_time, a.end_time, laneHeight);
                      const dur = durationMin(a.start_time, a.end_time);
                      const stylistFirst = a.employee_name?.split(' ')[0] ?? '—';
                      return (
                        <div
                          key={a.id}
                          className={`wk-block ${a.status}`}
                          style={{ top: pos.top, height: pos.height }}
                          onClick={() => navigate(`/wizyty/${a.id}`)}
                          title={`${STATUS_LABELS[a.status]} — ${a.client_name ?? 'Bez klienta'}${a.service_name ? ` — ${a.service_name}` : ''} — ${stylistFirst} — ${a.start_time.slice(0, 5)} (${dur} min)`}
                        >
                          <div className="wk-block-client">{a.client_name ?? 'Bez klienta'}</div>
                          {a.service_name && <div className="wk-block-service">{a.service_name}</div>}
                          <div className="wk-block-time">
                            {stylistFirst} · {a.start_time.slice(0, 5)} · {dur} min
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
