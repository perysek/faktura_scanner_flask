import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './Appointments.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { empColor } from '../../lib/appointments/employeeColor';
import { useElementHeight } from '../../lib/useElementHeight';
import { ViewSwitcher } from './ViewSwitcher';
import { CalendarMonthSidebar } from './CalendarMonthSidebar';
import { STATUS_LABELS } from '../../types/appointment';
import type { MultiEmployeeScheduleResponse } from '../../types/appointment';

const LANE_START_MIN = 7 * 60;
const LANE_END_MIN = 22 * 60;
// Fallback/mobile lane height — see CalendarWeekPage.tsx's identical constant
// for the full rationale (fix #6, implementation-log.md 2026-08-19).
const LANE_HEIGHT_FALLBACK = 900;

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
function todayIso(): string {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
}
function addDaysIso(dateStr: string, n: number): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(y, m - 1, d + n);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
function formatLong(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' });
}

const HOURS = Array.from({ length: 16 }, (_, i) => 7 + i); // 7..22

/**
 * Kalendarz — widok dnia. Ported z templates/appointments/calendar.html.
 * BEZ drag&drop (odkrycie audytu — patrz module-inventory.md) — bloki są
 * tylko klikalne (nawigacja do /wizyty/:id). Wielu pracowników jednocześnie,
 * stronicowane (`multi-employee-schedule`, 8 na stronę). Boczny pasek
 * month-cards wpięty tu na życzenie użytkownika (calendar-sidebar-redesign-
 * prompt.md — dzień-widok = proste "retarguj siatkę na kliknięty dzień").
 */
export function CalendarDayPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [date, setDate] = useState(searchParams.get('date') ?? todayIso());
  const [page, setPage] = useState(0);
  const [data, setData] = useState<MultiEmployeeScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [laneRef, laneHeight] = useElementHeight<HTMLDivElement>(LANE_HEIGHT_FALLBACK);

  useEffect(() => {
    setLoading(true);
    appointmentsApi
      .multiEmployeeSchedule(date, page * 8, 8)
      .then(setData)
      .finally(() => setLoading(false));
  }, [date, page]);

  function goDay(offset: number) {
    setDate((d) => addDaysIso(d, offset));
    setPage(0);
  }
  function goToday() {
    setDate(todayIso());
    setPage(0);
  }
  function handleSidebarDayClick(dateStr: string) {
    setDate(dateStr);
    setPage(0);
  }

  return (
    <div className="refined-page page-fills-viewport fade-in">
      {/* Page header at the true page root, spanning main content + sidebar
          — see WizytyListPage.tsx's identical relocation for the full
          rationale (user clarification 2026-08-19: header buttons row must
          reach the actual viewport-aligned right edge, not just
          `.cal-main`'s narrower one). */}
      <header className="page-header">
        <div>
          <h1 className="page-title">Wizyty</h1>
          <p className="page-subtitle">{formatLong(date)}</p>
        </div>
        <div>
          <ViewSwitcher active="day" date={date} />
        </div>
      </header>

      <div className="cal-grid-page">
      <div className="cal-main">
        <div className="date-nav">
          <button type="button" className="nav-btn" onClick={() => goDay(-1)}>
            ← Poprzedni
          </button>
          <input
            type="date"
            className="date-nav-date"
            value={date}
            onChange={(e) => {
              if (!e.target.value) return;
              setDate(e.target.value);
              setPage(0);
            }}
          />
          <button type="button" className="nav-btn" onClick={goToday}>
            Dziś
          </button>
          <button type="button" className="nav-btn" onClick={() => goDay(1)}>
            Następny →
          </button>
          {data && data.total_pages > 1 && (
            <div className="emp-page-nav">
              <button type="button" disabled={!data.has_prev} onClick={() => setPage((p) => p - 1)}>
                ←
              </button>
              <span className="date-nav-range">
                Strona {data.page + 1}/{data.total_pages} ({data.total_employees} prac.)
              </span>
              <button type="button" disabled={!data.has_next} onClick={() => setPage((p) => p + 1)}>
                →
              </button>
            </div>
          )}
        </div>

        {loading || !data ? (
          <p className="empty-text">Ładowanie...</p>
        ) : data.employees.length === 0 ? (
          <div className="empty-state">
            <p className="empty-text">Brak wizyt zaplanowanych na ten dzień.</p>
          </div>
        ) : (
          <div className="table-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {/* Employee-name header row, own row so it never shrinks — split
                out from the lane row below for the same reason as
                CalendarWeekPage.tsx's day-name header (fix #5): lets the
                time-label column sit in the SAME row as the lanes, aligned
                exactly to their hour-lines, no fudge-offset guessing.
                `cal-grid-header-cell` (fix #3d) gives it a background
                distinct from the grid below. */}
            <div className="cal-grid-header-cell" style={{ display: 'flex', flexShrink: 0 }}>
              <div style={{ width: '3rem', flexShrink: 0 }} />
              {data.employees.map((emp) => (
                <div key={emp.id} style={{ flex: 1, minWidth: 160, padding: '0.5rem', textAlign: 'center', borderLeft: '1px solid var(--color-border-subtle)', borderBottom: '1px solid var(--color-border-subtle)', fontSize: '0.75rem', fontWeight: 600, color: empColor(emp.id) }}>
                  {emp.full_name}
                </div>
              ))}
            </div>
            {/* Lane row — `flex: 1; minHeight: 0` claims all remaining height
                inside `.table-container` (bounded by `.page-fills-viewport`
                on desktop). `laneHeight` is this row's own measured pixel
                height (useElementHeight, ref below), so the 7am–10pm range
                always exactly fills whatever space is actually available. */}
            <div ref={laneRef} style={{ display: 'flex', flex: 1, minHeight: 0 }}>
              <div style={{ width: '3rem', flexShrink: 0, position: 'relative' }}>
                {HOURS.map((h) => (
                  <div key={h} className="cal-time-label" style={{ position: 'absolute', top: hourTop(h, laneHeight) }}>
                    {h}:00
                  </div>
                ))}
              </div>
              {data.employees.map((emp) => {
                const appts = data.schedules[emp.id] ?? [];
                const absences = data.absences[emp.id] ?? [];
                return (
                  <div key={emp.id} style={{ flex: 1, minWidth: 160, borderLeft: '1px solid var(--color-border-subtle)' }}>
                    <div className="cal-day-col" style={{ height: laneHeight, position: 'relative' }}>
                      {HOURS.map((h) => (
                        <div key={h} className="cal-hour-line" style={{ top: hourTop(h, laneHeight) }} />
                      ))}
                      {absences.map((ab) => {
                        const pos = position(ab.time_from ?? '07:00', ab.time_to ?? '22:00', laneHeight);
                        return (
                          <div key={ab.id} className={`day-absence${ab.status === 'pending' ? ' day-absence--pending' : ''}`} style={{ top: pos.top, height: pos.height }}>
                            {ab.category_name}
                          </div>
                        );
                      })}
                      {appts.map((a) => {
                        const pos = position(a.start_time, a.end_time, laneHeight);
                        const dur = durationMin(a.start_time, a.end_time);
                        const stylistFirst = emp.full_name.split(' ')[0];
                        return (
                          <div
                            key={a.id}
                            className={`day-block ${a.status}`}
                            style={{ top: pos.top, height: pos.height }}
                            onClick={() => navigate(`/wizyty/${a.id}`)}
                            title={`${STATUS_LABELS[a.status]} — ${a.client_name ?? 'Bez klienta'}${a.service_name ? ` — ${a.service_name}` : ''} — ${stylistFirst} — ${a.start_time.slice(0, 5)} (${dur} min)`}
                          >
                            <div className="day-block-client">{a.client_name ?? 'Bez klienta'}</div>
                            {a.service_name && <div className="day-block-service">{a.service_name}</div>}
                            <div className="day-block-time">
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

      <CalendarMonthSidebar selectedDate={date} onDayClick={handleSidebarDayClick} />
      </div>
    </div>
  );
}
