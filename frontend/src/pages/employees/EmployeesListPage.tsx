import { useEffect, useMemo, useState } from 'react';
import type { MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './EmployeesListPage.css';
import { useApiData } from '../../lib/useApiData';
import { employeesApi } from '../../lib/api/employees';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Icon } from '../../lib/icons/Icon';
import type { BalanceSummaryEntry, EmployeeListRow } from '../../types/employee';

type SortColumn = 'full_name' | 'position' | 'status' | 'avg_satisfaction' | 'balance';
type SortDir = 'asc' | 'desc';

const SESSION_KEY = 'filterState:employees';

function statusBadge(emp: EmployeeListRow) {
  if (!emp.is_active) return { cls: 'inactive', label: 'Nieaktywny' };
  if (emp.employment_status === 'on_leave') return { cls: 'on-leave', label: 'Na urlopie' };
  if (emp.employment_status === 'terminated') return { cls: 'terminated', label: 'Zwolniony' };
  return { cls: 'active', label: 'Aktywny' };
}

function sortValue(e: EmployeeListRow, column: SortColumn, balances: Record<string, BalanceSummaryEntry>): string | number {
  if (column === 'status') return (e.is_active ? '0_' : '1_') + (e.employment_status || 'active');
  if (column === 'balance') {
    const b = balances[String(e.id)];
    if (!b || b.status === 'unlimited') return -1;
    return b.used ?? 0;
  }
  if (column === 'avg_satisfaction') return e.avg_satisfaction ?? 0;
  return String(e[column as 'full_name' | 'position'] ?? '').toLowerCase();
}

/**
 * Pracownicy — lista + CRUD (największy dotąd moduł). Ported 1:1 z
 * templates/employees/list.html: search klient-side (dane już w pamięci z
 * `active_only=false`), stanowisko filtrowane serwerowo, bilans urlopu
 * dociągany osobnym fetchem (`/api/absence-balances/summary`) i mergowany
 * po stronie klienta — dokładnie jak oryginał, nie zagnieżdżony w
 * `/api/employees`. Trwałe usunięcie (superuser-only) — osobny modal
 * ostrzegający o kaskadowym skasowaniu konta użytkownika.
 */
export function EmployeesListPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const isSuperuser = auth.user?.role === 'superuser';

  const initial = useMemo(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as { search?: string; position?: string; status?: string }) : {};
    } catch {
      return {};
    }
  }, []);

  const [search, setSearch] = useState(initial.search ?? '');
  const [positionFilter, setPositionFilter] = useState(initial.position ?? '');
  const [statusFilter, setStatusFilter] = useState(initial.status ?? '');
  const [sort, setSort] = useState<{ column: SortColumn | null; dir: SortDir }>({ column: null, dir: 'asc' });
  const [hardDeleteTarget, setHardDeleteTarget] = useState<{ id: number; name: string; hasUser: boolean } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [bulkUpdating, setBulkUpdating] = useState(false);

  useEffect(() => {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ search, position: positionFilter, status: statusFilter }));
    } catch {
      /* ignore */
    }
  }, [search, positionFilter, statusFilter]);

  const employeesState = useApiData(() => employeesApi.list({ position: positionFilter, activeOnly: false }), [positionFilter]);
  const positionsState = useApiData(() => employeesApi.positions(), []);
  const statsState = useApiData(() => employeesApi.statistics(), []);
  const balancesState = useApiData(() => employeesApi.getBalanceSummary(), [employeesState.data]);
  const balances = useMemo(() => balancesState.data ?? {}, [balancesState.data]);

  const employees = useMemo(() => employeesState.data ?? [], [employeesState.data]);

  const filtered = useMemo(() => {
    let list = employees;
    if (statusFilter === 'active') list = list.filter((e) => e.is_active);
    else if (statusFilter === 'inactive') list = list.filter((e) => !e.is_active);
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter((e) => [e.full_name, e.first_name, e.last_name, e.phone, e.email, e.position].filter(Boolean).join(' ').toLowerCase().includes(q));
    }
    if (sort.column) {
      const { column, dir } = sort;
      list = [...list].sort((a, b) => {
        const av = sortValue(a, column, balances);
        const bv = sortValue(b, column, balances);
        const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : av < bv ? -1 : av > bv ? 1 : 0;
        return dir === 'asc' ? cmp : -cmp;
      });
    }
    return list;
  }, [employees, statusFilter, search, sort, balances]);

  function handleSort(column: SortColumn) {
    setSort((current) => (current.column === column ? { column, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { column, dir: 'asc' }));
  }
  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return { ariaSort: 'none' as const, glyph: '↕', active: false };
    const ariaSort = sort.dir === 'asc' ? ('ascending' as const) : ('descending' as const);
    return { ariaSort, glyph: sort.dir === 'asc' ? '↑' : '↓', active: true };
  }

  // Row-click mirrors "Zobacz" (view) — DESIGN.md §20.
  function handleRowClick(empId: number, event: MouseEvent<HTMLTableRowElement>) {
    if ((event.target as HTMLElement).closest('.action-icons')) return;
    navigate(`/pracownicy/${empId}`);
  }

  async function handleBulkUpdate() {
    setBulkUpdating(true);
    try {
      const result = await employeesApi.bulkUpdateServices();
      toast.success(`✓ Zaktualizowano usługi dla ${result.updated_count} z ${result.total_count} pracowników`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji usług');
    } finally {
      setBulkUpdating(false);
    }
  }

  async function confirmHardDelete() {
    if (!hardDeleteTarget) return;
    setDeleting(true);
    try {
      const result = await employeesApi.hardDelete(hardDeleteTarget.id);
      toast.success(result.message);
      setHardDeleteTarget(null);
      employeesState.reload();
      statsState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się usunąć pracownika');
    } finally {
      setDeleting(false);
    }
  }

  function renderBalanceBadge(empId: number) {
    const b = balances[String(empId)];
    if (!b) return <span className="dim">—</span>;
    if (b.status === 'unlimited') return <span className="dim">∞</span>;
    const cls = b.status === 'exceeded' ? 'balance-exceeded' : b.status === 'warning' ? 'balance-warning' : 'balance-ok';
    const unitL = b.unit === 'hours' ? 'h' : 'd';
    return (
      <span className={cls}>
        {Math.round(b.used)}/{b.limit}
        {unitL}
      </span>
    );
  }

  function renderRating(avg: number | null, count: number) {
    if (avg == null) return <span className="dim">—</span>;
    const cls = avg >= 4.5 ? 'rating-excellent' : avg >= 3.5 ? 'rating-good' : avg >= 2.5 ? 'rating-fair' : 'rating-poor';
    return (
      <>
        <span className={cls}>★ {avg.toFixed(1)}</span> <span className="rating-count">({count})</span>
      </>
    );
  }

  const columns: Array<{ column: SortColumn; label: string }> = [
    { column: 'full_name', label: 'Imię i nazwisko' },
    { column: 'position', label: 'Stanowisko' },
    { column: 'status', label: 'Status' },
    { column: 'avg_satisfaction', label: 'Ocena klientów' },
    { column: 'balance', label: 'Bilans urlopu' },
  ];

  return (
    <div className="refined-page employees-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Pracownicy</h1>
          <p className="page-subtitle">Zarządzanie personelem salonu</p>
        </div>
        <div className="page-header-actions">
          <Button variant="secondary" icon="sync" isLoading={bulkUpdating} loadingText="Aktualizowanie…" onClick={handleBulkUpdate}>
            Aktualizuj preferencje
          </Button>
          {auth.hasModuleWrite('employees') && (
            <ButtonLink variant="primary" icon="add" to="/pracownicy/nowy">
              Dodaj pracownika
            </ButtonLink>
          )}
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div>
            <p className="stat-label">Wszyscy pracownicy</p>
            <p className="stat-value">{statsState.data?.total_employees ?? '-'}</p>
          </div>
          <div className="stat-icon blue">
            <Icon name="badge" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Aktywni</p>
            <p className="stat-value">{statsState.data?.active_employees ?? '-'}</p>
          </div>
          <div className="stat-icon green">
            <Icon name="check_circle" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Śr. prowizja</p>
            <p className="stat-value purple">{statsState.data?.avg_salary ? `${statsState.data.avg_salary.toFixed(0)} zł` : '—'}</p>
          </div>
          <div className="stat-icon purple">
            <Icon name="percent" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Stanowiska</p>
            <p className="stat-value orange">{positionsState.data?.length ?? 0}</p>
          </div>
          <div className="stat-icon orange">
            <Icon name="work" />
          </div>
        </div>
      </div>

      <div className="search-card">
        <div className="search-wrapper">
          <div className="search-input-wrap">
            <input type="text" className="refined-input" placeholder="Szukaj po imieniu, nazwisku, telefonie lub emailu..." value={search} onChange={(e) => setSearch(e.target.value)} />
            {search && (
              <button type="button" className="search-clear-btn" aria-label="Wyczyść wyszukiwanie" onClick={() => setSearch('')}>
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          <select className="form-select" aria-label="Filtruj według stanowiska" style={{ minWidth: '180px' }} value={positionFilter} onChange={(e) => setPositionFilter(e.target.value)}>
            <option value="">Wszystkie stanowiska</option>
            {(positionsState.data ?? []).map((pos) => (
              <option key={pos} value={pos}>
                {pos}
              </option>
            ))}
          </select>
          <select className="form-select" aria-label="Filtruj według statusu" style={{ minWidth: '150px' }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Wszystkie statusy</option>
            <option value="active">Aktywni</option>
            <option value="inactive">Nieaktywni</option>
          </select>
        </div>
      </div>

      <div className="table-container stack-cards-wrap">
        <table className="refined-table stack-cards">
          <thead>
            <tr>
              {columns.map((col) => {
                const ind = sortIndicator(col.column);
                return (
                  <th key={col.column} className={`th-sortable${ind.active ? ' sort-active' : ''}`} aria-sort={ind.ariaSort} style={col.column !== 'full_name' && col.column !== 'position' ? { textAlign: 'center' } : undefined}>
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
            {employeesState.loading ? (
              <tr>
                <td colSpan={6} className="empty-state">
                  <p className="empty-text">Ładowanie pracowników...</p>
                </td>
              </tr>
            ) : employeesState.error ? (
              <tr>
                <td colSpan={6} className="empty-state">
                  <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                    Błąd ładowania: {employeesState.error.message}
                  </p>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-state">
                  <Icon name="search_off" className="empty-icon" />
                  <p className="empty-text">Nie znaleziono pracowników</p>
                </td>
              </tr>
            ) : (
              filtered.map((emp) => {
                const badge = statusBadge(emp);
                const initials = (emp.first_name.charAt(0) + emp.last_name.charAt(0)).toUpperCase();
                return (
                  <tr key={emp.id} className="row-clickable" onClick={(e) => handleRowClick(emp.id, e)}>
                    <td className="cell-name">
                      <div className="employee-info">
                        <div className="employee-avatar">{initials}</div>
                        <div>
                          <div className="employee-name">{emp.full_name}</div>
                          {emp.email && <div className="employee-email">{emp.email}</div>}
                        </div>
                      </div>
                    </td>
                    <td data-label="Stanowisko">{emp.position || <span className="dim">—</span>}</td>
                    <td data-label="Status" style={{ textAlign: 'center' }}>
                      <span className={`status-badge ${badge.cls}`}>{badge.label}</span>
                    </td>
                    <td data-label="Ocena klientów" style={{ textAlign: 'center' }}>
                      {renderRating(emp.avg_satisfaction, emp.rated_count)}
                    </td>
                    <td data-label="Bilans urlopu" style={{ textAlign: 'center' }}>
                      {renderBalanceBadge(emp.id)}
                    </td>
                    <td className="cell-actions" style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <div className="action-icons">
                        {isSuperuser && (
                          <button type="button" className="action-icon-btn danger-reveal" title="Usuń trwale" aria-label="Usuń trwale" onClick={() => setHardDeleteTarget({ id: emp.id, name: emp.full_name, hasUser: emp.user_id != null })}>
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        )}
                        <Link to={`/pracownicy/${emp.id}`} className="action-icon-btn" title="Zobacz" aria-label="Zobacz">
                          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        </Link>
                        <Link to={`/pracownicy/${emp.id}/edytuj`} className="action-icon-btn" title="Edytuj" aria-label="Edytuj">
                          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {hardDeleteTarget && (
        <Modal
          isOpen
          onClose={() => setHardDeleteTarget(null)}
          title="Trwałe usunięcie pracownika"
          footer={
            <>
              <Button variant="secondary" onClick={() => setHardDeleteTarget(null)}>
                Anuluj
              </Button>
              <Button variant="danger" isLoading={deleting} loadingText="Usuwanie…" onClick={confirmHardDelete}>
                Usuń trwale
              </Button>
            </>
          }
        >
          <p>
            Trwale usunąć pracownika <strong>{hardDeleteTarget.name}</strong>? Tej operacji <strong>nie można cofnąć</strong>.
          </p>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', marginTop: '0.75rem' }}>Zostaną usunięte:</p>
          <ul style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', margin: '0.25rem 0 0 1.1rem' }}>
            <li>rekord pracownika oraz przypisane usługi i dostępność,</li>
            <li>nieobecności i bilanse urlopowe (wraz z historią korekt).</li>
          </ul>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', marginTop: '0.625rem' }}>
            Wizyty i wpisy przychodu <strong>pozostaną nienaruszone</strong> — jeśli istnieją, usunięcie zostanie zablokowane.
          </p>
          {hardDeleteTarget.hasUser && (
            <div className="hard-delete-user-warning">
              <Icon name="person_off" />
              <span>
                Ten pracownik ma <strong>przypisane konto użytkownika</strong> — zostanie ono również trwale usunięte wraz z dostępem do aplikacji.
              </span>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
