import { useCallback, useEffect, useRef, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import './DataImportPage.css';
import { dataImportApi } from '../../lib/api/dataImport';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { CheckboxField, DatePickerField } from '../../components/ui/form';
import { Icon } from '../../lib/icons/Icon';
import { ScrollJumpButtons } from '../appointments/ScrollJumpButtons';
import { ConflictScanSection } from './ConflictScanSection';
import { ImportHistoryCard } from './ImportHistoryCard';
import { RunPanel } from './RunPanel';
import { SessionCard } from './SessionCard';
import { isoOf, rangeDays, todayISO } from './dataImportShared';
import { useImportRun } from './useImportRun';
import type { ImportHistoryRow, SessionStatusResponse } from '../../types/dataImport';

interface RangePreset {
  id: string;
  label: string;
  range: () => [string, string];
}

const PRESETS: RangePreset[] = [
  { id: '7', label: 'Ostatnie 7 dni', range: () => [todayISO(-6), todayISO(0)] },
  { id: '30', label: 'Ostatnie 30 dni', range: () => [todayISO(-29), todayISO(0)] },
  { id: '90', label: 'Ostatnie 90 dni', range: () => [todayISO(-89), todayISO(0)] },
  {
    id: 'month',
    label: 'Ten miesiąc',
    range: () => {
      const d = new Date();
      return [isoOf(new Date(d.getFullYear(), d.getMonth(), 1)), todayISO(0)];
    },
  },
  // The backend has no upper bound on date_end: future bookings come in as 'scheduled'.
  { id: 'next30', label: 'Nadchodzące 30 dni', range: () => [todayISO(0), todayISO(30)] },
];

const rise = (i: number) => ({ '--i': i }) as CSSProperties;

/**
 * Import wizyt z caldis.pl — pulls bookings from caldis.pl (Playwright scraper
 * on the server, services/data_import_runner.py) into the appointments table.
 * Not invoice OCR; that is a separate concern under Faktury.
 *
 * Layout, top to bottom: the import form beside the session card, the live
 * run panel (SSE log + counters), the run history, and the visit conflict scan
 * for duplicates a reschedule leaves behind. A run that is still going when
 * the page loads (found as `running` in the history) is re-attached to, so a
 * reload no longer loses the live log.
 *
 * All endpoints: /api/import/* (routes/import_routes.py), every one gated by
 * module_permission_required('data_import') — the same rule as the route guard
 * in router.tsx and the sidebar link in navConfig.ts.
 */
export function DataImportPage() {
  const toast = useToast();

  const [session, setSession] = useState<SessionStatusResponse | null>(null);
  const [sessionChecking, setSessionChecking] = useState(true);
  const [sessionFailed, setSessionFailed] = useState(false);

  const [dateStart, setDateStart] = useState(() => PRESETS[2].range()[0]);
  const [dateEnd, setDateEnd] = useState(() => PRESETS[2].range()[1]);
  const [dryRun, setDryRun] = useState(false);
  const [keepXlsx, setKeepXlsx] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [history, setHistory] = useState<ImportHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const reattachChecked = useRef(false);

  const loadSession = useCallback(() => {
    setSessionChecking(true);
    setSessionFailed(false);
    dataImportApi
      .sessionStatus()
      .then(setSession)
      .catch(() => setSessionFailed(true))
      .finally(() => setSessionChecking(false));
  }, []);

  const loadHistory = useCallback(() => {
    setHistoryLoading(true);
    dataImportApi
      .history()
      .then(setHistory)
      .catch(() => toast.error('Nie udało się wczytać historii importów.'))
      .finally(() => setHistoryLoading(false));
  }, [toast]);

  const { run, lines, start, attach, reset } = useImportRun(loadHistory);
  const busy = run.phase === 'starting' || run.phase === 'running';

  useEffect(() => {
    loadSession();
    loadHistory();
  }, [loadSession, loadHistory]);

  // Re-attach once, on the first history load, to a run that is still going.
  useEffect(() => {
    if (reattachChecked.current || historyLoading) return;
    reattachChecked.current = true;
    const running = history.find((r) => r.status === 'running');
    if (running && run.phase === 'idle') attach(running.id, running.started_at, running.dry_run);
  }, [history, historyLoading, run.phase, attach]);

  const days = rangeDays(dateStart, dateEnd);
  const activePreset = PRESETS.find((p) => {
    const [s, e] = p.range();
    return s === dateStart && e === dateEnd;
  })?.id;

  function applyPreset(p: RangePreset) {
    const [s, e] = p.range();
    setDateStart(s);
    setDateEnd(e);
    setFormError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!dateStart || !dateEnd) return setFormError('Wybierz zakres dat.');
    if (dateStart > dateEnd) return setFormError('Data „od” musi być wcześniejsza niż data „do”.');
    setFormError(null);
    const err = await start({ date_start: dateStart, date_end: dateEnd, dry_run: dryRun, keep_xlsx: keepXlsx });
    if (err) setFormError(err);
    else loadHistory();
  }

  const sessionNotReady = session !== null && session.status !== 'active';

  return (
    <div className="refined-page di-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Import wizyt z caldis.pl</h1>
          <p className="page-subtitle">Pobiera rezerwacje z caldis.pl i zapisuje je jako wizyty — z klientami, pracownikami i usługami.</p>
        </div>
        <div className="page-header-actions">
          <ButtonLink variant="ghost" icon="calendar_month" to="/wizyty">
            Przejdź do wizyt
          </ButtonLink>
        </div>
      </header>

      <div className="di-top">
        <form className="form-card di-card di-rise" style={rise(0)} onSubmit={handleSubmit} aria-labelledby="di-form-title" noValidate>
          <div className="di-card-head">
            <h2 id="di-form-title" className="di-card-title">
              Parametry importu
            </h2>
            {days !== null && (
              <span key={days} className="di-range-badge di-pop">
                {days === 1 ? '1 dzień' : `${days} dni`}
              </span>
            )}
          </div>

          <div className="di-presets" role="group" aria-label="Szybki wybór zakresu">
            {PRESETS.map((p) => (
              <button key={p.id} type="button" className="di-chip btn-press" aria-pressed={activePreset === p.id} onClick={() => applyPreset(p)} disabled={busy}>
                {p.label}
              </button>
            ))}
          </div>

          <div className="form-grid di-dates">
            <DatePickerField label="Data od" id="di-date-start" required value={dateStart} onChange={(v) => { setDateStart(v); setFormError(null); }} disabled={busy} />
            <DatePickerField label="Data do" id="di-date-end" required value={dateEnd} onChange={(v) => { setDateEnd(v); setFormError(null); }} disabled={busy} />
          </div>

          <div className="di-options">
            <CheckboxField
              id="di-dry-run"
              label="Tylko próba"
              description="Pobiera i sprawdza dane, ale niczego nie zapisuje w bazie."
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              disabled={busy}
            />
            <CheckboxField
              id="di-keep-xlsx"
              label="Zachowaj plik Excel"
              description="Zostawia na serwerze pobrany z caldis.pl plik XLSX."
              checked={keepXlsx}
              onChange={(e) => setKeepXlsx(e.target.checked)}
              disabled={busy}
            />
          </div>

          {sessionNotReady && (
            <div className="di-callout di-pop" data-tone="warn" role="status">
              <Icon name="warning_amber" />
              <div className="di-callout-body">
                <p>Sesja caldis.pl jest nieaktywna — import najpewniej się nie zaloguje. Odnów ją obok.</p>
              </div>
            </div>
          )}

          <div className="di-form-actions">
            <Button type="submit" variant="primary" icon={dryRun ? 'visibility' : 'download'} isLoading={busy} loadingText={run.phase === 'starting' ? 'Uruchamiam…' : 'Import w toku…'}>
              {dryRun ? 'Uruchom próbę' : 'Importuj wizyty'}
            </Button>
            {formError && (
              <p className="di-form-error di-pop" role="alert">
                {formError}
              </p>
            )}
          </div>
        </form>

        <SessionCard session={session} checkFailed={sessionFailed} checking={sessionChecking} onRecheck={loadSession} style={rise(1)} />
      </div>

      <RunPanel run={run} lines={lines} onClear={reset} style={rise(2)} />

      <ImportHistoryCard rows={history} loading={historyLoading} activeId={run.importId} onReload={loadHistory} style={rise(3)} />

      <ConflictScanSection style={rise(4)} />

      <ScrollJumpButtons />
    </div>
  );
}
