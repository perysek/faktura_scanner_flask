import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './FakturyListPage.css';
import { useApiData } from '../../lib/useApiData';
import { invoicesApi } from '../../lib/api/invoices';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { formatDate } from '../../lib/format';
import { SellerSyncModal } from './SellerSyncModal';
import type { Invoice } from '../../types/invoice';

type SortColumn = 'invoice_number' | 'seller_name' | 'invoice_date' | 'amount';
type SortDir = 'asc' | 'desc';
type StatusFilter = 'all' | 'paid' | 'unpaid' | 'overdue';

/** Ported 1:1 from list_refined.html's `isOverdueByDate()` — local-midnight
 * comparison, not a UTC one (an invoice due "today" isn't overdue yet). */
function isOverdueByDate(dateString: string | null): boolean {
  if (!dateString) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(dateString);
  due.setHours(0, 0, 0, 0);
  return due < today;
}

function isOverdue(invoice: Invoice): boolean {
  return invoice.status !== 'Opłacona' && isOverdueByDate(invoice.payment_due_date);
}

/** `getStatusInfo()` ported 1:1 — "Przeterminowana" is derived (status stays
 * `Nieopłacona` in the DB; only the due date decides the badge shown). */
function statusInfo(invoice: Invoice): { cls: string; text: string } {
  if (invoice.status === 'Opłacona') return { cls: 'status-paid', text: 'Opłacona' };
  if (isOverdue(invoice)) return { cls: 'status-overdue', text: 'Przeterminowana' };
  return { cls: 'status-unpaid', text: 'Nieopłacona' };
}

function sortValue(inv: Invoice, column: SortColumn): string | number {
  if (column === 'amount') return inv.amount ?? 0;
  if (column === 'invoice_date') return inv.invoice_date ? new Date(inv.invoice_date).getTime() : 0;
  return String(inv[column] ?? '').toLowerCase();
}

function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return '—';
  return amount.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Faktury — lista. Piąty moduł Fazy 2 (module-inventory.md), największy dotąd
 * pod względem złożoności backendu. Ten build celowo obejmuje TYLKO
 * list+CRUD+konflikt-sprzedawcy+sync-sprzedawców+eksport — podgląd PDF w
 * bocznym panelu (`togglePreviewPanel`/`openPreviewPanel` w oryginale),
 * `/import-dokumentow` (OCR upload+SSE staging), `/historia` i
 * `/ustawienia/email` świadomie odłożone jako osobny, następny przebieg
 * (patrz implementation-log.md, decyzja o zakresie) — to zupełnie inny rodzaj
 * UI (streaming progress, wieloplikowy staging), nie wariant tego samego
 * wzorca list+form co reszta Fazy 2. Kliknięcie w PDF otwiera plik w nowej
 * karcie (`/api/pdf/<id>`) zamiast bocznego panelu — realny podgląd
 * zachowany, tylko bez dedykowanego UI panelu.
 */
export function FakturyListPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const canWrite = auth.hasModuleWrite('invoices');

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<{ column: SortColumn | null; dir: SortDir }>({ column: null, dir: 'asc' });
  const [exportOpen, setExportOpen] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  const invoicesState = useApiData(() => invoicesApi.list(), []);
  const invoices = useMemo(() => invoicesState.data?.invoices ?? [], [invoicesState.data]);

  useEffect(() => {
    function onClickOutside(event: globalThis.MouseEvent) {
      if (exportRef.current && !exportRef.current.contains(event.target as Node)) setExportOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const filterCounts = useMemo(
    () => ({
      all: invoices.length,
      paid: invoices.filter((i) => i.status === 'Opłacona').length,
      unpaid: invoices.filter((i) => i.status !== 'Opłacona' && !isOverdue(i)).length,
      overdue: invoices.filter((i) => isOverdue(i)).length,
    }),
    [invoices],
  );

  const filtered = useMemo(() => {
    let list = invoices;
    if (statusFilter === 'paid') list = list.filter((i) => i.status === 'Opłacona');
    else if (statusFilter === 'unpaid') list = list.filter((i) => i.status !== 'Opłacona' && !isOverdue(i));
    else if (statusFilter === 'overdue') list = list.filter((i) => isOverdue(i));

    const q = searchQuery.toLowerCase().trim();
    if (q) {
      list = list.filter((i) => [i.invoice_number, i.seller_name, i.seller_nip].filter(Boolean).join(' ').toLowerCase().includes(q));
    }
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
  }, [invoices, statusFilter, searchQuery, sort]);

  const filteredTotal = useMemo(() => filtered.reduce((sum, i) => sum + (i.amount || 0), 0), [filtered]);

  function handleSort(column: SortColumn) {
    setSort((current) => (current.column === column ? { column, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { column, dir: 'asc' }));
  }

  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return { ariaSort: 'none' as const, glyph: '↕', active: false };
    const ariaSort = sort.dir === 'asc' ? ('ascending' as const) : ('descending' as const);
    return { ariaSort, glyph: sort.dir === 'asc' ? '↑' : '↓', active: true };
  }

  async function handleStatusToggle(invoice: Invoice, event: MouseEvent) {
    event.stopPropagation();
    // Same toggle rule as the original's handleStatusClick(): paid → unpaid,
    // anything else (unpaid or overdue-derived) → paid. "Przeterminowana" is
    // never a real DB value to toggle FROM/TO — it's derived from the due
    // date whenever status stays "Nieopłacona" (see `statusInfo()` above).
    const newStatus = invoice.status === 'Opłacona' ? 'Nieopłacona' : 'Opłacona';
    try {
      await invoicesApi.update(invoice.id, { status: newStatus });
      invoicesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zmienić statusu faktury');
    }
  }

  async function handleDelete(invoice: Invoice) {
    const ok = await confirm({
      title: 'Kasujemy fakturę?',
      message: `Skasować fakturę ${invoice.invoice_number || invoice.id} na zawsze? Księgowa może mieć pytania.`,
      confirmText: 'Kasuj',
      cancelText: 'Jednak nie',
    });
    if (!ok) return;
    try {
      await invoicesApi.delete(invoice.id);
      toast.success('Faktura usunięta');
      invoicesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania faktury');
    }
  }

  function handleRowClick(invoice: Invoice, event: MouseEvent<HTMLTableRowElement>) {
    if ((event.target as HTMLElement).closest('.row-actions') || (event.target as HTMLElement).closest('.clickable-status')) return;
    navigate(`/faktury/${invoice.id}/edytuj`);
  }

  const columns: Array<{ column: SortColumn; label: string }> = [
    { column: 'invoice_number', label: 'Nr faktury' },
    { column: 'seller_name', label: 'Sprzedawca' },
    { column: 'invoice_date', label: 'Data wyst.' },
    { column: 'amount', label: 'Kwota' },
  ];

  const pills: Array<{ key: StatusFilter; label: string }> = [
    { key: 'all', label: 'Wszystkie' },
    { key: 'paid', label: 'Opłacone' },
    { key: 'unpaid', label: 'Nieopłacone' },
    { key: 'overdue', label: 'Przeterminowane' },
  ];

  return (
    <div className="refined-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <h1 className="page-title">Wykaz faktur</h1>
        <div className="page-header-actions">
          <div className="dropdown" ref={exportRef}>
            <Button variant="secondary" icon="download" onClick={() => setExportOpen((v) => !v)}>
              Eksport
            </Button>
            {exportOpen && (
              <div className="dropdown-menu">
                <a className="dropdown-item" href={invoicesApi.exportUrl('excel')} onClick={() => setExportOpen(false)}>
                  <Icon name="insert_drive_file" /> Eksport do Excel
                </a>
                <a className="dropdown-item" href={invoicesApi.exportUrl('csv')} onClick={() => setExportOpen(false)}>
                  <Icon name="insert_drive_file" /> Eksport do CSV
                </a>
              </div>
            )}
          </div>
          <Button variant="secondary" icon="sync" onClick={() => setSyncOpen(true)} title="Sprawdź powiązania faktur ze sprzedawcami">
            Sync sprzedawców
          </Button>
          {canWrite && (
            <ButtonLink variant="primary" icon="add" to="/faktury/nowa">
              Nowa faktura
            </ButtonLink>
          )}
        </div>
      </header>

      <div className="filter-pills">
        {pills.map((p) => (
          <button key={p.key} type="button" className={`filter-pill${statusFilter === p.key ? ' active' : ''}`} onClick={() => setStatusFilter(p.key)}>
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
            placeholder="Szukaj po numerze, sprzedawcy lub NIP..."
            autoComplete="off"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="table-container">
        <table className="refined-table stack-cards">
          <thead>
            <tr>
              {columns.map((col) => {
                const ind = sortIndicator(col.column);
                return (
                  <th key={col.column} className={`th-sortable${ind.active ? ' sort-active' : ''}${col.column === 'amount' ? ' col-amount' : ''}`} aria-sort={ind.ariaSort}>
                    <button type="button" className="th-sort-btn" onClick={() => handleSort(col.column)}>
                      {col.label} <span className="th-sort-icon" aria-hidden="true">{ind.glyph}</span>
                    </button>
                  </th>
                );
              })}
              <th>NIP</th>
              <th>Termin</th>
              <th>Status</th>
              <th>
                <span className="sr-only">Akcje</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {invoicesState.loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 8 }).map((_, c) => (
                    <td key={c}>
                      <div className="skeleton" style={{ height: '1rem', borderRadius: '2px' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : invoicesState.error ? (
              <tr>
                <td colSpan={8} className="empty-state">
                  <p className="empty-text" style={{ color: 'var(--color-error)' }}>
                    Błąd ładowania faktur: {invoicesState.error.message}
                  </p>
                  <Button variant="secondary" style={{ marginTop: '0.75rem' }} onClick={() => invoicesState.reload()}>
                    Spróbuj ponownie
                  </Button>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-state">
                  <Icon name="search_off" className="empty-icon" />
                  <h3 className="empty-title">Brak faktur</h3>
                  <p className="empty-text">Dodaj fakturę ręcznie lub zaimportuj dokumenty.</p>
                  {canWrite && (
                    <ButtonLink variant="primary" to="/faktury/nowa">
                      Dodaj fakturę
                    </ButtonLink>
                  )}
                </td>
              </tr>
            ) : (
              filtered.map((invoice) => {
                const info = statusInfo(invoice);
                return (
                  <tr key={invoice.id} className="row-clickable" onClick={(e) => handleRowClick(invoice, e)}>
                    <td className="cell-name" data-label="Nr faktury">
                      <span className="invoice-number">{invoice.invoice_number || '—'}</span>
                    </td>
                    <td data-label="Sprzedawca">
                      <span className="seller-name" title={invoice.seller_name ?? ''}>
                        {invoice.seller_name || '—'}
                      </span>
                    </td>
                    <td data-label="Data wyst.">
                      <span className="date-value">{formatDate(invoice.invoice_date)}</span>
                    </td>
                    <td className="col-amount" data-label="Kwota">
                      <span className="amount-value">{formatAmount(invoice.amount)}</span>
                      <span className="currency-code">{!invoice.currency || invoice.currency === 'PLN' ? 'zł' : invoice.currency}</span>
                    </td>
                    <td data-label="NIP">
                      <span className="nip-number">{invoice.seller_nip || '—'}</span>
                    </td>
                    <td data-label="Termin">
                      <span className="date-value">{formatDate(invoice.payment_due_date)}</span>
                    </td>
                    <td data-label="Status">
                      <span className={`status-badge clickable-status ${info.cls}`} title="Kliknij aby zmienić status" onClick={(e) => handleStatusToggle(invoice, e)}>
                        {info.text}
                      </span>
                    </td>
                    <td className="cell-actions">
                      <div className="row-actions">
                        {invoice.pdf_path && (
                          <a href={invoicesApi.pdfUrl(invoice.id)} target="_blank" rel="noreferrer" className="action-btn" title="Podgląd dokumentu" aria-label="Podgląd dokumentu" onClick={(e) => e.stopPropagation()}>
                            <Icon name="visibility" />
                          </a>
                        )}
                        <Link to={`/faktury/${invoice.id}/edytuj`} className="action-btn" title="Edytuj" aria-label="Edytuj" onClick={(e) => e.stopPropagation()}>
                          <Icon name="edit" />
                        </Link>
                        {canWrite && (
                          <button className="action-btn delete" title="Usuń" aria-label="Usuń" onClick={(e) => { e.stopPropagation(); handleDelete(invoice); }}>
                            <Icon name="delete" />
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
            Wyświetlono <span className="pagination-count">{filtered.length}</span> z <span className="pagination-count">{invoices.length}</span> faktur
          </span>
          <span>
            Suma: <span className="pagination-count">{filteredTotal.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} zł</span>
          </span>
        </div>
      </div>

      <SellerSyncModal isOpen={syncOpen} onClose={() => setSyncOpen(false)} onApplied={() => invoicesState.reload()} />
    </div>
  );
}
