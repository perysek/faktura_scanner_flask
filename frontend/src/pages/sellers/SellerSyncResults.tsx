import { useState } from 'react';
import { Button } from '../../components/ui/Button';
import { useToast } from '../../components/feedback/ToastProvider';
import { sellersApi } from '../../lib/api/sellers';
import { ApiError } from '../../lib/api/client';
import type { NameDiscrepancy, SyncResult } from '../../types/seller';

interface SellerSyncResultsProps {
  result: SyncResult;
  onClose: () => void;
  onChanged: (result: SyncResult) => void;
}

/** Recommendation heuristic — ported 1:1 from list_refined.html's `analyzeDiscrepancy()`:
 * prefer whichever name has punctuation (more likely correctly formatted),
 * falling back to "longer + capitalised" as a completeness signal. */
function analyzeDiscrepancy(d: NameDiscrepancy): { recommendation: 'use_seller_name' | 'use_invoice_name' | null; reason: string } {
  const sellerName = d.seller_name || '';
  const invoiceName = d.invoice_seller_name || '';
  const sellerHasDots = sellerName.includes('.');
  const invoiceHasDots = invoiceName.includes('.');
  const sellerIsLonger = sellerName.length > invoiceName.length;
  const sellerHasCapitals = sellerName !== sellerName.toLowerCase();

  if (sellerHasDots && !invoiceHasDots) return { recommendation: 'use_seller_name', reason: 'Nazwa w bazie zawiera poprawną interpunkcję' };
  if (!sellerHasDots && invoiceHasDots) return { recommendation: 'use_invoice_name', reason: 'Nazwa na fakturze zawiera poprawną interpunkcję' };
  if (sellerIsLonger && sellerHasCapitals) return { recommendation: 'use_seller_name', reason: 'Nazwa w bazie jest pełniejsza i poprawnie sformatowana' };
  if (sellerIsLonger) return { recommendation: 'use_seller_name', reason: 'Nazwa w bazie jest pełniejsza' };
  return { recommendation: null, reason: '' };
}

/**
 * "Wyniki synchronizacji" — second of Sprzedawcy's three sub-features.
 * Ported from list_refined.html's `showSyncResults()`/`fixDiscrepancy()`/
 * `addMissingSeller()`/`refreshSyncResults()`. Original swaps DOM visibility
 * in-page (no URL change) — mirrored here as a component SellersListPage
 * conditionally renders instead of the list, not a new route.
 */
export function SellerSyncResults({ result, onClose, onChanged }: SellerSyncResultsProps) {
  const toast = useToast();
  const [busyKey, setBusyKey] = useState<string | null>(null);

  async function refresh() {
    try {
      const fresh = await sellersApi.sync();
      onChanged(fresh);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd odświeżania wyników synchronizacji');
    }
  }

  async function handleFix(action: 'use_seller_name' | 'use_invoice_name', d: NameDiscrepancy) {
    const key = `fix-${d.invoice_id}`;
    setBusyKey(key);
    try {
      const res = await sellersApi.fixDiscrepancy(action, d.invoice_id, d.seller_id);
      toast.success(res.message);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd naprawiania niezgodności');
    } finally {
      setBusyKey(null);
    }
  }

  async function handleAddMissing(nip: string, name: string) {
    const key = `add-${nip}`;
    setBusyKey(key);
    try {
      const res = await sellersApi.addMissing(nip, name);
      toast.success(res.message);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd dodawania sprzedawcy');
    } finally {
      setBusyKey(null);
    }
  }

  const allGood = result.missing_sellers.length === 0 && result.name_discrepancies.length === 0;

  return (
    <div className="refined-page sync-results-view animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Wyniki synchronizacji</h1>
          <p className="page-subtitle">Przegląd niezgodności i brakujących danych</p>
        </div>
        <Button variant="secondary" icon="close" onClick={onClose}>
          Zamknij
        </Button>
      </header>

      <div className="sync-summary-grid">
        <div className="sync-stat-card">
          <span className="sync-stat-value">{result.summary.total_sellers}</span>
          <span className="sync-stat-label">Sprzedawcy w bazie</span>
        </div>
        <div className="sync-stat-card">
          <span className="sync-stat-value">{result.summary.total_invoices}</span>
          <span className="sync-stat-label">Faktury w bazie</span>
        </div>
        <div className="sync-stat-card sync-stat-warning">
          <span className="sync-stat-value">{result.summary.missing_sellers_count}</span>
          <span className="sync-stat-label">Brakujący sprzedawcy</span>
        </div>
        <div className="sync-stat-card sync-stat-error">
          <span className="sync-stat-value">{result.summary.discrepancies_count}</span>
          <span className="sync-stat-label">Niezgodności nazw</span>
        </div>
      </div>

      {allGood && (
        <div className="sync-success-message">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ width: '3rem', height: '3rem', color: 'var(--color-success)' }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="sync-success-text">Wszystko zsynchronizowane! Brak niezgodności.</p>
        </div>
      )}

      {result.name_discrepancies.length > 0 && (
        <div className="sync-card">
          <div className="sync-card-header">
            <h3 className="sync-card-title">Niezgodności nazw</h3>
            <span className="sync-badge sync-badge-error">{result.name_discrepancies.length}</span>
          </div>
          <div className="table-container" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
            <table className="refined-table">
              <thead>
                <tr>
                  <th style={{ width: 120 }}>Nr faktury</th>
                  <th style={{ width: '25%' }}>Nazwa w bazie</th>
                  <th style={{ width: '25%' }}>Nazwa na fakturze</th>
                  <th>Akcje</th>
                </tr>
              </thead>
              <tbody>
                {result.name_discrepancies.map((d) => {
                  const rec = analyzeDiscrepancy(d);
                  const isSellerRecommended = rec.recommendation === 'use_seller_name';
                  const isInvoiceRecommended = rec.recommendation === 'use_invoice_name';
                  const busy = busyKey === `fix-${d.invoice_id}`;
                  return (
                    <tr key={`${d.invoice_id}-${d.seller_id}`} className="discrepancy-row">
                      <td style={{ fontFamily: "'Courier New', monospace", fontSize: '0.8125rem', fontWeight: 500 }}>{d.invoice_number}</td>
                      <td style={{ color: 'var(--color-ink)', fontWeight: 500 }}>{d.seller_name}</td>
                      <td style={{ color: 'var(--color-warning)', fontWeight: 500 }}>{d.invoice_seller_name}</td>
                      <td>
                        <div className="discrepancy-actions">
                          <Button variant={isSellerRecommended ? 'primary' : 'secondary'} small disabled={busy} onClick={() => handleFix('use_seller_name', d)}>
                            {isSellerRecommended && '✓ '}← Użyj z bazy
                          </Button>
                          <Button variant={isInvoiceRecommended ? 'primary' : 'secondary'} small disabled={busy} onClick={() => handleFix('use_invoice_name', d)}>
                            {isInvoiceRecommended && '✓ '}→ Użyj z faktury
                          </Button>
                        </div>
                        {rec.reason && <div className="discrepancy-recommendation">💡 {rec.reason}</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result.missing_sellers.length > 0 && (
        <div className="sync-card">
          <div className="sync-card-header">
            <h3 className="sync-card-title">Brakujący sprzedawcy</h3>
            <span className="sync-badge sync-badge-warning">{result.missing_sellers.length}</span>
          </div>
          <div className="table-container" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
            <table className="refined-table">
              <thead>
                <tr>
                  <th style={{ width: 140 }}>NIP</th>
                  <th>Nazwa</th>
                  <th style={{ width: 100, textAlign: 'center' }}>Faktury</th>
                  <th style={{ width: 180 }}>Akcje</th>
                </tr>
              </thead>
              <tbody>
                {result.missing_sellers.map((ms) => (
                  <tr key={ms.nip}>
                    <td style={{ fontFamily: "'Courier New', monospace", fontSize: '0.8125rem' }}>{ms.nip}</td>
                    <td style={{ fontWeight: 500 }}>{ms.name}</td>
                    <td style={{ textAlign: 'center' }}>
                      <span className="sync-count-badge">{ms.count}</span>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <Button variant="primary" small disabled={busyKey === `add-${ms.nip}`} isLoading={busyKey === `add-${ms.nip}`} loadingText="Dodawanie…" onClick={() => handleAddMissing(ms.nip, ms.name)}>
                        Dodaj do bazy
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
