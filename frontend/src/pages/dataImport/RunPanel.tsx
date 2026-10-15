import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { RUN_STATUS, STAT_TILES, formatDuration, prefersReducedMotion, useCountUp } from './dataImportShared';
import type { LogLine, RunState } from './useImportRun';

function StatTile({ label, tone, value, index }: { label: string; tone: string; value: number; index: number }) {
  const shown = useCountUp(value);
  return (
    <div className="di-tile" data-tone={tone} style={{ '--i': index } as CSSProperties}>
      <span className="di-tile-value">{shown.toLocaleString('pl-PL')}</span>
      <span className="di-tile-label">{label}</span>
    </div>
  );
}

function useElapsed(run: RunState): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (run.phase !== 'running' && run.phase !== 'starting') return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [run.phase]);
  if (!run.startedAt) return 0;
  return (run.finishedAt ?? now) - run.startedAt;
}

const LEVEL_LABEL: Record<LogLine['level'], string> = { info: 'info', warning: 'uwaga', error: 'błąd', progress: 'postęp' };

interface RunPanelProps {
  run: RunState;
  lines: LogLine[];
  onClear: () => void;
  style?: CSSProperties;
}

/**
 * Przebieg importu — the live view of one run: status + elapsed time, an
 * indeterminate bar while the scraper works, five rolling counters fed by the
 * SSE `stats` frames, and the tail of the log.
 *
 * The log follows new lines only while the reader is at its bottom; scrolling
 * up to read something pauses that, and a "Nowe wpisy" chip jumps back down.
 */
export function RunPanel({ run, lines, onClear, style }: RunPanelProps) {
  const logRef = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const lastCount = useRef(lines.length);
  const elapsed = useElapsed(run);

  const live = run.phase === 'running' || run.phase === 'starting';
  const status = run.status ? RUN_STATUS[run.status] : null;

  useLayoutEffect(() => {
    const added = lines.length - lastCount.current;
    lastCount.current = lines.length;
    const el = logRef.current;
    if (!el) return;
    if (follow) {
      el.scrollTop = el.scrollHeight;
      setUnseen(0);
    } else if (added > 0) {
      setUnseen((n) => n + added);
    }
  }, [lines, follow]);

  function handleLogScroll() {
    const el = logRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.clientHeight - el.scrollTop < 24;
    if (atBottom !== follow) setFollow(atBottom);
    if (atBottom) setUnseen(0);
  }

  function jumpToEnd() {
    const el = logRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    setFollow(true);
    setUnseen(0);
  }

  if (run.phase === 'idle') {
    return (
      <section className="form-card di-card di-rise" style={style} aria-labelledby="di-run-title">
        <div className="di-card-head">
          <h2 id="di-run-title" className="di-card-title">
            Przebieg importu
          </h2>
        </div>
        <div className="di-empty animate-fade-in">
          <span className="di-empty-icon" aria-hidden="true">
            <Icon name="terminal" />
          </span>
          <p className="di-empty-title">Brak aktywnego importu</p>
          <p className="di-empty-copy">Wybierz zakres dat i uruchom import — postęp i log pojawią się tutaj na żywo.</p>
        </div>
      </section>
    );
  }

  return (
    <section
      className="form-card di-card di-run di-rise"
      style={style}
      data-tone={live ? 'live' : status?.tone}
      aria-labelledby="di-run-title"
      aria-busy={live}
    >
      <div className="di-card-head">
        <div className="di-run-heading">
          <h2 id="di-run-title" className="di-card-title">
            {run.importId ? `Import #${run.importId}` : 'Uruchamiam import…'}
          </h2>
          {status && (
            <span key={run.status} className="di-pill di-pop" data-tone={status.tone} data-live={live ? 'true' : undefined}>
              <span className="di-pill-dot" aria-hidden="true" />
              {status.label}
            </span>
          )}
          {run.dryRun && <span className="di-tag">Próba — bez zapisu</span>}
        </div>
        <div className="di-run-meta">
          <span className="di-elapsed" aria-label="Czas trwania">
            <Icon name="schedule" /> {formatDuration(elapsed)}
          </span>
          {!live && (
            <Button variant="ghost" small icon="close" onClick={onClear} aria-label="Wyczyść panel przebiegu">
              Wyczyść
            </Button>
          )}
        </div>
      </div>

      <div className="di-progress" data-state={live ? 'live' : status?.tone ?? 'muted'} aria-hidden="true">
        <span className="di-progress-bar" />
      </div>

      <div className="di-tiles">
        {STAT_TILES.map((t, i) => (
          <StatTile key={t.key} label={t.label} tone={t.tone} value={t.pick(run.stats)} index={i} />
        ))}
      </div>

      {run.errorMessage && (
        <div className="di-callout di-pop" data-tone="bad" role="alert">
          <Icon name="error_outline" />
          <div className="di-callout-body">
            <p>{run.errorMessage}</p>
          </div>
        </div>
      )}

      <div className="di-log-wrap">
        <div ref={logRef} className="di-log" onScroll={handleLogScroll} role="log" aria-label="Log importu" tabIndex={0}>
          {lines.map((l) => (
            <div key={l.id} className="di-log-line" data-level={l.level}>
              <span className="di-log-time">{new Date(l.at).toLocaleTimeString('pl-PL', { hour12: false })}</span>
              <span className="di-log-level">{LEVEL_LABEL[l.level]}</span>
              <span className="di-log-text">{l.text}</span>
            </div>
          ))}
          {live && <div className="di-log-caret" aria-hidden="true" />}
        </div>
        {unseen > 0 && (
          <button type="button" className="di-log-jump di-pop" onClick={jumpToEnd}>
            <Icon name="arrow_downward" /> Nowe wpisy ({unseen})
          </button>
        )}
      </div>
    </section>
  );
}
