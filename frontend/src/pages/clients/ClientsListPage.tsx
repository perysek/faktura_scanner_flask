import { useEffect, useMemo, useState } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './ClientsListPage.css';
import { useApiData } from '../../lib/useApiData';
import { clientsApi } from '../../lib/api/clients';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { TrendSparkline, isVipClient } from '../../components/clients/TrendSparkline';
import { NotesDigest } from '../../components/visitNotes/NotesDigest';
import { formatDate, formatNextVisitLine1, formatPhone, parseDateForSort } from '../../lib/format';
import { useIsMobile } from '../appointments/MobileWizytyCalendarView';
import { ClientsMobileView } from './ClientsMobileView';
import { DEFAULT_SORT_DIR, clientInitials, clientRingStyle } from './clientsListShared';
import type { FilterKey, SortField, SortState } from './clientsListShared';
import type { Client } from '../../types/client';

const SESSION_KEY = 'filterState:clients';

interface SessionState {
  searchInput?: string;
  _sortField?: SortField;
  _sortDir?: 'asc' | 'desc';
  _filter?: FilterKey;
}

function loadSessionState(): SessionState {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as SessionState) : {};
  } catch {
    return {};
  }
}

const SORT_COLUMNS: Array<{ field: SortField; label: ReactNode }> = [
  { field: 'full_name', label: 'Klient' },
  { field: 'last_visit_date', label: 'Ostatnia wizyta' },
  { field: 'next_visit_date', label: 'Następna wizyta' },
  { field: 'completed_visits', label: 'Wizyt' },
  { field: 'no_show_count', label: <>No&#8209;show</> },
];

// <colgroup> widths (%) for the fixed-layout table — Klient, Ostatnia wizyta, Następna
// wizyta, Wizyt, No-show, Trend, Status, [Aktualne uwagi i zalecenia], Akcje. Each set
// sums to 100. The notes column only exists for callers with `appointments` access.
const COL_WIDTHS = [24, 12, 14, 8, 9, 13, 11, 9];
// Sized from measured minimums at 1440px (table ~1117px): No-show's header needs ~90px,
// the Status pill ~100px incl. padding, Akcje (2 icons) ~90px; the notes column takes the rest.
const COL_WIDTHS_WITH_NOTES = [19, 9, 9, 5, 8, 8, 9, 25, 8];

/**
 * Klienci — list page. Pilot module, Faza 1 (phase-01-pilot-clients.md §1.3).
 * Ported 1:1 from templates/clients/list.html: same columns, same client-side
 * sort/filter over one always-include_inactive fetch, same sparkline/VIP-ring
 * logic, same sessionStorage state restore. `Modals.confirm`/bespoke toast →
 * useConfirm()/useToast() (DESIGN.md §8).
 */
export function ClientsListPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const canWrite = auth.hasModuleWrite('clients');
  // "Aktualne uwagi i zalecenia" shows visit notes, so it follows the `appointments`
  // module (the server drops `recent_notes` for anyone without it).
  const showNotes = auth.hasModuleAccess('appointments');
  // Phone cards' "Umów wizytę" (swipe right / ⋯ sheet) needs the right to create visits; the
  // list then also asks the server for each client's last service, to prefill the new visit with.
  const canSchedule = auth.hasModuleWrite('appointments');
  const isMobile = useIsMobile(640);
  const wantLastService = isMobile && canSchedule;

  const initial = useMemo(loadSessionState, []);
  const [searchInput, setSearchInput] = useState(initial.searchInput ?? '');
  const [debouncedSearch, setDebouncedSearch] = useState(initial.searchInput ?? '');
  const [activeFilter, setActiveFilter] = useState<FilterKey>(initial._filter ?? 'active');
  const [sort, setSort] = useState<SortState>({
    field: initial._sortField ?? 'last_visit_date',
    dir: initial._sortDir ?? 'desc',
  });
  const [isUpdatingPrefs, setIsUpdatingPrefs] = useState(false);

  // Debounced live search: re-fetch 250ms after the user stops typing; Enter
  // fires immediately (list.html's exact behaviour — the search box has no button).
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    try {
      const state: SessionState = { searchInput, _sortField: sort.field, _sortDir: sort.dir, _filter: activeFilter };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
  }, [searchInput, sort, activeFilter]);

  // Always fetch inactive too — the chips filter client-side and need
  // accurate counts for all three states (Aktywni / VIP / Nieaktywni).
  const clientsState = useApiData(
    () => clientsApi.list({ search: debouncedSearch, includeInactive: true, includeNotes: showNotes, includeLastService: wantLastService }),
    [debouncedSearch, showNotes, wantLastService],
  );
  const trendsState = useApiData(() => clientsApi.visitTrends(), []);
  const statsState = useApiData(() => clientsApi.statistics(), []);

  const allClients = useMemo(() => clientsState.data ?? [], [clientsState.data]);
  const trends = trendsState.data ?? {};

  const filterCounts = useMemo(
    () => ({
      active: allClients.filter((c) => c.is_active).length,
      vip: allClients.filter(isVipClient).length,
      inactive: allClients.filter((c) => !c.is_active).length,
    }),
    [allClients],
  );

  const filtered = useMemo(() => {
    if (activeFilter === 'vip') return allClients.filter(isVipClient);
    if (activeFilter === 'inactive') return allClients.filter((c) => !c.is_active);
    return allClients.filter((c) => c.is_active);
  }, [allClients, activeFilter]);

  const sorted = useMemo(() => {
    const { field, dir } = sort;
    const copy = [...filtered];
    copy.sort((a, b) => {
      let av: string | number;
      let bv: string | number;
      if (field === 'last_visit_date' || field === 'next_visit_date') {
        av = parseDateForSort(a[field] ?? null);
        bv = parseDateForSort(b[field] ?? null);
        // No date (parses to 0) carries no signal — it sinks to the bottom whichever way
        // the list is sorted, instead of leading an ascending "Następna wizyta".
        if (!av || !bv) return !av && !bv ? 0 : !av ? 1 : -1;
      } else if (field === 'is_active') {
        av = a.is_active ? 1 : 0;
        bv = b.is_active ? 1 : 0;
      } else if (field === 'completed_visits' || field === 'no_show_count') {
        av = a[field] ?? 0;
        bv = b[field] ?? 0;
      } else {
        av = (a[field] ?? '').toLowerCase();
        bv = (b[field] ?? '').toLowerCase();
      }
      if (av < bv) return dir === 'asc' ? -1 : 1;
      if (av > bv) return dir === 'asc' ? 1 : -1;
      return 0;
    });
    return copy;
  }, [filtered, sort]);

  function handleSort(field: SortField) {
    setSort((current) => (current.field === field ? { field, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { field, dir: 'asc' }));
  }

  // Phone sort sheet: picking a new field starts in the direction people expect for it
  // (DEFAULT_SORT_DIR); picking the active one flips it.
  function handleSelectSort(field: SortField) {
    setSort((current) => (current.field === field ? { field, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { field, dir: DEFAULT_SORT_DIR[field] }));
  }

  function sortIndicator(field: SortField): { ariaSort: 'none' | 'ascending' | 'descending'; glyph: string; active: boolean } {
    if (sort.field !== field) return { ariaSort: 'none', glyph: '▲', active: false };
    const ariaSort: 'ascending' | 'descending' = sort.dir === 'asc' ? 'ascending' : 'descending';
    return { ariaSort, glyph: sort.dir === 'asc' ? '▲' : '▼', active: true };
  }

  async function handleDeactivate(client: Client) {
    const ok = await confirm({
      title: 'Dezaktywacja klienta',
      message: `Dezaktywować klienta "${client.full_name}"?`,
      confirmText: 'Dezaktywuj',
    });
    if (!ok) return;
    try {
      await clientsApi.deactivate(client.id);
      toast.success(`Klient "${client.full_name}" został dezaktywowany.`);
      clientsState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd dezaktywacji');
    }
  }

  async function handleBulkUpdatePreferences() {
    setIsUpdatingPrefs(true);
    try {
      const result = await clientsApi.bulkUpdatePreferences();
      toast.success(`✓ Zaktualizowano preferencje dla ${result.updated_count} z ${result.total_count} klientów`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji preferencji');
    } finally {
      setIsUpdatingPrefs(false);
    }
  }

  // Clickable row = same target as "Zobacz" (view) — DESIGN.md §20. Started
  // as mobile-only tap-anywhere-on-card; now applies at every viewport size.
  function handleRowClick(client: Client, event: MouseEvent<HTMLTableRowElement>) {
    if ((event.target as HTMLElement).closest('.action-icons')) return;
    navigate(`/klienci/${client.id}`);
  }

  if (isMobile) {
    return (
      <ClientsMobileView
        clients={sorted}
        loading={clientsState.loading}
        error={clientsState.error}
        onRetry={clientsState.reload}
        searchInput={searchInput}
        onSearchChange={setSearchInput}
        onSearchSubmit={() => setDebouncedSearch(searchInput)}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        filterCounts={filterCounts}
        sort={sort}
        onSelectSort={handleSelectSort}
        canWrite={canWrite}
        canSchedule={canSchedule}
        linkedEmployeeId={auth.linkedEmployeeId}
        showNotes={showNotes}
        onBulkUpdatePreferences={handleBulkUpdatePreferences}
        isUpdatingPrefs={isUpdatingPrefs}
      />
    );
  }

  const isActiveSort = sortIndicator('is_active');
  const colWidths = showNotes ? COL_WIDTHS_WITH_NOTES : COL_WIDTHS;
  // Columns in the body: 8 base + the notes column.
  const columnCount = colWidths.length;
  const notesColIndex = 7;

  return (
    <div className="refined-page clients-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Klienci</h1>
          <p className="page-subtitle">Zarządzanie bazą klientów salonu · {sorted.length} wyświetlonych</p>
        </div>
        <div className="page-header-actions">
          {canWrite && (
            <Button variant="secondary" icon="auto_awesome" isLoading={isUpdatingPrefs} loadingText="Aktualizowanie…" onClick={handleBulkUpdatePreferences}>
              Aktualizuj preferencje
            </Button>
          )}
          {canWrite && (
            <ButtonLink variant="primary" icon="add" to="/klienci/nowy">
              Dodaj klienta
            </ButtonLink>
          )}
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div>
            <p className="stat-label">Wszyscy</p>
            <p className="stat-value">{statsState.data?.total_clients ?? '-'}</p>
          </div>
          <div className="stat-icon blue">
            <Icon name="people" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Aktywni</p>
            <p className="stat-value green">{statsState.data?.active_clients ?? '-'}</p>
          </div>
          <div className="stat-icon green">
            <Icon name="check_circle" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Ostatni mies.</p>
            <p className="stat-value blue">{statsState.data?.recent_visitors ?? '-'}</p>
          </div>
          <div className="stat-icon blue">
            <Icon name="calendar_today" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Urodziny</p>
            <p className="stat-value pink">{statsState.data?.clients_with_birthdate ?? '-'}</p>
          </div>
          <div className="stat-icon pink">
            <Icon name="cake" />
          </div>
        </div>
      </div>

      <div className="filter-row">
        <div className="filter-chips" role="group" aria-label="Filtruj klientów">
          <button type="button" className={`filter-chip${activeFilter === 'active' ? ' active' : ''}`} onClick={() => setActiveFilter('active')}>
            Aktywni <span className="chip-count">{filterCounts.active}</span>
          </button>
          <button
            type="button"
            className={`filter-chip${activeFilter === 'vip' ? ' active' : ''}`}
            title="Minimum 3 wizyty w ostatnich 8 tygodniach"
            onClick={() => setActiveFilter('vip')}
          >
            VIP <span className="chip-count">{filterCounts.vip}</span>
          </button>
          <button
            type="button"
            className={`filter-chip${activeFilter === 'inactive' ? ' active' : ''}`}
            title="Zdezaktywowani klienci"
            onClick={() => setActiveFilter('inactive')}
          >
            Nieaktywni <span className="chip-count">{filterCounts.inactive}</span>
          </button>
        </div>
        <div className="search-box-inline">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Szukaj po imieniu, telefonie lub emailu..."
            className="refined-input"
            aria-label="Szukaj klientów"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setDebouncedSearch(searchInput);
            }}
          />
        </div>
      </div>

      <div className="table-container stack-cards-wrap" aria-live="polite" aria-label="Lista klientów">
        <table className={`refined-table clients-table stack-cards${showNotes ? ' clients-table--notes' : ''}`}>
          <colgroup>
            {colWidths.map((width, i) => (
              <col key={i} className={showNotes && i === notesColIndex ? 'vn-col-notes' : undefined} style={{ width: `${width}%` }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {SORT_COLUMNS.map((col) => {
                const indicator = sortIndicator(col.field);
                return (
                  <th key={col.field} className={`th-sortable${indicator.active ? ' sort-active' : ''}`} aria-sort={indicator.ariaSort}>
                    <button type="button" className="th-sort-btn" onClick={() => handleSort(col.field)}>
                      {col.label}
                      <span className="th-sort-icon" aria-hidden="true">
                        {indicator.glyph}
                      </span>
                    </button>
                  </th>
                );
              })}
              <th>
                Trend
                <br />
                <span style={{ fontSize: '0.5625rem', fontWeight: 400, letterSpacing: 0, textTransform: 'none' }}>6 mies.</span>
              </th>
              <th className={`th-sortable${isActiveSort.active ? ' sort-active' : ''}`} aria-sort={isActiveSort.ariaSort}>
                <button type="button" className="th-sort-btn" onClick={() => handleSort('is_active')}>
                  Status
                  <span className="th-sort-icon" aria-hidden="true">
                    {isActiveSort.glyph}
                  </span>
                </button>
              </th>
              {showNotes && <th className="vn-th-notes">Aktualne uwagi i zalecenia</th>}
              <th>Akcje</th>
            </tr>
          </thead>
          <tbody>
            {clientsState.loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: columnCount }).map((_, c) => (
                    <td key={c} className={c >= 3 ? 'cell-hide-sm' : ''}>
                      <div className="skeleton" style={{ height: '1rem', borderRadius: '2px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : clientsState.error ? (
              <tr>
                <td colSpan={columnCount} className="empty-state cell-empty">
                  <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                    Błąd ładowania klientów: {clientsState.error.message}
                  </p>
                  <Button variant="secondary" style={{ marginTop: '0.75rem' }} onClick={() => clientsState.reload()}>
                    Spróbuj ponownie
                  </Button>
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={columnCount} className="empty-state cell-empty">
                  <Icon name="search_off" className="empty-icon" />
                  <p className="empty-text">Nie znaleziono klientów</p>
                </td>
              </tr>
            ) : (
              sorted.map((client) => (
                <ClientRow key={client.id} client={client} trend={trends[client.id]} canWrite={canWrite} showNotes={showNotes} onDeactivate={handleDeactivate} onRowClick={handleRowClick} />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface ClientRowProps {
  client: Client;
  trend: number[] | undefined;
  canWrite: boolean;
  showNotes: boolean;
  onDeactivate: (client: Client) => void;
  onRowClick: (client: Client, event: MouseEvent<HTMLTableRowElement>) => void;
}

function ClientRow({ client, trend, canWrite, showNotes, onDeactivate, onRowClick }: ClientRowProps) {
  const initials = clientInitials(client);
  const noShows = client.no_show_count ?? 0;
  const isVip = isVipClient(client);
  const ringStyle = clientRingStyle(client);

  return (
    <tr className="row-clickable" data-client-id={client.id} onClick={(e) => onRowClick(client, e)}>
      <td className="cell-name" data-label="Klient">
        <div className="client-info">
          <div className="client-avatar" style={ringStyle}>
            {initials}
          </div>
          <div>
            <div className="client-name">
              {client.full_name}
              {isVip && <span className="vip-tag">★ VIP</span>}
            </div>
            {client.phone && <div className="client-phone">{formatPhone(client.phone)}</div>}
          </div>
        </div>
      </td>
      <td data-label="Ostatnia wizyta">{formatDate(client.last_visit_date)}</td>
      <td data-label="Następna wizyta">
        {client.next_visit_date ? (
          <div className="next-visit-desk">
            {formatNextVisitLine1(client.next_visit_date, client.next_visit_time)}
            {client.next_visit_employee && <div className="nv-emp">{client.next_visit_employee}</div>}
          </div>
        ) : (
          <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>
        )}
      </td>
      <td data-label="Wizyt">
        <span className="visit-count">{client.completed_visits ?? 0}</span>
      </td>
      <td data-label="No-show">
        {noShows > 2 ? <span className="noshow-count-danger">{noShows}</span> : <span className="visit-count">{noShows}</span>}
      </td>
      <td className="trend-cell cell-hide-sm" data-label="Trend">
        <TrendSparkline months={trend} />
      </td>
      <td className="cell-hide-lg" data-label="Odwołał">
        <span className="visit-count">{client.cancelled_count ?? 0}</span>
      </td>
      <td className="cell-hide-lg" data-label="Telefon">
        {client.phone ? formatPhone(client.phone) : <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>}
      </td>
      <td className="status-cell" data-label="Status">
        <span className={`status-badge ${client.is_active ? 'active' : 'inactive'}`}>{client.is_active ? 'Aktywny' : 'Nieaktywny'}</span>
      </td>
      {showNotes && (
        <td className="vn-cell-notes" data-label="Aktualne uwagi i zalecenia">
          <NotesDigest notes={client.recent_notes} />
        </td>
      )}
      <td className="cell-actions" style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
        <div className="action-icons">
          <Link to={`/klienci/${client.id}`} className="action-icon-btn" title="Zobacz" aria-label="Zobacz">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
          </Link>
          {canWrite && (
            <Link to={`/klienci/${client.id}/edytuj`} className="action-icon-btn" title="Edytuj" aria-label="Edytuj">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
            </Link>
          )}
          {canWrite && client.is_active && noShows > 2 && (
            <button
              type="button"
              className="action-icon-btn danger"
              title="Dezaktywuj klienta"
              aria-label="Dezaktywuj klienta"
              onClick={(e) => {
                e.stopPropagation();
                onDeactivate(client);
              }}
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
