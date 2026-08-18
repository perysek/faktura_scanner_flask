import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './Appointments.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { empColor } from '../../lib/appointments/employeeColor';
import { ViewSwitcher } from './ViewSwitcher';
import { CalendarMonthSidebar } from './CalendarMonthSidebar';
import { STATUS_LABELS } from '../../types/appointment';
import type { MultiEmployeeScheduleResponse } from '../../types/appointment';

const LANE_START_MIN = 7 * 60;
const LANE_END_MIN = 22 * 60;
const LANE_HEIGHT = 900;

function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}
function position(start: string, end: string) {
  const s = Math.max(LANE_START_MIN, toMinutes(start));
  const e = Math.min(LANE_END_MIN, toMinutes(end));
  const top = ((s - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * LANE_HEIGHT;
  const height = Math.max(16, ((e - s) / (LANE_END_MIN - LANE_START_MIN)) * LANE_HEIGHT);
  return { top, height };
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
    <div className="refined-page cal-grid-page fade-in">
      <div className="cal-main">
        <header className="page-header">
          <div>
            <h1 className="page-title">Wizyty</h1>
            <p className="page-subtitle">{formatLong(date)}</p>
          </div>
          <div>
            <ViewSwitcher active="day" date={date} />
          </div>
        </header>

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
          <div className="table-container" style={{ flex: 1, overflow: 'auto' }}>
            <div style={{ display: 'flex' }}>
              <div style={{ width: '3rem', flexShrink: 0, position: 'relative', height: LANE_HEIGHT + 24 }}>
                {HOURS.map((h) => (
                  <div key={h} className="cal-time-label" style={{ position: 'absolute', top: ((h * 60 - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * LANE_HEIGHT }}>
                    {h}:00
                  </div>
                ))}
              </div>
              {data.employees.map((emp) => {
                const appts = data.schedules[emp.id] ?? [];
                const absences = data.absences[emp.id] ?? [];
                return (
                  <div key={emp.id} style={{ flex: 1, minWidth: 160, borderLeft: '1px solid var(--color-border-subtle)' }}>
                    <div style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)', fontSize: '0.75rem', fontWeight: 600, color: empColor(emp.id) }}>{emp.full_name}</div>
                    <div className="cal-day-col" style={{ height: LANE_HEIGHT, position: 'relative' }}>
                      {HOURS.map((h) => (
                        <div key={h} className="cal-hour-line" style={{ top: ((h * 60 - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * LANE_HEIGHT }} />
                      ))}
                      {absences.map((ab) => {
                        const pos = position(ab.time_from ?? '07:00', ab.time_to ?? '22:00');
                        return (
                          <div key={ab.id} className={`day-absence${ab.status === 'pending' ? ' day-absence--pending' : ''}`} style={{ top: pos.top, height: pos.height }}>
                            {ab.category_name}
                          </div>
                        );
                      })}
                      {appts.map((a) => {
                        const pos = position(a.start_time, a.end_time);
                        return (
                          <div key={a.id} className={`day-block ${a.status}`} style={{ top: pos.top, height: pos.height, borderLeftColor: empColor(emp.id) }} onClick={() => navigate(`/wizyty/${a.id}`)} title={`${STATUS_LABELS[a.status]} — ${a.client_name ?? ''}`}>
                            <div className="day-block-client">{(a.client_name ?? 'Bez klienta').split(' ')[0]}</div>
                            <div className="day-block-time">{a.start_time.slice(0, 5)}</div>
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
  );
}
