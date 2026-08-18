import { useEffect, useMemo, useState } from 'react';
import type { MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './ServicesListPage.css';
import { useApiData } from '../../lib/useApiData';
import { servicesApi } from '../../lib/api/services';
import { useAuth } from '../../contexts/AuthContext';
import { ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import type { Service } from '../../types/service';

type SortColumn = 'name' | 'service_type' | 'category' | 'duration_minutes' | 'price' | 'is_active';
type SortDir = 'asc' | 'desc';

const SESSION_KEY = 'filterState:services';

function sortValue(s: Service, column: SortColumn): string | number {
  if (column === 'duration_minutes' || column === 'price') return s[column] ?? 0;
  if (column === 'is_active') return s.is_active ? 1 : 0;
  return String(s[column] ?? '').toLowerCase();
}

function daysSince(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86400000));
}

/**
 * Usługi — lista + CRUD (pierwsza z czterech pod-stron modułu, patrz
 * implementation-log.md — "Średnia" z module-inventory.md okazała się
 * zaniżona, tak jak przy Sprzedawcach). Ported 1:1 z templates/services/list.html:
 * search/typ/nieaktywne filtrowane SERWEROWO (nie klient-side jak u
 * Sprzedawców — ta lista faktycznie używa `search`/`type`/`active_only`),
 * sortowanie klient-side nad już pobranym zbiorem, stan filtrów w
 * sessionStorage (`saveFilterState`/`restoreFilterState` z oryginału).
 */
export function ServicesListPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const canWrite = auth.hasModuleWrite('services');

  const initial = useMemo(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as { search?: string; type?: string; showInactive?: boolean }) : {};
    } catch {
      return {};
    }
  }, []);

  const [search, setSearch] = useState(initial.search ?? '');
  const [debouncedSearch, setDebouncedSearch] = useState(initial.search ?? '');
  const [typeFilter, setTypeFilter] = useState(initial.type ?? '');
  const [showInactive, setShowInactive] = useState(initial.showInactive ?? false);
  const [sort, setSort] = useState<{ column: SortColumn | null; dir: SortDir }>({ column: null, dir: 'asc' });

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ search, type: typeFilter, showInactive }));
    } catch {
      /* ignore */
    }
  }, [search, typeFilter, showInactive]);

  const servicesState = useApiData(() => servicesApi.list({ search: debouncedSearch, type: typeFilter, activeOnly: !showInactive }), [debouncedSearch, typeFilter, showInactive]);
  const statsState = useApiData(() => servicesApi.statistics(), []);

  const services = useMemo(() => servicesState.data ?? [], [servicesState.data]);
  const sorted = useMemo(() => {
    if (!sort.column) return services;
    const { column, dir } = sort;
    return [...services].sort((a, b) => {
      const av = sortValue(a, column);
      const bv = sortValue(b, column);
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : av < bv ? -1 : av > bv ? 1 : 0;
      return dir === 'asc' ? cmp : -cmp;
    });
  }, [services, sort]);

  function handleSort(column: SortColumn) {
    setSort((current) => (current.column === column ? { column, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { column, dir: 'asc' }));
  }

  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return { ariaSort: 'none' as const, glyph: '↕', active: false };
    const ariaSort = sort.dir === 'asc' ? ('ascending' as const) : ('descending' as const);
    return { ariaSort, glyph: sort.dir === 'asc' ? '↑' : '↓', active: true };
  }

  // Row-click mirrors "Zobacz" (view) — DESIGN.md §20.
  function handleRowClick(service: Service, event: MouseEvent<HTMLTableRowElement>) {
    if ((event.target as HTMLElement).closest('.action-icons')) return;
    navigate(`/uslugi/${service.id}`);
  }

  const columns: Array<{ column: SortColumn; label: string }> = [
    { column: 'name', label: 'Nazwa usługi' },
    { column: 'service_type', label: 'Typ' },
    { column: 'category', label: 'Kategoria' },
    { column: 'duration_minutes', label: 'Czas trwania' },
    { column: 'price', label: 'Cena' },
    { column: 'is_active', label: 'Status' },
  ];

  return (
    <div className="refined-page services-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Usługi</h1>
          <p className="page-subtitle">Zarządzanie katalogiem usług salonu</p>
        </div>
        {canWrite && (
          <ButtonLink variant="primary" icon="add" to="/uslugi/nowa">
            Dodaj usługę
          </ButtonLink>
        )}
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div>
            <p className="stat-label">Wszystkie usługi</p>
            <p className="stat-value">{statsState.data?.total_services ?? '-'}</p>
          </div>
          <div className="stat-icon blue">
            <Icon name="spa" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Aktywne</p>
            <p className="stat-value green">{statsState.data?.active_services ?? '-'}</p>
          </div>
          <div className="stat-icon green">
            <Icon name="check_circle" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Średnia cena</p>
            <p className="stat-value purple">{statsState.data?.avg_price !== undefined ? `${statsState.data.avg_price.toFixed(2)} zł` : '-'}</p>
          </div>
          <div className="stat-icon purple">
            <Icon name="payments" />
          </div>
        </div>
      </div>

      <div className="search-card">
        <div className="search-wrapper">
          <input type="text" className="refined-input" placeholder="Szukaj po nazwie, kategorii lub opisie..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ flex: 1, minWidth: '220px' }} />
          <select className="form-select" aria-label="Filtruj według typu usługi" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ minWidth: '140px' }}>
            <option value="">Wszystkie typy</option>
            <option value="main">Główne</option>
            <option value="addon">Dodatkowe</option>
          </select>
          <label className="filter-checkbox-label">
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Pokaż nieaktywne
          </label>
        </div>
      </div>

      <div className="table-container">
        <table className="refined-table">
          <thead>
            <tr>
              {columns.map((col) => {
                const ind = sortIndicator(col.column);
                return (
                  <th key={col.column} className={`th-sortable${ind.active ? ' sort-active' : ''}`} aria-sort={ind.ariaSort}>
                    <button type="button" className="th-sort-btn" onClick={() => handleSort(col.column)}>
                      {col.label} <span className="th-sort-icon" aria-hidden="true">{ind.glyph}</span>
                    </button>
                  </th>
                );
              })}
              <th>Akcje</th>
            </tr>
          </thead>
          <tbody>
            {servicesState.loading ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <Icon name="spa" className="empty-icon" />
                  <p className="empty-text">Ładowanie usług...</p>
                </td>
              </tr>
            ) : servicesState.error ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                    Błąd ładowania usług: {servicesState.error.message}
                  </p>
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <Icon name="search_off" className="empty-icon" />
                  <p className="empty-text">Nie znaleziono usług</p>
                </td>
              </tr>
            ) : (
              sorted.map((service) => {
                const recentChange = service.last_price_change_date && Date.now() - new Date(service.last_price_change_date).getTime() < 90 * 86400000;
                return (
                  <tr key={service.id} className="row-clickable" onClick={(e) => handleRowClick(service, e)}>
                    <td>
                      <div>
                        <div style={{ fontWeight: 500, color: 'var(--color-ink)' }}>{service.name}</div>
                        {service.description && <div style={{ fontSize: '0.75rem', color: 'var(--color-ink-subtle)', marginTop: '0.25rem' }}>{service.description}</div>}
                      </div>
                    </td>
                    <td>
                      <span className={`type-badge ${service.service_type}`}>{service.service_type === 'addon' ? 'Dodatkowa' : 'Główna'}</span>
                    </td>
                    <td>{service.category}</td>
                    <td>{service.formatted_duration}</td>
                    <td style={{ fontWeight: 500 }}>
                      {service.formatted_price}
                      {recentChange && service.last_price_change_date && (
                        <span className="price-trend-chip" title={`Cenę zmieniono ${daysSince(service.last_price_change_date)} dni temu`}>
                          ↕
                        </span>
                      )}
                    </td>
                    <td>
                      <span className={`status-badge ${service.is_active ? 'active' : 'inactive'}`}>{service.is_active ? 'Aktywna' : 'Nieaktywna'}</span>
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <div className="action-icons">
                        <Link to={`/uslugi/${service.id}`} className="action-icon-btn" title="Zobacz" aria-label="Zobacz">
                          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        </Link>
                        {canWrite && (
                          <Link to={`/uslugi/${service.id}/edytuj`} className="action-icon-btn" title="Edytuj" aria-label="Edytuj">
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
