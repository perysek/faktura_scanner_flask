import { useEffect, useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { useToast } from '../../components/feedback/ToastProvider';
import { invoicesApi } from '../../lib/api/invoices';
import { ApiError } from '../../lib/api/client';
import type { InvoiceSyncItem } from '../../types/invoice';

export interface SellerSyncModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called after a successful "Zastosuj zmiany" apply, so the caller can
   * reload its own invoice list (the sync updates seller_id links that the
   * list's table doesn't otherwise re-fetch on its own). */
  onApplied: () => void;
}

/**
 * "Sync sprzedawców" — checkbox-select-and-apply modal, ported 1:1 from
 * list_refined.html's `openSellerSyncModal()`/`showSellerSyncModal()`.
 * Own fetch-on-open (rather than the caller pre-fetching and passing a
 * result down) so FakturyListPage doesn't need to hold sync state at all —
 * this is the ONLY place `/api/invoices/seller-sync-check` is called from.
 */
export function SellerSyncModal({ isOpen, onClose, onApplied }: SellerSyncModalProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<InvoiceSyncItem[] | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setItems(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    invoicesApi
      .sellerSyncCheck()
      .then((result) => {
        if (cancelled) return;
        const all = [...result.unlinked, ...result.wrong_link];
        setItems(all);
        setChecked(new Set(all.map((_, i) => i)));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        toast.error(err instanceof ApiError ? err.message : 'Błąd sprawdzania powiązań ze sprzedawcami');
        onClose();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  function toggleAll(value: boolean) {
    setChecked(value && items ? new Set(items.map((_, i) => i)) : new Set());
  }

  function toggleOne(index: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  async function handleApply() {
    if (!items) return;
    const updates = items.filter((_, i) => checked.has(i)).map((item) => ({ invoice_id: item.invoice_id, seller_id: item.suggested_seller_id }));
    if (updates.length === 0) {
      toast.info('Nie zaznaczono żadnej pozycji do aktualizacji');
      return;
    }
    setApplying(true);
    try {
      const result = await invoicesApi.sellerSyncApply(updates);
      toast.success(result.message || `Zaktualizowano ${result.updated_count} faktur`);
      onClose();
      onApplied();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji powiązań');
    } finally {
      setApplying(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Synchronizacja powiązań — Sprzedawcy"
      size="large"
      footer={
        items && items.length > 0 ? (
          <>
            <Button variant="secondary" onClick={onClose}>
              Anuluj
            </Button>
            <Button variant="primary" isLoading={applying} loadingText="Aktualizowanie…" onClick={handleApply}>
              Zastosuj zmiany
            </Button>
          </>
        ) : (
          <Button variant="secondary" onClick={onClose}>
            Zamknij
          </Button>
        )
      }
    >
      {loading ? (
        <p className="empty-text">Sprawdzanie powiązań…</p>
      ) : !items || items.length === 0 ? (
        <p className="empty-text">Wszystkie faktury są poprawnie powiązane ze sprzedawcami.</p>
      ) : (
        <>
          <div className="sync-modal-intro">
            Znaleziono <strong>{items.length}</strong> faktur wymagających aktualizacji powiązania ze sprzedawcą. Odznacz wiersze, których nie chcesz zmieniać.
          </div>
          <div className="sync-modal-toggle-row">
            <button type="button" onClick={() => toggleAll(true)}>
              Zaznacz wszystkie
            </button>
            <button type="button" onClick={() => toggleAll(false)}>
              Odznacz wszystkie
            </button>
          </div>
          <div className="sync-modal-table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '2rem' }}>
                    <span className="sr-only">Zaznacz</span>
                  </th>
                  <th>Nr faktury</th>
                  <th>Sprzedawca (faktura)</th>
                  <th>Sprzedawca (baza)</th>
                  <th>Typ</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={`${item.invoice_id}-${i}`}>
                    <td>
                      <input type="checkbox" checked={checked.has(i)} onChange={() => toggleOne(i)} />
                    </td>
                    <td>
                      <span style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{item.invoice_number || '—'}</span>
                      <div style={{ fontSize: '0.7rem', color: 'var(--color-ink-subtle)' }}>{item.invoice_date || ''}</div>
                    </td>
                    <td>
                      {item.invoice_seller_name || '—'}
                      <div style={{ fontFamily: 'monospace', fontSize: '0.7rem', color: 'var(--color-ink-subtle)' }}>{item.invoice_nip || '(brak NIP)'}</div>
                    </td>
                    <td>
                      {item.suggested_seller_name || '—'}
                      {item.type === 'wrong_link' && <div style={{ fontSize: '0.7rem', color: 'var(--color-ink-subtle)', marginTop: 2 }}>Było: {item.current_seller_name || '—'}</div>}
                      <div style={{ marginTop: 2 }}>
                        <span className={`sync-modal-match-badge ${item.match_reason === 'nazwa' ? 'by-name' : 'by-nip'}`}>{item.match_reason === 'nazwa' ? 'wg nazwy' : 'wg NIP'}</span>
                      </div>
                    </td>
                    <td style={{ fontSize: '0.75rem', color: item.type === 'unlinked' ? 'var(--color-warning)' : 'var(--color-error)' }}>
                      {item.type === 'unlinked' ? 'brak powiązania' : 'błędne powiązanie'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Modal>
  );
}
