import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import './VisitNotes.css';
import { visitNotesApi } from '../../lib/api/visitNotes';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../feedback/ToastProvider';
import { useConfirm } from '../feedback/ConfirmProvider';
import { Button } from '../ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { formatDate } from '../../lib/format';
import { formatNoteStamp } from '../../lib/visitNotes/noteFormat';
import { VisitNoteModal } from './VisitNoteModal';
import type { VisitNote } from '../../types/visitNote';

const PAGE_SIZE = 10;
/** The server never returns more than this per request (MAX_PAGE_SIZE). */
const MAX_REFETCH = 50;

/** The two host pages style their cards differently; the section borrows each one's own classes. */
const HOST = {
  detail: { card: 'detail-card', header: 'detail-section-header', title: 'detail-section-title', Tag: 'h2' },
  form: { card: 'form-card', header: 'vn-header', title: 'card-title', Tag: 'h3' },
} as const;

export interface VisitNotesSectionProps {
  clientId: number;
  /** Visit page only: the visit being viewed. The add button binds to it and shows
   * only while it is completed; leave unset on the client page (picker instead). */
  appointmentId?: number;
  /** Change it to refetch from outside, e.g. when the visit's status changes. */
  refreshKey?: string | number;
  /** Which page's card styling to borrow. */
  variant: keyof typeof HOST;
}

/**
 * "Uwagi i zalecenia z wizyt": a client's notes across all their visits, newest
 * edit first, ten at a time. Shared by the client page and the visit page.
 *
 * Who may edit/delete/add is decided by the server per row (`can_edit`) and once
 * for the section (`can_add`) from the `appointments` flags + own-data scope —
 * the UI only reflects it, it never re-derives it.
 */
export function VisitNotesSection({ clientId, appointmentId, refreshKey, variant }: VisitNotesSectionProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const host = HOST[variant];

  const [notes, setNotes] = useState<VisitNote[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [canAdd, setCanAdd] = useState(false);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [loadingMore, setLoadingMore] = useState(false);
  const [editing, setEditing] = useState<VisitNote | null>(null);
  const [adding, setAdding] = useState(false);
  const latestRequest = useRef(0);

  /** (Re)load the newest `count` notes. After a write the rows already on screen are kept. */
  const load = useCallback(
    async (count: number) => {
      const request = ++latestRequest.current;
      try {
        const page = await visitNotesApi.list(clientId, {
          limit: Math.min(Math.max(count, PAGE_SIZE), MAX_REFETCH),
          offset: 0,
          appointmentId,
        });
        if (request !== latestRequest.current) return; // a newer load superseded this one
        setNotes(page.notes);
        setTotal(page.total);
        setHasMore(page.has_more);
        setCanAdd(page.can_add);
        setStatus('ready');
      } catch (err) {
        if (request !== latestRequest.current) return;
        setErrorMessage(err instanceof ApiError ? err.message : 'Nie udało się wczytać uwag');
        setStatus('error');
      }
    },
    [clientId, appointmentId],
  );

  // A different client is a different list: show loading, not the previous client's rows.
  useEffect(() => {
    setStatus('loading');
    setNotes([]);
  }, [clientId]);

  useEffect(() => {
    load(PAGE_SIZE);
  }, [load, refreshKey]);

  async function handleLoadMore() {
    setLoadingMore(true);
    try {
      const page = await visitNotesApi.list(clientId, { limit: PAGE_SIZE, offset: notes.length, appointmentId });
      // De-dupe by id: an edit elsewhere can shift rows between pages.
      setNotes((prev) => {
        const seen = new Set(prev.map((n) => n.id));
        return [...prev, ...page.notes.filter((n) => !seen.has(n.id))];
      });
      setTotal(page.total);
      setHasMore(page.has_more);
      setCanAdd(page.can_add);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się wczytać starszych wpisów');
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleDelete(note: VisitNote) {
    const ok = await confirm({
      title: 'Usuń uwagę',
      message: `Czy na pewno usunąć tę uwagę z wizyty z dnia ${formatDate(note.appointment_date)}?`,
      confirmText: 'Usuń',
      type: 'danger',
    });
    if (!ok) return;
    try {
      await visitNotesApi.remove(note.id);
      toast.success('Uwaga usunięta');
      await load(notes.length);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się usunąć uwagi');
    }
  }

  const showActions = notes.some((n) => n.can_edit);

  return (
    <div className={`${host.card} vn-section`}>
      <div className={host.header}>
        <host.Tag className={host.title}>Uwagi i zalecenia z wizyt</host.Tag>
        {status === 'ready' && total > 0 && <span className="vn-count">{total} wpisów łącznie</span>}
      </div>

      {status === 'loading' ? (
        <p className="empty-text">Ładowanie...</p>
      ) : status === 'error' ? (
        <div className="vn-error">
          <p className="empty-text" style={{ color: 'var(--color-error)' }}>
            Błąd ładowania uwag: {errorMessage}
          </p>
          <Button variant="secondary" small onClick={() => load(PAGE_SIZE)}>
            Spróbuj ponownie
          </Button>
        </div>
      ) : (
        <>
          {notes.length === 0 ? (
            <p className="empty-text vn-empty">Brak uwag z wizyt.</p>
          ) : (
            <div className="vn-table-wrap stack-cards-wrap">
              <table className="refined-table stack-cards vn-table">
                <thead>
                  <tr>
                    <th>Data wizyty</th>
                    <th>Klient</th>
                    <th>Usługa</th>
                    <th>Ostatnia edycja</th>
                    <th>Edytował</th>
                    <th>Treść uwagi</th>
                    {showActions && (
                      <th>
                        <span className="sr-only">Akcje</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {notes.map((note) => (
                    <tr key={note.id}>
                      <td className="cell-name vn-cell-date" data-label="Data wizyty">
                        <Link to={`/wizyty/${note.appointment_id}`} className="vn-visit-link">
                          {formatDate(note.appointment_date)}
                        </Link>
                      </td>
                      <td data-label="Klient">{note.client_name ?? '—'}</td>
                      <td data-label="Usługa">{note.service_name ?? '—'}</td>
                      <td className="vn-cell-stamp" data-label="Ostatnia edycja">
                        {formatNoteStamp(note.updated_at)}
                      </td>
                      <td data-label="Edytował">{note.updated_by_name ?? '—'}</td>
                      <td className="vn-cell-text" data-label="Treść uwagi">
                        {note.note_text}
                      </td>
                      {showActions && (
                        <td className="cell-actions">
                          {note.can_edit && (
                            <div className="action-icons">
                              <button type="button" className="action-icon-btn" title="Edytuj uwagę" aria-label="Edytuj uwagę" onClick={() => setEditing(note)}>
                                <Icon name="edit" />
                              </button>
                              <button type="button" className="action-icon-btn vn-action-delete" title="Usuń uwagę" aria-label="Usuń uwagę" onClick={() => handleDelete(note)}>
                                <Icon name="delete" />
                              </button>
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="vn-footer">
            <div>
              {hasMore && (
                <button type="button" className="vn-more" onClick={handleLoadMore} disabled={loadingMore}>
                  {loadingMore ? 'Ładowanie…' : 'Zobacz starsze wpisy →'}
                </button>
              )}
            </div>
            {canAdd && (
              <Button variant="secondary" small icon="note_add" onClick={() => setAdding(true)}>
                Dodaj uwagę
              </Button>
            )}
          </div>
        </>
      )}

      <VisitNoteModal isOpen={editing !== null} onClose={() => setEditing(null)} note={editing} onSaved={() => load(notes.length)} />
      <VisitNoteModal
        isOpen={adding}
        onClose={() => setAdding(false)}
        appointmentId={appointmentId ?? null}
        clientId={clientId}
        onSaved={() => load(notes.length)}
      />
    </div>
  );
}
