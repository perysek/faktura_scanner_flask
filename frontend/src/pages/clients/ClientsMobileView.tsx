import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { NotesDigest } from '../../components/visitNotes/NotesDigest';
import { isVipClient } from '../../components/clients/TrendSparkline';
import { Icon } from '../../lib/icons/Icon';
import { formatDate, formatNextVisitLine1, formatPhone } from '../../lib/format';
import { DEFAULT_SORT_DIR, clientInitials, clientRingStyle } from './clientsListShared';
import type { FilterKey, SortField, SortState } from './clientsListShared';
import type { Client } from '../../types/client';

const SORT_OPTIONS: Array<{ field: SortField; label: string; hints: Record<SortState['dir'], string> }> = [
  { field: 'last_visit_date', label: 'Ostatnia wizyta', hints: { desc: 'Najnowsza najpierw', asc: 'Najstarsza najpierw' } },
  { field: 'next_visit_date', label: 'Następna wizyta', hints: { asc: 'Najbliższa najpierw', desc: 'Najdalsza najpierw' } },
  { field: 'full_name', label: 'Imię i nazwisko', hints: { asc: 'A → Z', desc: 'Z → A' } },
  { field: 'completed_visits', label: 'Liczba wizyt', hints: { desc: 'Najwięcej najpierw', asc: 'Najmniej najpierw' } },
  { field: 'no_show_count', label: 'No-show', hints: { desc: 'Najwięcej najpierw', asc: 'Najmniej najpierw' } },
];

// Desktop can also sort by Status (a table header); the phone sheet doesn't offer it
// (the filter chips cover it) but a restored session may still carry it.
const SORT_LABEL: Record<SortField, string> = {
  full_name: 'Imię i nazwisko',
  last_visit_date: 'Ostatnia wizyta',
  next_visit_date: 'Następna wizyta',
  completed_visits: 'Liczba wizyt',
  no_show_count: 'No-show',
  is_active: 'Status',
};

export interface ClientsMobileViewProps {
  /** Already filtered + sorted. */
  clients: Client[];
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  searchInput: string;
  onSearchChange: (value: string) => void;
  onSearchSubmit: () => void;
  activeFilter: FilterKey;
  onFilterChange: (filter: FilterKey) => void;
  filterCounts: Record<FilterKey, number>;
  sort: SortState;
  onSelectSort: (field: SortField) => void;
  canWrite: boolean;
  showNotes: boolean;
  onDeactivate: (client: Client) => void;
  onBulkUpdatePreferences: () => void;
  isUpdatingPrefs: boolean;
}

/**
 * Klienci — phone rendering (≤640px). Same shape as Użytkownicy: a sticky search +
 * filter bar, a card list (tap opens the client, ⋯ opens a bottom action sheet with
 * what the desktop row's icons do), and the page's primary action pinned to the thumb
 * zone. What the table's sortable headers did lives in a sort sheet — the headers
 * are hidden on a phone, so without it there would be no way to sort at all.
 */
export function ClientsMobileView({
  clients,
  loading,
  error,
  onRetry,
  searchInput,
  onSearchChange,
  onSearchSubmit,
  activeFilter,
  onFilterChange,
  filterCounts,
  sort,
  onSelectSort,
  canWrite,
  showNotes,
  onDeactivate,
  onBulkUpdatePreferences,
  isUpdatingPrefs,
}: ClientsMobileViewProps) {
  const confirm = useConfirm();
  const [sheetClient, setSheetClient] = useState<Client | null>(null);
  const [sortOpen, setSortOpen] = useState(false);
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);

  // The shell's top bar has a slot for page-level actions (the visits page parks
  // "Rozlicz przeszłe wizyty" there) — the bulk preferences refresh lives in it, since
  // the page header itself is dropped on a phone to win back viewport height.
  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-actions'));
  }, []);

  async function handleBulkClick() {
    const ok = await confirm({
      title: 'Aktualizacja preferencji',
      message: 'Przeliczyć preferencje wszystkich klientów na podstawie historii ich wizyt?',
      confirmText: 'Aktualizuj',
    });
    if (ok) onBulkUpdatePreferences();
  }

  function handleSortPick(field: SortField) {
    onSelectSort(field);
    setSortOpen(false);
  }

  function handleSheetDeactivate(client: Client) {
    setSheetClient(null);
    onDeactivate(client);
  }

  const sheet = sheetClient;
  const sheetRisk = sheet ? (sheet.no_show_count ?? 0) > 2 : false;

  return (
    <div className={`refined-page clients-page clients-page--mobile${canWrite ? ' clients-page--cta' : ''} animate-fade-up`}>
      {/* The shell's top bar already names the page — keep the h1 for screen readers only. */}
      <h1 className="clients-sr-only">Klienci</h1>

      <div className="clients-toolbar">
        <div className="clients-search">
          <Icon name="search" />
          <input
            type="search"
            className="form-input"
            placeholder="Szukaj: imię, telefon, email…"
            aria-label="Szukaj klientów"
            enterKeyHint="search"
            value={searchInput}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onSearchSubmit();
                e.currentTarget.blur();
              }
            }}
          />
        </div>
        <div className="filter-chips" role="group" aria-label="Filtruj klientów">
          <button type="button" className={`filter-chip${activeFilter === 'active' ? ' active' : ''}`} aria-pressed={activeFilter === 'active'} onClick={() => onFilterChange('active')}>
            Aktywni <span className="chip-count">{filterCounts.active}</span>
          </button>
          <button type="button" className={`filter-chip${activeFilter === 'vip' ? ' active' : ''}`} aria-pressed={activeFilter === 'vip'} onClick={() => onFilterChange('vip')}>
            VIP <span className="chip-count">{filterCounts.vip}</span>
          </button>
          <button type="button" className={`filter-chip${activeFilter === 'inactive' ? ' active' : ''}`} aria-pressed={activeFilter === 'inactive'} onClick={() => onFilterChange('inactive')}>
            Nieaktywni <span className="chip-count">{filterCounts.inactive}</span>
          </button>
        </div>
      </div>

      <div className="clients-listbar">
        <span className="clients-count" aria-live="polite">
          {loading ? ' ' : `${clients.length} ${clients.length === 1 ? 'klient' : 'klientów'}`}
        </span>
        <button type="button" className="clients-sort-btn" aria-haspopup="dialog" onClick={() => setSortOpen(true)}>
          Sortuj: <strong>{SORT_LABEL[sort.field]}</strong>
          <Icon name={sort.dir === 'asc' ? 'arrow_upward' : 'arrow_downward'} />
        </button>
      </div>

      {loading ? (
        <ul className="client-cards" aria-label="Ładowanie klientów">
          {Array.from({ length: 6 }).map((_, i) => (
            <li key={i} className="client-card client-card--skeleton">
              <div className="skeleton" style={{ width: '2.5rem', height: '2.5rem', borderRadius: '50%', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton" style={{ height: '0.9375rem', width: '55%', marginBottom: '0.5rem' }} />
                <div className="skeleton" style={{ height: '0.75rem', width: '80%' }} />
              </div>
            </li>
          ))}
        </ul>
      ) : error ? (
        <div className="clients-state" role="alert">
          <p style={{ color: 'var(--color-error)' }}>Błąd ładowania klientów: {error.message}</p>
          <Button variant="secondary" icon="refresh" onClick={onRetry}>
            Spróbuj ponownie
          </Button>
        </div>
      ) : clients.length === 0 ? (
        <div className="clients-state">
          <Icon name="search_off" className="empty-icon" />
          <p>Nie znaleziono klientów</p>
        </div>
      ) : (
        <ul className="client-cards">
          {clients.map((client) => (
            <ClientCard key={client.id} client={client} showNotes={showNotes} onOpenSheet={setSheetClient} />
          ))}
        </ul>
      )}

      {canWrite && (
        <div className="clients-mobile-cta">
          <ButtonLink to="/klienci/nowy" variant="primary" icon="add">
            Dodaj klienta
          </ButtonLink>
        </div>
      )}

      {canWrite &&
        headerSlot &&
        createPortal(
          <button
            type="button"
            className="clients-header-btn"
            aria-label="Aktualizuj preferencje klientów"
            title="Aktualizuj preferencje"
            aria-busy={isUpdatingPrefs}
            disabled={isUpdatingPrefs}
            onClick={handleBulkClick}
          >
            <Icon name={isUpdatingPrefs ? 'hourglass_top' : 'auto_awesome'} />
          </button>,
          headerSlot,
        )}

      <Modal isOpen={sheet !== null} onClose={() => setSheetClient(null)} title={sheet?.full_name ?? ''} variant="sheet">
        {sheet && (
          <ul className="action-sheet">
            <li>
              <Link className="action-sheet-item" to={`/klienci/${sheet.id}`}>
                <Icon name="visibility" /> Zobacz klienta
              </Link>
            </li>
            {canWrite && (
              <li>
                <Link className="action-sheet-item" to={`/klienci/${sheet.id}/edytuj`}>
                  <Icon name="edit" /> Edytuj dane
                </Link>
              </li>
            )}
            {canWrite && sheet.is_active && sheetRisk && (
              <li className="action-sheet-danger">
                <button type="button" className="action-sheet-item" onClick={() => handleSheetDeactivate(sheet)}>
                  <Icon name="person_off" /> Dezaktywuj klienta
                </button>
              </li>
            )}
          </ul>
        )}
      </Modal>

      <Modal isOpen={sortOpen} onClose={() => setSortOpen(false)} title="Sortuj klientów" variant="sheet">
        <ul className="action-sheet">
          {SORT_OPTIONS.map((opt) => {
            const active = sort.field === opt.field;
            return (
              <li key={opt.field}>
                <button type="button" className={`action-sheet-item${active ? ' is-active' : ''}`} aria-pressed={active} onClick={() => handleSortPick(opt.field)}>
                  <span className="sort-item-text">
                    <span className="sort-item-label">{opt.label}</span>
                    <span className="sort-item-hint">{opt.hints[active ? sort.dir : DEFAULT_SORT_DIR[opt.field]]}</span>
                  </span>
                  {active && <Icon name={sort.dir === 'asc' ? 'arrow_upward' : 'arrow_downward'} className="sort-item-check" />}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="action-sheet-reason">Dotknij aktywnego pola ponownie, aby odwrócić kolejność.</p>
      </Modal>
    </div>
  );
}

interface ClientCardProps {
  client: Client;
  showNotes: boolean;
  onOpenSheet: (client: Client) => void;
}

function ClientCard({ client, showNotes, onOpenSheet }: ClientCardProps) {
  const noShows = client.no_show_count ?? 0;
  const hasNotes = showNotes && !!client.recent_notes && client.recent_notes.length > 0;

  return (
    <li className="client-card">
      <Link to={`/klienci/${client.id}`} className="client-card-main">
        <span className="client-avatar" style={clientRingStyle(client)}>
          {clientInitials(client)}
        </span>
        <span className="client-card-text">
          <span className="client-card-name">
            {client.full_name}
            {isVipClient(client) && <span className="vip-tag">★ VIP</span>}
          </span>
          {client.phone && <span className="client-card-sub">{formatPhone(client.phone)}</span>}
          <span className="client-card-facts">
            <span className="client-fact">
              <span className="client-fact-label">Ostatnia</span>
              {formatDate(client.last_visit_date)}
            </span>
            <span className="client-fact">
              <span className="client-fact-label">Następna</span>
              {client.next_visit_date ? formatNextVisitLine1(client.next_visit_date, client.next_visit_time) : '—'}
            </span>
          </span>
          <span className="client-card-meta">
            <span className="client-pill">
              Wizyt <strong>{client.completed_visits ?? 0}</strong>
            </span>
            {noShows > 0 && (
              <span className={`client-pill${noShows > 2 ? ' client-pill--danger' : ''}`}>
                No-show <strong>{noShows}</strong>
              </span>
            )}
            {!client.is_active && <span className="client-pill client-pill--muted">Nieaktywny</span>}
          </span>
          {hasNotes && (
            <span className="client-card-notes">
              <NotesDigest notes={client.recent_notes} />
            </span>
          )}
        </span>
      </Link>
      <button type="button" className="client-card-more" aria-label={`Akcje: ${client.full_name}`} onClick={() => onOpenSheet(client)}>
        <Icon name="more_horiz" />
      </button>
    </li>
  );
}
