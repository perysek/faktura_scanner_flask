import { useCallback, useEffect, useMemo, useState } from 'react';
import type { MouseEvent } from 'react';
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
import { StatusChangeModal } from './StatusChangeModal';
import { CalendarMonthSidebar } from './CalendarMonthSidebar';
import { STATUS_LABELS } from '../../types/appointment';
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

  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));
  const [mode, setMode] = useState<'week' | 'chain'>('week');
  const [chainDates, setChainDates] = useState<string[]>([]);
  const [monthCache, setMonthCache] = useState<{ key: string; byDate: Map<string, AppointmentListItem[]> } | null>(null);
  const [chainLoading, setChainLoading] = useState(false);

  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sort, setSort] = useState<{ column: SortColumn; dir: 'asc' | 'desc' }>({ column: 'appointment_date', dir: 'asc' });
  const [statusModalAppt, setStatusModalAppt] = useState<AppointmentListItem | null>(null);

  const [weekAppointments, setWeekAppointments] = useState<AppointmentListItem[]>([]);
  const [weekLoading, setWeekLoading] = useState(true);
  const [weekError, setWeekError] = useState<Error | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    appointmentsApi.employees().then(setEmployees).catch(() => {});
  }, []);

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

  function exitChainMode() {
    setMode('week');
    setChainDates([]);
  }

  async function ensureMonthLoaded(dateStr: string): Promise<Map<string, AppointmentListItem[]>> {
    const key = dateStr.slice(0, 7);
    if (monthCache && monthCache.key === key) return monthCache.byDate;
    const [y, m] = key.split('-').map(Number);
    const start = `${key}-01`;
    const end = iso(new Date(y, m, 0));
    const res = await appointmentsApi.list({ start_date: start, end_date: end });
    const byDate = new Map<string, AppointmentListItem[]>();
    for (const a of res.appointments) {
      if (!byDate.has(a.appointment_date)) byDate.set(a.appointment_date, []);
      byDate.get(a.appointment_date)!.push(a);
    }
    setMonthCache({ key, byDate });
    return byDate;
  }

  function hasReal(byDate: Map<string, AppointmentListItem[]>, dateStr: string): boolean {
    return (byDate.get(dateStr) ?? []).some((a) => a.status !== 'cancelled' && a.status !== 'no_show');
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
    if (mode === 'chain' && monthCache) {
      return chainDates.flatMap((d) => monthCache.byDate.get(d) ?? []).sort((a, b) => (a.appointment_date + a.start_time).localeCompare(b.appointment_date + b.start_time));
    }
    return weekAppointments;
  }, [mode, monthCache, chainDates, weekAppointments]);

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
    <div className="refined-page cal-grid-page fade-in">
      <div className="cal-main">
        <header className="page-header">
          <div>
            <h1 className="page-title">Wizyty</h1>
            <p className="page-subtitle">{mode === 'chain' ? 'Widok dnia z bocznego paska' : 'Tydzień wizyt'}</p>
          </div>
          <div>
            <ViewSwitcher active="list" date={iso(weekStart)} employeeId={employeeId} />
            {canWrite && (
              <ButtonLink variant="primary" icon="add" to="/wizyty/nowa">
                Nowa wizyta
              </ButtonLink>
            )}
          </div>
        </header>

        <div className="date-nav">
          <button type="button" className="nav-btn" onClick={() => goWeek(-1)}>
            ← Poprzedni
          </button>
          <input type="date" className="date-nav-date" aria-label="Wybierz tydzień" value={iso(weekStart)} onChange={(e) => onDateInputChange(e.target.value)} />
          <span className="date-nav-range">{rangeLabel}</span>
          <button type="button" className="nav-btn" onClick={goToday}>
            Dziś
          </button>
          <button type="button" className="nav-btn" onClick={() => goWeek(1)}>
            Następny →
          </button>
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

        <div className="table-container page-fills-viewport" style={{ flex: 1 }}>
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
                      <td className="cell-date" data-label="Data">
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
                        <span className={`status-badge clickable ${appt.status}`} onClick={(e) => { e.stopPropagation(); setStatusModalAppt(appt); }}>
                          {STATUS_LABELS[appt.status]}
                        </span>
                      </td>
                      <td data-label="Ocena">
                        <span className={appt.satisfaction_score ? 'stars-desktop' : 'stars-none'}>{stars(appt.satisfaction_score)}</span>
                      </td>
                      <td className="cell-actions">
                        <Link to={`/wizyty/${appt.id}/edytuj`} className="action-icon-btn" title="Edytuj" aria-label="Edytuj" onClick={(e) => e.stopPropagation()}>
                          <Icon name="edit" />
                        </Link>
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
      </div>

      <CalendarMonthSidebar selectedDate={mode === 'chain' ? chainDates[0] ?? iso(weekStart) : iso(weekStart)} onDayClick={handleSidebarDayClick} />

      {statusModalAppt && (
        <StatusChangeModal
          isOpen
          onClose={() => setStatusModalAppt(null)}
          appointmentId={statusModalAppt.id}
          currentStatus={statusModalAppt.status}
          onSuccess={handleStatusUpdated}
        />
      )}
    </div>
  );
}
