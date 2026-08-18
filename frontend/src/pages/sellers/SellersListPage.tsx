import { useMemo, useState } from 'react';
import type { MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './SellersListPage.css';
import { useApiData } from '../../lib/useApiData';
import { sellersApi } from '../../lib/api/sellers';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { formatCurrency } from '../../lib/format';
import { SellerPasswordsPanel } from './SellerPasswordsPanel';
import { SellerSyncResults } from './SellerSyncResults';
import type { Seller, SyncResult } from '../../types/seller';

type SortColumn = 'seller_nip' | 'seller_name' | 'invoices' | 'total_paid' | 'total_unpaid' | 'last_updated';
type SortDir = 'asc' | 'desc';

function sortValue(s: Seller, column: SortColumn): string | number {
  if (column === 'invoices') return s.actual_invoice_count || s.invoice_count || 0;
  if (column === 'last_updated') return s.last_updated ? new Date(s.last_updated).getTime() : 0;
  if (column === 'total_paid' || column === 'total_unpaid') return s[column] ?? 0;
  return String(s[column] ?? '').toLowerCase();
}

function formatDateShort(dateString: string | null): string {
  if (!dateString) return '—';
  const d = new Date(dateString);
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(-2)}`;
}

/**
 * Sprzedawcy — lista + CRUD (pierwsza z trzech pod-funkcji modułu, patrz
 * module-inventory.md korekta 2026-08-17). Ported 1:1 from
 * templates/sellers/list_refined.html: search fetches once, filters/sorts
 * client-side (the original never actually uses the server's `search` query
 * param from this page — matched exactly, not "improved").
 */
export function SellersListPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const canWrite = auth.hasModuleWrite('invoices');

  const [searchQuery, setSearchQuery] = useState('');
  const [sort, setSort] = useState<{ column: SortColumn | null; dir: SortDir }>({ column: null, dir: 'asc' });
  const [passwordsPanelOpen, setPasswordsPanelOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);

  const sellersState = useApiData(() => sellersApi.list(), []);
  // Stable empty-array reference (not `?? []` inline) so the two useMemo's
  // below don't see a "new" dependency on every render while data is null.
  const sellers = useMemo(() => sellersState.data?.sellers ?? [], [sellersState.data]);
  const globalStats = sellersState.data?.global_stats ?? null;

  const stats = useMemo(() => {
    const total = sellers.length;
    if (globalStats) {
      return { total, invoices: globalStats.total_invoices, paid: globalStats.total_paid, unpaid: globalStats.total_unpaid };
    }
    return {
      total,
      invoices: sellers.reduce((sum, s) => sum + (s.actual_invoice_count || s.invoice_count || 0), 0),
      paid: sellers.reduce((sum, s) => sum + (s.total_paid || 0), 0),
      unpaid: sellers.reduce((sum, s) => sum + (s.total_unpaid || 0), 0),
    };
  }, [sellers, globalStats]);

  const filtered = useMemo(() => {
    let list = sellers;
    const q = searchQuery.toLowerCase().trim();
    if (q) {
      list = list.filter((s) => [s.seller_nip, s.seller_name, s.address].filter(Boolean).join(' ').toLowerCase().includes(q));
    }
    if (sort.column) {
      const { column, dir } = sort;
      list = [...list].sort((a, b) => {
        const av = sortValue(a, column);
        const bv = sortValue(b, column);
        let cmp: number;
        if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv;
        else cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return dir === 'asc' ? cmp : -cmp;
      });
    }
    return list;
  }, [sellers, searchQuery, sort]);

  function handleSort(column: SortColumn) {
    setSort((current) => (current.column === column ? { column, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { column, dir: 'asc' }));
  }

  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return { ariaSort: 'none' as const, glyph: '↕', active: false };
    const ariaSort = sort.dir === 'asc' ? ('ascending' as const) : ('descending' as const);
    return { ariaSort, glyph: sort.dir === 'asc' ? '↑' : '↓', active: true };
  }

  async function handleDelete(seller: Seller) {
    const ok = await confirm({
      title: 'Usuń sprzedawcę',
      message: `Czy na pewno chcesz usunąć sprzedawcę ${seller.seller_name}? Wszystkie jego faktury zostaną usunięte razem z nim.`,
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      const result = await sellersApi.delete(seller.id);
      toast.success(result.message);
      sellersState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania sprzedawcy');
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await sellersApi.sync();
      setSyncResult(result);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd synchronizacji danych');
    } finally {
      setSyncing(false);
    }
  }

  function closeSyncResults() {
    setSyncResult(null);
    sellersState.reload();
  }

  // No detail page for Sprzedawcy — row-click mirrors "Edytuj" (DESIGN.md §20).
  function handleRowClick(seller: Seller, event: MouseEvent<HTMLTableRowElement>) {
    if ((event.target as HTMLElement).closest('.row-actions')) return;
    navigate(`/sprzedawcy/${seller.id}/edytuj`);
  }

  if (syncResult) {
    return <SellerSyncResults result={syncResult} onClose={closeSyncResults} onChanged={setSyncResult} />;
  }

  const columns: Array<{ column: SortColumn; label: string; align?: 'center' | 'right' }> = [
    { column: 'seller_nip', label: 'NIP' },
    { column: 'seller_name', label: 'Nazwa' },
    { column: 'invoices', label: 'Faktury', align: 'center' },
    { column: 'total_paid', label: 'Opłacone', align: 'right' },
    { column: 'total_unpaid', label: 'Nieopłacone', align: 'right' },
    { column: 'last_updated', label: 'Aktualizacja' },
  ];

  return (
    <div className="refined-page sellers-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <h1 className="page-title">Sprzedawcy</h1>
        <div className="header-actions">
          {/* No "lock" glyph in the shared icon set (paths.ts, ~70 entries) —
              raw inline SVG ported 1:1 from the original, same pattern as
              ClientsListPage's row-action icons (Faza 1). */}
          <button type="button" className="refined-btn-secondary btn-press" onClick={() => setPasswordsPanelOpen(true)}>
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Hasła PDF
          </button>
          <Button variant="secondary" icon="sync" isLoading={syncing} loadingText="Synchronizacja…" onClick={handleSync}>
            Synchronizuj
          </Button>
          {canWrite && (
            <ButtonLink variant="primary" icon="add" to="/sprzedawcy/nowy">
              Nowy sprzedawca
            </ButtonLink>
          )}
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div>
            <p className="stat-label">Sprzedawcy</p>
            <p className="stat-value">{stats.total}</p>
          </div>
          <div className="stat-icon blue">
            <Icon name="people" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Faktury</p>
            <p className="stat-value">{stats.invoices}</p>
          </div>
          <div className="stat-icon purple">
            <Icon name="insert_drive_file" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Opłacone</p>
            <p className="stat-value green">{formatCurrency(stats.paid)}</p>
          </div>
          <div className="stat-icon green">
            <Icon name="payments" />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <p className="stat-label">Nieopłacone</p>
            <p className="stat-value orange">{formatCurrency(stats.unpaid)}</p>
          </div>
          <div className="stat-icon orange">
            <Icon name="warning_amber" />
          </div>
        </div>
      </div>

      <div className="search-bar">
        <div className="search-wrapper">
          <svg className="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input type="text" className="search-input" placeholder="Szukaj po NIP lub nazwie..." autoComplete="off" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
        </div>
      </div>

      <div className="table-container">
        <table className="refined-table stack-cards">
          <thead>
            <tr>
              {columns.map((col) => {
                const ind = sortIndicator(col.column);
                return (
                  <th key={col.column} className={`th-sortable${ind.active ? ' sort-active' : ''}`} aria-sort={ind.ariaSort} style={col.align ? { textAlign: col.align } : undefined}>
                    <button type="button" className="th-sort-btn" onClick={() => handleSort(col.column)}>
                      {col.label} <span className="th-sort-icon" aria-hidden="true">{ind.glyph}</span>
                    </button>
                  </th>
                );
              })}
              <th>
                <span className="sr-only">Akcje</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sellersState.loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 7 }).map((_, c) => (
                    <td key={c}>
                      <div className="skeleton" style={{ height: '1rem', borderRadius: '2px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : sellersState.error ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                    Błąd ładowania sprzedawców: {sellersState.error.message}
                  </p>
                  <Button variant="secondary" style={{ marginTop: '0.75rem' }} onClick={() => sellersState.reload()}>
                    Spróbuj ponownie
                  </Button>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <Icon name="search_off" className="empty-icon" />
                  <h3 className="empty-title">Brak sprzedawców</h3>
                  <p className="empty-text">Dodaj sprzedawców ręcznie lub zsynchronizuj dane z faktur.</p>
                  <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', marginTop: '0.75rem' }}>
                    <ButtonLink variant="primary" to="/sprzedawcy/nowy">
                      Dodaj sprzedawcę
                    </ButtonLink>
                    <Button variant="secondary" onClick={handleSync}>
                      Synchronizuj
                    </Button>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((seller) => {
                const invoiceCount = seller.actual_invoice_count || seller.invoice_count || 0;
                return (
                  <tr key={seller.id} className="row-clickable" onClick={(e) => handleRowClick(seller, e)}>
                    <td data-label="NIP">
                      <span className="nip-number">{seller.seller_nip || '—'}</span>
                    </td>
                    <td className="cell-name" data-label="Nazwa">
                      <span className="seller-name" title={seller.seller_name}>
                        {seller.seller_name || '—'}
                      </span>
                    </td>
                    <td data-label="Faktury" style={{ textAlign: 'center' }}>
                      <span className="invoice-count">{invoiceCount}</span>
                    </td>
                    <td data-label="Opłacone" style={{ textAlign: 'right' }}>
                      <span className="amount-paid">{formatCurrency(seller.total_paid || 0, 'PLN')}</span>
                    </td>
                    <td data-label="Nieopłacone" style={{ textAlign: 'right' }}>
                      <span className="amount-unpaid">{formatCurrency(seller.total_unpaid || 0, 'PLN')}</span>
                    </td>
                    <td data-label="Aktualizacja">
                      <span className="date-value">{formatDateShort(seller.last_updated)}</span>
                    </td>
                    <td className="cell-actions">
                      <div className="row-actions">
                        <Link to={`/sprzedawcy/${seller.id}/edytuj`} className="action-btn" title="Edytuj" aria-label="Edytuj">
                          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </Link>
                        {canWrite && (
                          <button className="action-btn delete" onClick={() => handleDelete(seller)} title="Usuń" aria-label="Usuń">
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
        <div className="pagination-bar">
          <span>
            Wyświetlono <span className="pagination-count">{filtered.length}</span> z <span className="pagination-count">{sellers.length}</span> sprzedawców
          </span>
        </div>
      </div>

      <SellerPasswordsPanel isOpen={passwordsPanelOpen} onClose={() => setPasswordsPanelOpen(false)} sellers={sellers} />
    </div>
  );
}
