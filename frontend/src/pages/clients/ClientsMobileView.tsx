import { useEffect, useRef, useState } from 'react';
import type { MouseEvent, TouchEvent } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { isVipClient } from '../../components/clients/TrendSparkline';
import { Icon } from '../../lib/icons/Icon';
import { formatDate, formatNextVisitLine1, formatPhone, telHref } from '../../lib/format';
import { DEFAULT_SORT_DIR, clientInitials, clientRingStyle, newVisitHref, truncateNote } from './clientsListShared';
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

/** Same mechanics (and thresholds) as the employees list's card swipe, itself ported from the visits
 * list — hand-rolled, no gesture library in this project's deps. A horizontal drag must dominate the
 * vertical one by 1.5x before it counts as a swipe at all, so an ordinary list scroll that starts on
 * a card is never hijacked. Swipe LEFT → the client's page; swipe RIGHT → a new visit for them. */
const SWIPE_TRIGGER_PX = 84;
const SWIPE_MAX_PX = 120;

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
  /** May create visits (`appointments` write) — gates swipe-right and the sheet's "Umów wizytę". */
  canSchedule: boolean;
  /** The logged-in user's own employee, if their account is linked to one — prefilled in the new visit. */
  linkedEmployeeId: number | null;
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
  canSchedule,
  linkedEmployeeId,
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
            <ClientCard
              key={client.id}
              client={client}
              showNotes={showNotes}
              canSchedule={canSchedule}
              linkedEmployeeId={linkedEmployeeId}
              onOpenSheet={setSheetClient}
            />
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
            {canSchedule && (
              <li>
                <Link className="action-sheet-item" to={newVisitHref(sheet, linkedEmployeeId)}>
                  <Icon name="edit_calendar" /> Umów wizytę
                </Link>
              </li>
            )}
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
  canSchedule: boolean;
  linkedEmployeeId: number | null;
  onOpenSheet: (client: Client) => void;
}

/** Per-card drag state. `dx` is signed: negative = dragging left, positive = dragging right. */
function useCardSwipe(allowRight: boolean, onLeft: () => void, onRight: () => void) {
  const [dx, setDx] = useState(0);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  // A triggered swipe can be followed by a synthetic click on the card; swallow exactly that one.
  const suppressClickRef = useRef(false);

  function onTouchStart(e: TouchEvent) {
    const t = e.touches[0];
    startRef.current = { x: t.clientX, y: t.clientY };
    suppressClickRef.current = false;
  }
  function onTouchMove(e: TouchEvent) {
    const start = startRef.current;
    if (!start) return;
    const t = e.touches[0];
    const moveX = t.clientX - start.x;
    const moveY = t.clientY - start.y;
    if (Math.abs(moveX) <= Math.abs(moveY) * 1.5) return;
    if (moveX < 0) setDx(Math.max(moveX, -SWIPE_MAX_PX));
    else if (allowRight) setDx(Math.min(moveX, SWIPE_MAX_PX));
  }
  function onTouchEnd() {
    startRef.current = null;
    const final = dx;
    setDx(0);
    if (final <= -SWIPE_TRIGGER_PX) {
      suppressClickRef.current = true;
      onLeft();
    } else if (allowRight && final >= SWIPE_TRIGGER_PX) {
      suppressClickRef.current = true;
      onRight();
    }
  }
  function onTouchCancel() {
    startRef.current = null;
    setDx(0);
  }
  /** True when the click that just fired belongs to a swipe and must be ignored. */
  function consumeSuppressedClick(): boolean {
    const was = suppressClickRef.current;
    suppressClickRef.current = false;
    return was;
  }

  return { dx, handlers: { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel }, consumeSuppressedClick };
}

const stopPropagation = (e: MouseEvent) => e.stopPropagation();

function ClientCard({ client, showNotes, canSchedule, linkedEmployeeId, onOpenSheet }: ClientCardProps) {
  const navigate = useNavigate();
  const noShows = client.no_show_count ?? 0;
  const viewHref = `/klienci/${client.id}`;
  const visitHref = newVisitHref(client, linkedEmployeeId);
  const swipe = useCardSwipe(
    canSchedule,
    () => navigate(viewHref),
    () => navigate(visitHref),
  );
  const note = showNotes ? client.recent_notes?.[0] : undefined;
  const armedLeft = swipe.dx <= -SWIPE_TRIGGER_PX;
  const armedRight = swipe.dx >= SWIPE_TRIGGER_PX;

  return (
    <li className="client-card-wrap">
      {swipe.dx < 0 && (
        <div className={`client-swipe-reveal client-swipe-reveal--left${armedLeft ? ' is-armed' : ''}`} aria-hidden="true">
          <div className="client-swipe-content client-swipe-content--left" style={{ transform: `translateX(${swipe.dx}px)` }}>
            <Icon name="visibility" />
            <span className="client-swipe-label">Zobacz</span>
          </div>
        </div>
      )}
      {canSchedule && swipe.dx > 0 && (
        <div className={`client-swipe-reveal client-swipe-reveal--right${armedRight ? ' is-armed' : ''}`} aria-hidden="true">
          <div className="client-swipe-content client-swipe-content--right" style={{ transform: `translateX(${swipe.dx}px)` }}>
            <span className="client-swipe-label">Nowa wizyta</span>
            <Icon name="edit_calendar" />
          </div>
        </div>
      )}
      <div
        className={`client-card${armedLeft ? ' is-armed-left' : ''}${armedRight ? ' is-armed-right' : ''}`}
        style={swipe.dx !== 0 ? { transform: `translateX(${swipe.dx}px)`, transition: 'none' } : undefined}
        onClick={() => {
          if (swipe.consumeSuppressedClick()) return;
          navigate(viewHref);
        }}
        {...swipe.handlers}
      >
        <span className="client-avatar" style={clientRingStyle(client)}>
          {clientInitials(client)}
        </span>
        <div className="client-card-text">
          {/* The card is a div (it has to host a tel: link, and anchors can't nest); the name is the
              focusable link that keeps keyboard and screen-reader access to the client's page. */}
          <Link to={viewHref} className="client-card-name" onClick={stopPropagation}>
            {client.full_name}
            {isVipClient(client) && <span className="vip-tag">★ VIP</span>}
          </Link>
          {client.phone && (
            <span className="client-card-phone-row">
              <a className="client-phone-btn" href={telHref(client.phone)} aria-label={`Zadzwoń: ${formatPhone(client.phone)}`} onClick={stopPropagation}>
                <Icon name="call" />
              </a>
              <span className="client-card-phone">{formatPhone(client.phone)}</span>
            </span>
          )}
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
          {note && (
            <p className="client-card-note">
              {truncateNote(note.text)}
              {note.service_name && <span className="client-note-service"> ({note.service_name})</span>}
            </p>
          )}
        </div>
        <button
          type="button"
          className="client-card-more"
          aria-label={`Akcje: ${client.full_name}`}
          onClick={(e) => {
            e.stopPropagation();
            onOpenSheet(client);
          }}
        >
          <Icon name="more_horiz" />
        </button>
      </div>
    </li>
  );
}
