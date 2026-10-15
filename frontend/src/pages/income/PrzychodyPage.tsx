import { useLayoutEffect, useMemo, useRef } from 'react';
import type { MouseEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import '../faktury/FakturyListPage.css';
import './PrzychodyPage.css';
import { useApiData } from '../../lib/useApiData';
import { incomeApi } from '../../lib/api/income';
import { Button } from '../../components/ui/Button';
import { DatePicker } from '../../components/ui/DatePicker';
import { Icon } from '../../lib/icons/Icon';
import { formatDate } from '../../lib/format';
import type { IncomeLedgerRecord } from '../../types/income';

type PeriodType = 'dzien' | 'tydzien' | 'miesiac' | 'rok' | 'zakres';
type SortColumn = 'payment_date' | 'client_name' | 'gross_amount' | 'net_amount' | 'employee_name';
type SortDir = 'asc' | 'desc';
type MethodFilter = 'all' | 'cash' | 'card' | 'other';

const PERIOD_OPTIONS: Array<{ key: PeriodType; label: string }> = [
  { key: 'dzien', label: 'Dzień' },
  { key: 'tydzien', label: 'Tydzień' },
  { key: 'miesiac', label: 'Miesiąc' },
  { key: 'rok', label: 'Rok' },
];
const SORT_COLUMNS: SortColumn[] = ['payment_date', 'client_name', 'gross_amount', 'net_amount', 'employee_name'];
const MONTHS_NOM = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
const RETURN_KEY = 'przychody-return';
const RETURN_MAX_AGE_MS = 30 * 60 * 1000;

// ── dates (local calendar days, never UTC) ─────────────────────────────────
function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function parseIso(v: string | null): Date | null {
  if (!v || !/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
  const [y, m, d] = v.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  return Number.isNaN(date.getTime()) ? null : date;
}
function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}
function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/** The whole day/week/month/year that contains `anchor`. Weeks start on Monday. */
function periodRange(type: Exclude<PeriodType, 'zakres'>, anchor: Date): [Date, Date] {
  if (type === 'dzien') return [anchor, anchor];
  if (type === 'tydzien') {
    const start = addDays(anchor, -((anchor.getDay() + 6) % 7));
    return [start, addDays(start, 6)];
  }
  if (type === 'miesiac') return [new Date(anchor.getFullYear(), anchor.getMonth(), 1), new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0)];
  return [new Date(anchor.getFullYear(), 0, 1), new Date(anchor.getFullYear(), 11, 31)];
}

/** Previous/next whole period — by calendar unit (never a day count, which drifts
 * across months of different lengths); a custom range moves by its own length. */
function shiftRange(type: PeriodType, start: Date, end: Date, dir: 1 | -1): [Date, Date] {
  if (type === 'dzien') return periodRange('dzien', addDays(start, dir));
  if (type === 'tydzien') return periodRange('tydzien', addDays(start, 7 * dir));
  if (type === 'miesiac') return periodRange('miesiac', new Date(start.getFullYear(), start.getMonth() + dir, 1));
  if (type === 'rok') return periodRange('rok', new Date(start.getFullYear() + dir, 0, 1));
  const len = daysBetween(start, end) + 1;
  return [addDays(start, dir * len), addDays(end, dir * len)];
}

function rangeLabel(type: PeriodType, start: Date, end: Date): string {
  const d = (x: Date) => `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}.${x.getFullYear()}`;
  if (type === 'dzien') return d(start);
  if (type === 'miesiac') return `${MONTHS_NOM[start.getMonth()]} ${start.getFullYear()}`;
  if (type === 'rok') return String(start.getFullYear());
  return `${d(start)} – ${d(end)}`;
}

// ── formatting ─────────────────────────────────────────────────────────────
function formatAmount(amount: number | null | undefined): string {
  return (amount ?? 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function methodKey(method: string | null): MethodFilter {
  const m = (method ?? '').trim().toLowerCase();
  if (m === 'gotówka' || m === 'gotowka' || m === 'cash') return 'cash';
  if (m === 'karta' || m === 'card') return 'card';
  return 'other';
}
function methodLabel(method: string | null): string {
  const m = (method ?? '').trim();
  if (!m) return '—';
  return m.charAt(0).toUpperCase() + m.slice(1);
}

function sortValue(r: IncomeLedgerRecord, column: SortColumn): string | number {
  if (column === 'gross_amount' || column === 'net_amount') return r[column] ?? 0;
  if (column === 'payment_date') return r.payment_date;
  return String(r[column] ?? '').toLowerCase();
}

function csvCell(value: string): string {
  return /[";\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Excel-friendly CSV (semicolon, Polish decimal comma, UTF-8 BOM) of exactly the rows on screen. */
function downloadCsv(rows: IncomeLedgerRecord[], from: string, to: string) {
  const header = ['Data wpływu', 'Klient', 'Wartość brutto', 'Wartość netto', 'Udział pracownika', 'Pracownik', 'Metoda płatności', 'Nowy klient'];
  const lines = rows.map((r) =>
    [r.payment_date, r.client_name, formatAmount(r.gross_amount), formatAmount(r.net_amount), formatAmount(r.employee_share), r.employee_name, r.payment_method ?? '', r.is_new_client ? 'tak' : 'nie']
      .map((v) => csvCell(String(v)))
      .join(';'),
  );
  const blob = new Blob(['﻿' + [header.join(';'), ...lines].join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `przychody_${from}_${to}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

interface ReturnSnap {
  search: string;
  tableScrollTop: number;
  mainScrollTop: number;
  savedAt: number;
}

/** Scroll snapshot for "visit page → Powrót" (the filters/period/sort themselves
 * live in the URL, so they come back with the link). Taken once, per tab, 30 min. */
function takeReturnSnap(search: string): ReturnSnap | null {
  try {
    const raw = sessionStorage.getItem(RETURN_KEY);
    sessionStorage.removeItem(RETURN_KEY);
    if (!raw) return null;
    const snap = JSON.parse(raw) as ReturnSnap;
    if (snap.search !== search || Date.now() - snap.savedAt > RETURN_MAX_AGE_MS) return null;
    return snap;
  } catch {
    return null;
  }
}

/**
 * Finanse → Przychody. Rejestr rekordów przychodu (income_records — jeden na
 * zakończoną wizytę) z okresu wg daty wpływu, w tej samej tabeli/zachowaniu co
 * Koszty (FakturyListPage: pigułki filtra, wyszukiwarka, sortowanie kolumn,
 * klik w wiersz, stopka z licznikiem i sumą, eksport). Nad tabelą karty
 * statystyk liczone przez backend dla całego okresu (nie dla wyszukiwania).
 *
 * Cały stan widoku (okres, daty, filtr, szukaj, sortowanie) siedzi w URL-u, więc
 * powrót z widoku wizyty (link przekazuje `returnTo`) albo przyciskiem Wstecz
 * odtwarza dokładnie ten sam widok; pozycję przewinięcia dokłada sessionStorage.
 */
export function PrzychodyPage() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const tableRef = useRef<HTMLDivElement>(null);
  const returnSnap = useRef<ReturnSnap | null | undefined>(undefined);
  if (returnSnap.current === undefined) returnSnap.current = takeReturnSnap(location.search);

  // ── URL state ────────────────────────────────────────────────────────────
  const today = useMemo(() => new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()), []);
  const rawType = params.get('okres') as PeriodType | null;
  const periodType: PeriodType = rawType && ['dzien', 'tydzien', 'miesiac', 'rok', 'zakres'].includes(rawType) ? rawType : 'miesiac';
  const [defStart, defEnd] = periodRange(periodType === 'zakres' ? 'miesiac' : periodType, today);
  let start = parseIso(params.get('od')) ?? defStart;
  let end = parseIso(params.get('do')) ?? defEnd;
  if (end < start) [start, end] = [end, start];
  const from = iso(start);
  const to = iso(end);

  const searchQuery = params.get('q') ?? '';
  const rawMethod = params.get('metoda') as MethodFilter | null;
  const methodFilter: MethodFilter = rawMethod && ['all', 'cash', 'card', 'other'].includes(rawMethod) ? rawMethod : 'all';
  const rawSort = params.get('sort') as SortColumn | null;
  const sort: { column: SortColumn | null; dir: SortDir } = {
    column: rawSort && SORT_COLUMNS.includes(rawSort) ? rawSort : null,
    dir: params.get('kier') === 'desc' ? 'desc' : 'asc',
  };

  function update(patch: Record<string, string | null>) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v === null || v === '') next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: true },
    );
  }
  function setRange(type: PeriodType, s: Date, e: Date) {
    update({ okres: type, od: iso(s), do: iso(e) });
  }

  // ── period controls ──────────────────────────────────────────────────────
  function handlePeriodType(type: PeriodType) {
    if (type === 'zakres') {
      update({ okres: 'zakres', od: from, do: to });
      return;
    }
    const [s, e] = periodRange(type, start);
    setRange(type, s, e);
  }
  function handleShift(dir: 1 | -1) {
    const [s, e] = shiftRange(periodType, start, end, dir);
    setRange(periodType, s, e);
  }
  function handleNow() {
    if (periodType === 'zakres') {
      const len = daysBetween(start, end);
      setRange('zakres', addDays(today, -len), today);
      return;
    }
    const [s, e] = periodRange(periodType, today);
    setRange(periodType, s, e);
  }
  function handleFrom(value: string) {
    const s = parseIso(value);
    if (!s) return;
    setRange('zakres', s, s > end ? s : end);
  }
  function handleTo(value: string) {
    const e = parseIso(value);
    if (!e) return;
    setRange('zakres', e < start ? e : start, e);
  }

  // ── data ─────────────────────────────────────────────────────────────────
  const ledgerState = useApiData(() => incomeApi.ledger(from, to), [from, to]);
  const records = useMemo(() => ledgerState.data?.records ?? [], [ledgerState.data]);
  const stats = ledgerState.data?.stats;

  const filterCounts = useMemo(
    () => ({
      all: records.length,
      cash: records.filter((r) => methodKey(r.payment_method) === 'cash').length,
      card: records.filter((r) => methodKey(r.payment_method) === 'card').length,
      other: records.filter((r) => methodKey(r.payment_method) === 'other').length,
    }),
    [records],
  );

  const filtered = useMemo(() => {
    let list = records;
    if (methodFilter !== 'all') list = list.filter((r) => methodKey(r.payment_method) === methodFilter);
    const q = searchQuery.toLowerCase().trim();
    if (q) list = list.filter((r) => [r.client_name, r.employee_name, r.payment_method].filter(Boolean).join(' ').toLowerCase().includes(q));
    if (sort.column) {
      const { column, dir } = sort;
      list = [...list].sort((a, b) => {
        const av = sortValue(a, column);
        const bv = sortValue(b, column);
        const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : av < bv ? -1 : av > bv ? 1 : 0;
        return dir === 'asc' ? cmp : -cmp;
      });
    }
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [records, methodFilter, searchQuery, sort.column, sort.dir]);

  const filteredGross = useMemo(() => filtered.reduce((s, r) => s + (r.gross_amount || 0), 0), [filtered]);
  const filteredNet = useMemo(() => filtered.reduce((s, r) => s + (r.net_amount || 0), 0), [filtered]);

  // Put the scroll position back once the rows of the restored view are on screen.
  useLayoutEffect(() => {
    const snap = returnSnap.current;
    if (!snap || ledgerState.loading || !ledgerState.data) return;
    returnSnap.current = null;
    if (tableRef.current) tableRef.current.scrollTop = snap.tableScrollTop;
    const main = document.getElementById('main-content');
    if (main) main.scrollTop = snap.mainScrollTop;
  }, [ledgerState.loading, ledgerState.data]);

  // ── table behaviour (1:1 with Koszty) ──────────────────────────────────
  function handleSort(column: SortColumn) {
    const dir: SortDir = sort.column === column && sort.dir === 'asc' ? 'desc' : 'asc';
    update({ sort: column, kier: dir });
  }
  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return { ariaSort: 'none' as const, glyph: '↕', active: false };
    return { ariaSort: sort.dir === 'asc' ? ('ascending' as const) : ('descending' as const), glyph: sort.dir === 'asc' ? '↑' : '↓', active: true };
  }

  const visitState = { returnTo: `/przychody${location.search}`, returnLabel: 'Powrót do przychodów' };
  function rememberScroll() {
    try {
      const snap: ReturnSnap = {
        search: location.search,
        tableScrollTop: tableRef.current?.scrollTop ?? 0,
        mainScrollTop: document.getElementById('main-content')?.scrollTop ?? 0,
        savedAt: Date.now(),
      };
      sessionStorage.setItem(RETURN_KEY, JSON.stringify(snap));
    } catch {
      /* storage unavailable: the way back just starts at the top */
    }
  }
  function handleRowClick(record: IncomeLedgerRecord, event: MouseEvent<HTMLTableRowElement>) {
    if ((event.target as HTMLElement).closest('.row-actions')) return;
    rememberScroll();
    navigate(`/wizyty/${record.appointment_id}`, { state: visitState });
  }

  const columns: Array<{ column: SortColumn; label: string; amount?: boolean }> = [
    { column: 'payment_date', label: 'Data wpływu' },
    { column: 'client_name', label: 'Klient' },
    { column: 'gross_amount', label: 'Wartość brutto', amount: true },
    { column: 'net_amount', label: 'Wartość netto', amount: true },
    { column: 'employee_name', label: 'Pracownik' },
  ];
  const pills: Array<{ key: MethodFilter; label: string }> = [
    { key: 'all', label: 'Wszystkie' },
    { key: 'cash', label: 'Gotówka' },
    { key: 'card', label: 'Karta' },
    { key: 'other', label: 'Inne' },
  ];
  const lost = stats?.lost;
  const lostRows: Array<{ key: 'client_cancel' | 'no_show' | 'salon_cancel'; label: string }> = [
    { key: 'client_cancel', label: 'Odwołane przez klienta' },
    { key: 'no_show', label: 'Klient nie przyszedł' },
    { key: 'salon_cancel', label: 'Odwołane przez salon' },
  ];
  const statValue = (v: string) => (ledgerState.loading && !stats ? '–' : v);

  return (
    <div className="refined-page page-fills-viewport income-page animate-fade-up">
      <header className="page-header">
        <h1 className="page-title">Wykaz przychodów</h1>
        <div className="page-header-actions">
          <Button variant="secondary" icon="download" onClick={() => downloadCsv(filtered, from, to)} disabled={filtered.length === 0} title="Eksport widocznych wierszy do CSV (Excel)">
            Eksport
          </Button>
        </div>
      </header>

      <div className="income-period-bar" role="group" aria-label="Okres">
        <div className="income-period-nav">
          <button type="button" className="refined-btn-secondary refined-btn-sm" title="Poprzedni okres" aria-label="Poprzedni okres" onClick={() => handleShift(-1)}>
            <Icon name="chevron_left" />
          </button>
          <button type="button" className="refined-btn-secondary refined-btn-sm" onClick={handleNow}>
            Teraz
          </button>
          <button type="button" className="refined-btn-secondary refined-btn-sm" title="Następny okres" aria-label="Następny okres" onClick={() => handleShift(1)}>
            <Icon name="chevron_right" />
          </button>
        </div>
        <label className="income-period-field">
          <span className="income-period-label">Okres</span>
          <select className="form-select income-period-select" value={periodType} onChange={(e) => handlePeriodType(e.target.value as PeriodType)}>
            {PERIOD_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
            <option value="zakres">Własny zakres</option>
          </select>
        </label>
        <div className="income-period-field">
          <label className="income-period-label" htmlFor="przychody-od">
            Od
          </label>
          <div className="income-period-date">
            <DatePicker id="przychody-od" value={from} onChange={handleFrom} />
          </div>
        </div>
        <div className="income-period-field">
          <label className="income-period-label" htmlFor="przychody-do">
            Do
          </label>
          <div className="income-period-date">
            <DatePicker id="przychody-do" value={to} onChange={handleTo} />
          </div>
        </div>
        <p className="income-period-desc">{rangeLabel(periodType, start, end)}</p>
      </div>

      <div className="income-stats" aria-busy={ledgerState.loading}>
        <div className="stat-card income-stat">
          <div>
            <p className="stat-label">Liczba wpływów</p>
            <p className="stat-value">{statValue(String(stats?.count ?? 0))}</p>
            <p className="income-stat-sub">wizyt rozliczonych w okresie</p>
          </div>
          <div className="stat-icon blue">
            <Icon name="assessment" />
          </div>
        </div>
        <div className="stat-card income-stat">
          <div>
            <p className="stat-label">Średnia wartość brutto</p>
            <p className="stat-value">{statValue(`${formatAmount(stats?.avg_gross)} zł`)}</p>
            <p className="income-stat-sub">na jeden wpływ</p>
          </div>
          <div className="stat-icon purple">
            <Icon name="percent" />
          </div>
        </div>
        <div className="stat-card income-stat">
          <div>
            <p className="stat-label">Suma brutto</p>
            <p className="stat-value green">{statValue(`${formatAmount(stats?.total_gross)} zł`)}</p>
            <p className="income-stat-sub">netto: {formatAmount(stats?.total_net)} zł</p>
          </div>
          <div className="stat-icon green">
            <Icon name="payments" />
          </div>
        </div>
        <div className="stat-card income-stat income-stat--lost">
          <div className="income-stat-body">
            <p className="stat-label">Utracone brutto</p>
            <p className="stat-value orange">{statValue(`${formatAmount(lost?.amount)} zł`)}</p>
            <ul className="income-lost-list">
              {lostRows.map((row) => (
                <li key={row.key}>
                  <span className="income-lost-label">{row.label}</span>
                  <span className="income-lost-value">
                    {formatAmount(lost?.[row.key].amount)} zł <span className="income-lost-count">({lost?.[row.key].visits ?? 0})</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="stat-icon orange">
            <Icon name="event_busy" />
          </div>
        </div>
        <div className="stat-card income-stat">
          <div>
            <p className="stat-label">Nowi klienci</p>
            <p className="stat-value pink">{statValue(`${(stats?.new_client_pct ?? 0).toLocaleString('pl-PL', { maximumFractionDigits: 1 })}%`)}</p>
            <p className="income-stat-sub">
              {formatAmount(stats?.new_client_gross)} zł brutto · {stats?.new_client_visits ?? 0} wizyt
            </p>
          </div>
          <div className="stat-icon pink">
            <Icon name="person" />
          </div>
        </div>
      </div>

      <div className="filter-pills">
        {pills.map((p) => (
          <button key={p.key} type="button" className={`filter-pill${methodFilter === p.key ? ' active' : ''}`} onClick={() => update({ metoda: p.key === 'all' ? null : p.key })}>
            {p.label} <span className="count">{filterCounts[p.key]}</span>
          </button>
        ))}
      </div>

      <div className="invoice-search-bar">
        <div className="invoice-search-wrapper">
          <svg className="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            className="search-input"
            placeholder="Szukaj po kliencie, pracowniku lub metodzie płatności..."
            autoComplete="off"
            value={searchQuery}
            onChange={(e) => update({ q: e.target.value })}
          />
        </div>
      </div>

      <div className="table-container" ref={tableRef}>
        <table className="refined-table stack-cards">
          <thead>
            <tr>
              {columns.map((col) => {
                const ind = sortIndicator(col.column);
                return (
                  <th key={col.column} className={`th-sortable${ind.active ? ' sort-active' : ''}${col.amount ? ' col-amount' : ''}`} aria-sort={ind.ariaSort}>
                    <button type="button" className="th-sort-btn" onClick={() => handleSort(col.column)}>
                      {col.label} <span className="th-sort-icon" aria-hidden="true">{ind.glyph}</span>
                    </button>
                  </th>
                );
              })}
              <th>Metoda płatności</th>
              <th>
                <span className="sr-only">Akcje</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {ledgerState.loading && !ledgerState.data ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 7 }).map((_, c) => (
                    <td key={c}>
                      <div className="skeleton" style={{ height: '1rem', borderRadius: '2px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : ledgerState.error ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                    Błąd ładowania przychodów: {ledgerState.error.message}
                  </p>
                  <Button variant="secondary" style={{ marginTop: '0.75rem' }} onClick={() => ledgerState.reload()}>
                    Spróbuj ponownie
                  </Button>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <Icon name="search_off" className="empty-icon" />
                  <h3 className="empty-title">Brak przychodów</h3>
                  <p className="empty-text">{records.length === 0 ? 'W wybranym okresie nie rozliczono żadnej wizyty.' : 'Żaden wpływ nie pasuje do filtra lub wyszukiwania.'}</p>
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.id} className="row-clickable" onClick={(e) => handleRowClick(r, e)}>
                  <td className="cell-name" data-label="Data wpływu">
                    <span className="date-value income-date">{formatDate(r.payment_date)}</span>
                  </td>
                  <td data-label="Klient">
                    <span className="seller-name" title={r.client_name}>
                      {r.client_name}
                      {r.is_new_client && <span className="income-new-badge">nowy</span>}
                    </span>
                  </td>
                  <td className="col-amount" data-label="Wartość brutto">
                    <span className="amount-value">{formatAmount(r.gross_amount)}</span>
                    <span className="currency-code">zł</span>
                  </td>
                  <td className="col-amount" data-label="Wartość netto" title={`Udział pracownika: ${formatAmount(r.employee_share)} zł`}>
                    <span className="amount-value">{formatAmount(r.net_amount)}</span>
                    <span className="currency-code">zł</span>
                  </td>
                  <td data-label="Pracownik">
                    <span className="seller-name" title={r.employee_name}>
                      {r.employee_name}
                    </span>
                  </td>
                  <td data-label="Metoda płatności">
                    <span className={`income-method income-method--${methodKey(r.payment_method)}`}>{methodLabel(r.payment_method)}</span>
                  </td>
                  <td className="cell-actions">
                    <div className="row-actions">
                      <Link
                        to={`/wizyty/${r.appointment_id}`}
                        state={visitState}
                        className="action-btn"
                        title="Otwórz wizytę"
                        aria-label={`Otwórz wizytę: ${r.client_name}, ${formatDate(r.payment_date)}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          rememberScroll();
                        }}
                      >
                        <Icon name="open_in_new" />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <div className="pagination-bar">
          <span>
            Wyświetlono <span className="pagination-count">{filtered.length}</span> z <span className="pagination-count">{records.length}</span> wpływów
          </span>
          <span>
            Suma brutto: <span className="pagination-count">{formatAmount(filteredGross)} zł</span> · netto: <span className="pagination-count">{formatAmount(filteredNet)} zł</span>
          </span>
        </div>
      </div>
    </div>
  );
}
