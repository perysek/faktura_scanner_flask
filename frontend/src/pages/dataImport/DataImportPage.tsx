import { useEffect, useRef, useState } from 'react';
import './DataImportPage.css';
import { dataImportApi } from '../../lib/api/dataImport';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { ConflictScanSection } from './ConflictScanSection';
import type { ImportHistoryRow, ImportRunStatus, ImportStats, SessionStatus, SseEvent } from '../../types/dataImport';

function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const SESSION_BADGE: Record<SessionStatus, { label: string; className: string }> = {
  active: { label: 'Aktywna', className: 'session-badge-active' },
  expired: { label: 'Wygasła', className: 'session-badge-expired' },
  missing: { label: 'Brak sesji', className: 'session-badge-missing' },
};

const STATUS_BADGE: Record<ImportRunStatus, { label: string; className: string }> = {
  completed: { label: 'Ukończony', className: 'run-badge-completed' },
  running: { label: 'W toku', className: 'run-badge-running' },
  failed: { label: 'Błąd', className: 'run-badge-failed' },
  cancelled: { label: 'Anulowany', className: 'run-badge-cancelled' },
  unknown: { label: 'Nieznany', className: '' },
};

interface LogLine {
  text: string;
  level: 'info' | 'warning' | 'error' | 'progress';
}

function durationLabel(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return '—';
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  return ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`;
}

function skippedTotal(s: ImportStats): number {
  return (s.skipped_zero ?? 0) + (s.skipped_no_client ?? 0) + (s.skipped_no_employee ?? 0) + (s.skipped_duplicate ?? 0);
}

/** Import danych z caldis.pl — admin-only Playwright-scraper wrapper. Ported
 * from templates/data_import/index.html's inline script. Not invoice OCR
 * (that's a separate, still-deferred concern under Faktury) — this scrapes
 * appointment bookings from caldis.pl into the database.
 *
 * The "Odnów sesję" (reconnect) flow launches a HEADED Playwright browser
 * window ON THE SERVER MACHINE for manual login — this is inherently a
 * server-console operation, not something a remote browser session can
 * complete interactively. Ported as-is (button fires the request, the 503
 * "headless server" fallback message is shown verbatim) since the backend
 * behavior is unchanged; a superuser running this against a headless deploy
 * target still needs the documented `python scripts/...` fallback either way.
 */
export function DataImportPage() {
  const toast = useToast();

  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [sessionAgeDays, setSessionAgeDays] = useState<number | null>(null);
  const [sessionCheckFailed, setSessionCheckFailed] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [showManualReconnectHint, setShowManualReconnectHint] = useState(false);

  const [dateStart, setDateStart] = useState(todayISO(-90));
  const [dateEnd, setDateEnd] = useState(todayISO(0));
  const [dryRun, setDryRun] = useState(false);
  const [keepXlsx, setKeepXlsx] = useState(false);

  const [importBusy, setImportBusy] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; level: 'info' | 'error' | 'success' } | null>(null);
  const [logLines, setLogLines] = useState<LogLine[]>([]);
  const [result, setResult] = useState<{ stats: ImportStats; errorMessage?: string } | null>(null);

  const [history, setHistory] = useState<ImportHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const eventSourceRef = useRef<EventSource | null>(null);
  const logPanelRef = useRef<HTMLDivElement>(null);
  const lastStatusRef = useRef<ImportRunStatus | null>(null);
  const lastStatsRef = useRef<ImportStats | null>(null);

  function loadSessionStatus() {
    setSessionCheckFailed(false);
    dataImportApi
      .sessionStatus()
      .then((r) => {
        setSessionStatus(r.status);
        setSessionAgeDays(r.age_days);
      })
      .catch(() => setSessionCheckFailed(true));
  }

  function loadHistory() {
    setHistoryLoading(true);
    dataImportApi
      .history()
      .then(setHistory)
      .catch(() => toast.error('Błąd ładowania historii'))
      .finally(() => setHistoryLoading(false));
  }

  useEffect(() => {
    loadSessionStatus();
    loadHistory();
    return () => {
      eventSourceRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (logPanelRef.current) logPanelRef.current.scrollTop = logPanelRef.current.scrollHeight;
  }, [logLines]);

  async function handleReconnect() {
    setReconnecting(true);
    setShowManualReconnectHint(false);
    try {
      await dataImportApi.reconnectSession();
      loadSessionStatus();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setShowManualReconnectHint(true);
      } else {
        toast.error(err instanceof ApiError ? err.message : 'Błąd podczas odnawiania sesji.');
      }
    } finally {
      setReconnecting(false);
    }
  }

  function handleSseEvent(event: SseEvent) {
    if (event.type === 'log') {
      setLogLines((prev) => [...prev, { text: event.message, level: event.level ?? 'info' }]);
    } else if (event.type === 'stats') {
      lastStatsRef.current = event.stats;
      setStatusMsg({
        text: `Wstawiono: ${event.stats.inserted ?? 0} | Pominięto: ${skippedTotal(event.stats)} | Błędy: ${event.stats.errors ?? 0}`,
        level: 'info',
      });
    } else if (event.type === 'status') {
      lastStatusRef.current = event.status;
      if (event.status === 'failed') setStatusMsg({ text: 'Import zakończony błędem.', level: 'error' });
    } else if (event.type === 'done') {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      setImportBusy(false);

      const finalStatus = event.status || lastStatusRef.current || 'unknown';
      const finalStats = event.stats || lastStatsRef.current || {};
      const ok = finalStatus === 'completed';
      setStatusMsg({ text: ok ? 'Import zakończony.' : `Import zakończony ze statusem: ${finalStatus}`, level: ok ? 'success' : 'error' });
      setResult({ stats: finalStats, errorMessage: event.error_message });
      setLogLines((prev) => [...prev, { text: `— Koniec (${finalStatus}) —`, level: ok ? 'info' : 'error' }]);
      lastStatusRef.current = null;
      lastStatsRef.current = null;
      setTimeout(loadHistory, 1000);
    }
  }

  async function handleStartImport() {
    if (!dateStart || !dateEnd) {
      setStatusMsg({ text: 'Wybierz zakres dat.', level: 'error' });
      return;
    }
    if (dateStart > dateEnd) {
      setStatusMsg({ text: 'Data od musi być wcześniejsza niż data do.', level: 'error' });
      return;
    }

    setImportBusy(true);
    setLogLines([{ text: '— Start importu —', level: 'info' }]);
    setResult(null);
    setStatusMsg({ text: 'Uruchamiam import...', level: 'info' });

    let importId: number;
    try {
      const data = await dataImportApi.start({ date_start: dateStart, date_end: dateEnd, dry_run: dryRun, keep_xlsx: keepXlsx });
      importId = data.import_id;
      setStatusMsg({ text: `Import #${importId} — trwa...`, level: 'info' });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setStatusMsg({ text: 'Import już trwa — poczekaj na zakończenie.', level: 'error' });
      } else {
        setStatusMsg({ text: err instanceof ApiError ? err.message : 'Błąd uruchamiania importu.', level: 'error' });
      }
      setImportBusy(false);
      return;
    }

    eventSourceRef.current?.close();
    const es = new EventSource(`/api/import/${importId}/stream`, { withCredentials: true });
    eventSourceRef.current = es;
    es.onmessage = (evt) => {
      try {
        handleSseEvent(JSON.parse(evt.data) as SseEvent);
      } catch {
        /* malformed frame — ignore, matches original's silent catch */
      }
    };
    es.onerror = () => setLogLines((prev) => [...prev, { text: '[WARN] Połączenie SSE przerwane — czekam na reconnect...', level: 'warning' }]);
  }

  const sessionBadge = sessionCheckFailed ? { label: 'Błąd sprawdzania', className: 'session-badge-error' } : sessionStatus ? SESSION_BADGE[sessionStatus] : { label: 'Sprawdzanie...', className: '' };

  return (
    <div className="refined-page data-import-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Import danych z caldis.pl</h1>
          <p className="page-subtitle">Pobiera rezerwacje z caldis.pl przez Playwright i importuje do bazy danych.</p>
        </div>
      </header>

      <div className="di-card">
        <h2 className="di-card-title">Sesja caldis.pl</h2>
        <div className="di-session-row">
          <span className={`session-badge ${sessionBadge.className}`}>{sessionBadge.label}</span>
          {sessionStatus && sessionStatus !== 'active' && (
            <Button variant="secondary" small isLoading={reconnecting} loadingText="Łączę..." onClick={handleReconnect}>
              <Icon name="refresh" /> Odnów sesję
            </Button>
          )}
          {showManualReconnectHint && (
            <p className="di-manual-hint">
              Serwer bez interfejsu graficznego. Uruchom raz: <code>python scripts/import_appointments_playwright.py --headed</code>
            </p>
          )}
        </div>
        {sessionAgeDays !== null && <p className="di-session-age">Wiek sesji: {sessionAgeDays} dni</p>}
      </div>

      <div className="di-card">
        <h2 className="di-card-title">Parametry importu</h2>
        <div className="di-form-grid">
          <div>
            <label className="field-label" htmlFor="date-start">
              Data od
            </label>
            <input id="date-start" type="date" className="field-input" value={dateStart} onChange={(e) => setDateStart(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="date-end">
              Data do
            </label>
            <input id="date-end" type="date" className="field-input" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} />
          </div>
        </div>
        <div className="checkbox-wrapper" style={{ marginTop: '0.75rem' }}>
          <input type="checkbox" id="dry-run" className="refined-checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          <label className="checkbox-label" htmlFor="dry-run">
            Suchy przebieg (parsuj, nie zapisuj do bazy)
          </label>
        </div>
        <div className="checkbox-wrapper" style={{ marginTop: '0.5rem' }}>
          <input type="checkbox" id="keep-xlsx" className="refined-checkbox" checked={keepXlsx} onChange={(e) => setKeepXlsx(e.target.checked)} />
          <label className="checkbox-label" htmlFor="keep-xlsx">
            Zapisz w Excel (zachowaj pobrany plik XLSX z caldis.pl)
          </label>
        </div>
        <div className="di-import-actions">
          <Button variant="primary" icon="download" isLoading={importBusy} loadingText="Importowanie..." onClick={handleStartImport}>
            Importuj
          </Button>
          {statusMsg && <span className={`di-status-msg di-status-${statusMsg.level}`}>{statusMsg.text}</span>}
        </div>
      </div>

      <div className="di-card">
        <h2 className="di-card-title">Log importu</h2>
        <div ref={logPanelRef} className="di-log-panel">
          {logLines.length === 0 ? <span className="di-log-placeholder">Brak aktywnego importu.</span> : logLines.map((l, i) => <div key={i} className={`di-log-line di-log-${l.level}`}>{l.text}</div>)}
        </div>
      </div>

      {result && (
        <div className="di-card">
          <h2 className="di-card-title">Wynik importu</h2>
          <div className="di-result-stats">
            {[
              { label: 'Wstawiono', value: result.stats.inserted ?? 0, className: 'stat-green' },
              { label: 'Nowi klienci', value: result.stats.clients_created ?? 0, className: 'stat-blue' },
              { label: 'Duplikaty', value: result.stats.skipped_duplicate ?? 0, className: 'stat-yellow' },
              { label: 'Pominięto', value: skippedTotal(result.stats) - (result.stats.skipped_duplicate ?? 0), className: 'stat-gray' },
              { label: 'Błędy', value: result.stats.errors ?? 0, className: 'stat-red' },
            ].map((m) => (
              <div key={m.label} className="di-result-tile">
                <div className={`di-result-value ${m.className}`}>{m.value}</div>
                <div className="di-result-label">{m.label}</div>
              </div>
            ))}
          </div>
          {result.errorMessage && <p className="di-result-error">Błąd: {result.errorMessage}</p>}
        </div>
      )}

      <div className="di-card">
        <h2 className="di-card-title">Historia importów (ostatnie 20)</h2>
        <div className="table-container">
          <table className="refined-table">
            <thead>
              <tr>
                <th>Rozpoczęto</th>
                <th>Zakres</th>
                <th>Przez</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Wstawiono</th>
                <th style={{ textAlign: 'right' }}>Pominięto</th>
                <th style={{ textAlign: 'right' }}>Błędy</th>
                <th>Suchy</th>
                <th style={{ textAlign: 'right' }}>Czas</th>
              </tr>
            </thead>
            <tbody>
              {historyLoading ? (
                <tr>
                  <td colSpan={9} className="empty-state cell-empty">
                    Ładowanie historii...
                  </td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-state cell-empty">
                    Brak historii importów.
                  </td>
                </tr>
              ) : (
                history.map((row) => {
                  const badge = STATUS_BADGE[row.status] ?? STATUS_BADGE.unknown;
                  const errCount = row.stats.errors ?? 0;
                  return (
                    <tr key={row.id}>
                      <td>{row.started_at ? new Date(row.started_at).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</td>
                      <td>{row.date_range_start && row.date_range_end ? `${row.date_range_start.slice(0, 10)} → ${row.date_range_end.slice(0, 10)}` : '—'}</td>
                      <td>{row.triggered_by_name || '—'}</td>
                      <td>
                        <span className={`run-badge ${badge.className}`}>{badge.label}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>{row.stats.inserted ?? '—'}</td>
                      <td style={{ textAlign: 'right' }}>{skippedTotal(row.stats) || '—'}</td>
                      <td style={{ textAlign: 'right', color: errCount > 0 ? 'var(--color-error)' : undefined }}>{row.stats.errors ?? '—'}</td>
                      <td>{row.dry_run ? '✓' : ''}</td>
                      <td style={{ textAlign: 'right' }}>{durationLabel(row.started_at, row.finished_at)}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ConflictScanSection />
    </div>
  );
}
