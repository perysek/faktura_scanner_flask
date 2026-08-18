import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './Appointments.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { empColor } from '../../lib/appointments/employeeColor';
import { ViewSwitcher } from './ViewSwitcher';
import { EmployeeFilter } from './EmployeeFilter';
import { STATUS_LABELS } from '../../types/appointment';
import type { AppointmentListItem, CalendarAbsence, EmployeeOption } from '../../types/appointment';

const LANE_START_MIN = 7 * 60;
const LANE_END_MIN = 22 * 60;
const LANE_HEIGHT = 900;
const HOURS = Array.from({ length: 16 }, (_, i) => 7 + i);
const DAY_NAMES = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd'];

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
    <div className="refined-page fade-in" style={{ display: 'flex', flexDirection: 'column' }}>
      <header className="page-header">
        <div>
          <h1 className="page-title">Wizyty</h1>
          <p className="page-subtitle">Tydzień {formatDateShort(iso(weekStart))} – {formatDateShort(iso(addDays(weekStart, 6)))}</p>
        </div>
        <div>
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
        <div className="table-container" style={{ flex: 1, overflow: 'auto' }}>
          <div style={{ display: 'flex' }}>
            <div style={{ width: '3rem', flexShrink: 0, position: 'relative', height: LANE_HEIGHT + 24 }}>
              {HOURS.map((h) => (
                <div key={h} className="cal-time-label" style={{ position: 'absolute', top: ((h * 60 - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * LANE_HEIGHT }}>
                  {h}:00
                </div>
              ))}
            </div>
            {days.map((day, i) => {
              const dateStr = iso(day);
              const dayAppts = appointments.filter((a) => a.appointment_date === dateStr);
              const dayAbsences = absences.filter((a) => dateStr >= a.date_from && dateStr <= a.date_to);
              return (
                <div key={dateStr} style={{ flex: 1, minWidth: 120, borderLeft: '1px solid var(--color-border-subtle)' }}>
                  <div style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid var(--color-border-subtle)', fontSize: '0.75rem', fontWeight: 600 }}>
                    {DAY_NAMES[i]} {day.getDate()}
                  </div>
                  <div className="cal-day-col" style={{ height: LANE_HEIGHT, position: 'relative' }}>
                    {HOURS.map((h) => (
                      <div key={h} className="cal-hour-line" style={{ top: ((h * 60 - LANE_START_MIN) / (LANE_END_MIN - LANE_START_MIN)) * LANE_HEIGHT }} />
                    ))}
                    {dayAbsences.map((ab, idx) => {
                      const pos = position(ab.time_from ?? '07:00', ab.time_to ?? '22:00');
                      return (
                        <div key={idx} className={`wk-absence${ab.status === 'pending' ? ' wk-absence--pending' : ''}`} style={{ top: pos.top, height: pos.height }}>
                          {ab.category_name}
                        </div>
                      );
                    })}
                    {dayAppts.map((a) => {
                      const pos = position(a.start_time, a.end_time);
                      return (
                        <div key={a.id} className={`wk-block ${a.status}`} style={{ top: pos.top, height: pos.height, borderLeftColor: empColor(employeeId) }} onClick={() => navigate(`/wizyty/${a.id}`)} title={`${STATUS_LABELS[a.status]} — ${a.client_name ?? ''}`}>
                          <div className="wk-block-client">{(a.client_name ?? 'Bez klienta').split(' ')[0]}</div>
                          <div className="wk-block-time">{a.start_time.slice(0, 5)}</div>
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
