import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './Appointments.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { ViewSwitcher } from './ViewSwitcher';
import { PastVisitsScanner } from './PastVisitsScanner';
import { EmployeeFilter } from './EmployeeFilter';
import { STATUS_LABELS } from '../../types/appointment';
import type { AppointmentListItem, EmployeeOption } from '../../types/appointment';

const MONTH_NAMES = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
const WEEKDAYS = ['Pon', 'Wt', 'Śr', 'Czw', 'Pt', 'Sob', 'Nd'];

function iso(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}
function todayIso(): string {
  const n = new Date();
  return iso(n.getFullYear(), n.getMonth(), n.getDate());
}

/**
 * Kalendarz — widok miesiąca. Ported z templates/appointments/calendar_month.html.
 * Jeden pracownik naraz, siatka 7×N z podglądem 2-3 wizyt na dzień (+N więcej).
 * BEZ bocznego paska (spec: tylko dzień + lista).
 */
export function CalendarMonthPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialDate = searchParams.get('date');
  const initial = initialDate ? new Date(initialDate) : new Date();
  const [year, setYear] = useState(initial.getFullYear());
  const [month, setMonth] = useState(initial.getMonth());
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState<number | null>(searchParams.get('employee_id') ? Number(searchParams.get('employee_id')) : null);
  const [appointments, setAppointments] = useState<AppointmentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const today = todayIso();

  useEffect(() => {
    appointmentsApi.employees().then((list) => {
      setEmployees(list);
      setEmployeeId((cur) => cur ?? list[0]?.id ?? null);
    });
  }, []);

  useEffect(() => {
    if (!employeeId) return;
    setLoading(true);
    const start = iso(year, month, 1);
    const end = iso(year, month, new Date(year, month + 1, 0).getDate());
    appointmentsApi
      .list({ start_date: start, end_date: end, employee_id: employeeId })
      .then((res) => setAppointments(res.appointments))
      .finally(() => setLoading(false));
  }, [employeeId, year, month]);

  const byDate = useMemo(() => {
    const m = new Map<string, AppointmentListItem[]>();
    for (const a of appointments) {
      if (!m.has(a.appointment_date)) m.set(a.appointment_date, []);
      m.get(a.appointment_date)!.push(a);
    }
    return m;
  }, [appointments]);

  const totalDays = new Date(year, month + 1, 0).getDate();
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7;
  const cells: Array<{ dateStr: string; day: number; outside: boolean }> = [];
  // Leading/trailing filler uses `new Date(year, month ± n, day)` rather than
  // manual month/year arithmetic — JS normalizes an out-of-range month
  // (-1, 12, …) into the correct adjacent year on its own, which a bare
  // `month - 1` string-formatted directly does NOT (breaks every December→
  // January and January→December boundary).
  for (let i = firstWeekday; i > 0; i--) {
    const d = new Date(year, month, 1 - i);
    cells.push({ dateStr: iso(d.getFullYear(), d.getMonth(), d.getDate()), day: d.getDate(), outside: true });
  }
  for (let d = 1; d <= totalDays; d++) cells.push({ dateStr: iso(year, month, d), day: d, outside: false });
  const trailingCount = cells.length % 7 === 0 ? 0 : 7 - (cells.length % 7);
  for (let i = 1; i <= trailingCount; i++) {
    const d = new Date(year, month + 1, i);
    cells.push({ dateStr: iso(d.getFullYear(), d.getMonth(), d.getDate()), day: d.getDate(), outside: true });
  }

  function goMonth(offset: number) {
    const d = new Date(year, month + offset, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth());
  }
  function goToday() {
    const n = new Date();
    setYear(n.getFullYear());
    setMonth(n.getMonth());
  }

  return (
    <div className="refined-page page-fills-viewport fade-in" style={{ display: 'flex', flexDirection: 'column' }}>
      <header className="page-header">
        <div>
          <h1 className="page-title">Wizyty</h1>
          <p className="page-subtitle" style={{ textTransform: 'capitalize' }}>
            {MONTH_NAMES[month]} {year}
          </p>
        </div>
        <div>
          <PastVisitsScanner />
          <ViewSwitcher active="month" date={iso(year, month, 1)} employeeId={employeeId} />
        </div>
      </header>

      <div className="date-nav">
        <button type="button" className="nav-btn" onClick={() => goMonth(-1)}>
          ← Poprzedni
        </button>
        <button type="button" className="nav-btn" onClick={goToday}>
          Dziś
        </button>
        <button type="button" className="nav-btn" onClick={() => goMonth(1)}>
          Następny →
        </button>
        <div className="empf-divider" />
        <span className="empf-label">Pracownik:</span>
        <EmployeeFilter employees={employees} selectedId={employeeId} onSelect={setEmployeeId} />
      </div>

      {loading ? (
        <p className="empty-text">Ładowanie...</p>
      ) : (
        <>
          <div className="month-card-weekdays" style={{ marginBottom: '0.25rem' }}>
            {WEEKDAYS.map((w) => (
              <span key={w} style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--color-ink-subtle)', fontWeight: 500 }}>
                {w}
              </span>
            ))}
          </div>
          <div className="month-grid">
            {cells.map((cell) => {
              const dayAppts = (byDate.get(cell.dateStr) ?? []).filter((a) => a.status !== 'cancelled');
              const visible = dayAppts.slice(0, 3);
              const more = dayAppts.length - visible.length;
              return (
                <div key={cell.dateStr} className={`month-cell${cell.outside ? ' outside' : ''}${cell.dateStr === today ? ' today' : ''}`} onClick={() => navigate(`/wizyty/kalendarz?date=${cell.dateStr}`)}>
                  <span className="month-cell-num">{cell.day}</span>
                  {visible.map((a) => {
                    const stylistFirst = a.employee_name?.split(' ')[0] ?? '—';
                    return (
                      <span
                        key={a.id}
                        className={`month-cell-appt ${a.status}`}
                        title={`${STATUS_LABELS[a.status]} — ${a.start_time.slice(0, 5)} — ${a.client_name ?? 'Bez klienta'} (${stylistFirst})`}
                      >
                        {a.client_name ?? 'Bez klienta'} ({stylistFirst})
                      </span>
                    );
                  })}
                  {more > 0 && <span className="month-cell-more">+{more} więcej</span>}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
