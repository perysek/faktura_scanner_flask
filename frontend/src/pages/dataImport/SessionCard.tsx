import { useState } from 'react';
import type { CSSProperties } from 'react';
import { dataImportApi } from '../../lib/api/dataImport';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { SESSION_MAX_AGE_DAYS } from './dataImportShared';
import type { SessionStatusResponse } from '../../types/dataImport';

/** The command routes/import_routes.py's 503 tells a headless server to run once. */
const MANUAL_COMMAND = 'python scripts/import_appointments_playwright.py --headed';

const STATE_COPY = {
  active: { label: 'Aktywna', tone: 'ok' },
  expired: { label: 'Wygasła', tone: 'warn' },
  missing: { label: 'Brak sesji', tone: 'bad' },
} as const;

interface SessionCardProps {
  session: SessionStatusResponse | null;
  checkFailed: boolean;
  checking: boolean;
  onRecheck: () => void;
  style?: CSSProperties;
}

function plDays(n: number): string {
  return n === 1 ? '1 dzień' : `${n} dni`;
}

/**
 * Sesja caldis.pl — what the scraper will log in with. The backend keeps a
 * Playwright storage-state file and calls it 'expired' purely by age
 * (SESSION_MAX_AGE_DAYS), so the meter shows how much of that window is left.
 *
 * "Zaloguj ponownie" opens a HEADED browser on the server machine and waits
 * up to 2 minutes for someone to log in there; on a headless Linux deploy the
 * backend answers 503 straight away, and the card then shows the one-off
 * console command instead (copyable).
 */
export function SessionCard({ session, checkFailed, checking, onRecheck, style }: SessionCardProps) {
  const toast = useToast();
  const [reconnecting, setReconnecting] = useState(false);
  const [headless, setHeadless] = useState(false);

  async function handleReconnect() {
    setReconnecting(true);
    setHeadless(false);
    try {
      await dataImportApi.reconnectSession();
      toast.success('Sesja caldis.pl odnowiona.');
      onRecheck();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) setHeadless(true);
      else toast.error(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem.');
    } finally {
      setReconnecting(false);
    }
  }

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(MANUAL_COMMAND);
      toast.success('Skopiowano polecenie.');
    } catch {
      toast.error('Nie udało się skopiować — zaznacz polecenie ręcznie.');
    }
  }

  const state = session ? STATE_COPY[session.status] : null;
  const age = session?.age_days ?? null;
  const left = age === null ? null : Math.max(0, SESSION_MAX_AGE_DAYS - age);
  const fill = left === null ? 0 : left / SESSION_MAX_AGE_DAYS;
  const meterTone = fill > 0.33 ? 'ok' : fill > 0 ? 'warn' : 'bad';

  return (
    <section className="form-card di-card di-rise" style={style} aria-labelledby="di-session-title">
      <div className="di-card-head">
        <h2 id="di-session-title" className="di-card-title">
          Sesja caldis.pl
        </h2>
        <Button variant="ghost" small icon="refresh" onClick={onRecheck} isLoading={checking} loadingText="Sprawdzam…" aria-label="Sprawdź stan sesji ponownie">
          Sprawdź
        </Button>
      </div>

      <div className="di-session-status" aria-live="polite">
        {checkFailed ? (
          <span className="di-pill" data-tone="muted">
            <span className="di-pill-dot" aria-hidden="true" />
            Nie udało się sprawdzić
          </span>
        ) : state ? (
          <span key={session?.status} className="di-pill di-pop" data-tone={state.tone} data-live={session?.status === 'active' ? 'true' : undefined}>
            <span className="di-pill-dot" aria-hidden="true" />
            {state.label}
          </span>
        ) : (
          <span className="di-pill skeleton di-pill-skeleton" aria-label="Sprawdzanie sesji" />
        )}
      </div>

      {session && age !== null && left !== null && (
        <div className="di-meter-block">
          <div
            className="di-meter"
            data-tone={meterTone}
            role="meter"
            aria-label="Pozostała ważność sesji"
            aria-valuemin={0}
            aria-valuemax={SESSION_MAX_AGE_DAYS}
            aria-valuenow={Math.round(left)}
            aria-valuetext={`${plDays(Math.round(left))} z ${SESSION_MAX_AGE_DAYS}`}
          >
            <span className="di-meter-fill" style={{ transform: `scaleX(${fill})` }} />
          </div>
          <p className="di-meter-caption">
            {session.status === 'active' ? (
              <>
                Zapisana {plDays(Math.round(age))} temu · ważna jeszcze ok. <strong>{plDays(Math.round(left))}</strong>
              </>
            ) : (
              <>Zapisana {plDays(Math.round(age))} temu — po {SESSION_MAX_AGE_DAYS} dniach import jej nie użyje.</>
            )}
          </p>
        </div>
      )}

      {session?.status === 'missing' && <p className="di-muted-copy">Na serwerze nie ma zapisanej sesji, więc import nie zaloguje się do caldis.pl.</p>}

      <div className="di-session-actions">
        <Button
          variant={session && session.status !== 'active' ? 'primary' : 'secondary'}
          small={session?.status === 'active'}
          icon="lock"
          isLoading={reconnecting}
          loadingText="Czekam na logowanie (do 2 min)…"
          onClick={handleReconnect}
        >
          {session?.status === 'active' ? 'Zaloguj ponownie' : 'Odnów sesję'}
        </Button>
      </div>

      {headless && (
        <div className="di-callout di-pop" data-tone="warn" role="status">
          <Icon name="terminal" />
          <div className="di-callout-body">
            <p>Serwer nie ma ekranu, więc nie otworzy okna logowania. Uruchom raz na serwerze:</p>
            <div className="di-command">
              <code>{MANUAL_COMMAND}</code>
              <Button variant="ghost" small icon="content_paste" onClick={copyCommand} aria-label="Skopiuj polecenie">
                Kopiuj
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
