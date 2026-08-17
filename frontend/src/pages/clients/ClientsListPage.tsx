import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, MouseEvent, ReactNode } from 'react';
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
import { ScrollTopButton } from '../../components/ui/ScrollTopButton';
import { formatDate, formatNextVisitLine1, formatPhone, parseDateForSort } from '../../lib/format';
import type { Client } from '../../types/client';

type FilterKey = 'active' | 'vip' | 'inactive';
type SortField = 'full_name' | 'last_visit_date' | 'next_visit_date' | 'completed_visits' | 'no_show_count' | 'is_active';

interface SortState {
  field: SortField;
  dir: 'asc' | 'desc';
}

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
  const clientsState = useApiData(() => clientsApi.list({ search: debouncedSearch, includeInactive: true }), [debouncedSearch]);
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

  // Tap-anywhere-on-card navigation (mobile stack-cards view only).
  function handleRowClick(client: Client, event: MouseEvent<HTMLTableRowElement>) {
    if (!window.matchMedia('(max-width: 640px)').matches) return;
    if ((event.target as HTMLElement).closest('.action-icons')) return;
    navigate(`/klienci/${client.id}`);
  }

  const isActiveSort = sortIndicator('is_active');

  return (
    <div className="refined-page clients-page animate-fade-up">
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

      <div className="stat-strip">
        <div className="stat-strip-item">
          <p className="stat-strip-value">{statsState.data?.total_clients ?? '-'}</p>
          <p className="stat-strip-label">Wszyscy</p>
        </div>
        <div className="stat-strip-item">
          <p className="stat-strip-value green">{statsState.data?.active_clients ?? '-'}</p>
          <p className="stat-strip-label">Aktywni</p>
        </div>
        <div className="stat-strip-item">
          <p className="stat-strip-value info">{statsState.data?.recent_visitors ?? '-'}</p>
          <p className="stat-strip-label">Ostatni mies.</p>
        </div>
        <div className="stat-strip-item">
          <p className="stat-strip-value pink">{statsState.data?.clients_with_birthdate ?? '-'}</p>
          <p className="stat-strip-label">Urodziny</p>
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
        <table className="refined-table clients-table stack-cards">
          <colgroup>
            <col style={{ width: '24%' }} />
            <col style={{ width: '12%' }} />
            <col style={{ width: '14%' }} />
            <col style={{ width: '8%' }} />
            <col style={{ width: '9%' }} />
            <col style={{ width: '13%' }} />
            <col style={{ width: '11%' }} />
            <col style={{ width: '9%' }} />
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
              <th>Akcje</th>
            </tr>
          </thead>
          <tbody>
            {clientsState.loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 8 }).map((_, c) => (
                    <td key={c} className={c >= 3 ? 'cell-hide-sm' : ''}>
                      <div className="skeleton" style={{ height: '1rem', borderRadius: '2px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : clientsState.error ? (
              <tr>
                <td colSpan={8} className="empty-state cell-empty">
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
                <td colSpan={8} className="empty-state cell-empty">
                  <Icon name="search_off" className="empty-icon" />
                  <p className="empty-text">Nie znaleziono klientów</p>
                </td>
              </tr>
            ) : (
              sorted.map((client) => (
                <ClientRow key={client.id} client={client} trend={trends[client.id]} canWrite={canWrite} onDeactivate={handleDeactivate} onRowClick={handleRowClick} />
              ))
            )}
          </tbody>
        </table>
      </div>

      <ScrollTopButton />
    </div>
  );
}

interface ClientRowProps {
  client: Client;
  trend: number[] | undefined;
  canWrite: boolean;
  onDeactivate: (client: Client) => void;
  onRowClick: (client: Client, event: MouseEvent<HTMLTableRowElement>) => void;
}

function ClientRow({ client, trend, canWrite, onDeactivate, onRowClick }: ClientRowProps) {
  const initials = `${client.first_name.charAt(0)}${(client.last_name || '').charAt(0)}`.toUpperCase();
  const noShows = client.no_show_count ?? 0;
  const isVip = isVipClient(client);
  const isRisk = noShows > 2;
  const ringColor = isRisk ? 'var(--color-error)' : isVip ? 'var(--color-accent)' : null;
  const ringStyle: CSSProperties | undefined = ringColor
    ? { boxShadow: `0 0 0 2px #fff, 0 0 0 3.5px ${ringColor}` }
    : undefined;

  return (
    <tr data-client-id={client.id} onClick={(e) => onRowClick(client, e)}>
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
