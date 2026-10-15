import { useCallback, useEffect, useRef, useState } from 'react';
import { dataImportApi } from '../../lib/api/dataImport';
import { ApiError } from '../../lib/api/client';
import type { ImportRunStatus, ImportStats, SseEvent } from '../../types/dataImport';

export type LogLevel = 'info' | 'warning' | 'error' | 'progress';

export interface LogLine {
  id: number;
  text: string;
  level: LogLevel;
  at: number;
}

export type RunPhase = 'idle' | 'starting' | 'running' | 'done';

export interface RunState {
  phase: RunPhase;
  importId: number | null;
  dryRun: boolean;
  startedAt: number | null;
  finishedAt: number | null;
  status: ImportRunStatus | null;
  stats: ImportStats;
  errorMessage: string | null;
  /** Set while the EventSource is reconnecting; cleared by the next frame. */
  streamInterrupted: boolean;
  /** True when this run was picked up from history after a reload, not started here. */
  reattached: boolean;
}

const IDLE: RunState = {
  phase: 'idle',
  importId: null,
  dryRun: false,
  startedAt: null,
  finishedAt: null,
  status: null,
  stats: {},
  errorMessage: null,
  streamInterrupted: false,
  reattached: false,
};

/** Keeps the DOM bounded on a very chatty import — the panel is a live tail, not an archive. */
const MAX_LINES = 1500;

export interface StartPayload {
  date_start: string;
  date_end: string;
  dry_run: boolean;
  keep_xlsx: boolean;
}

/**
 * One caldis.pl import run, end to end: POST /api/import/start, then the SSE
 * stream at /api/import/<id>/stream until its `done` frame. `attach()` also
 * picks up a run that is already going (found as `running` in the history
 * after a page reload), which the old page couldn't do — it simply lost the
 * log. The stream is a native EventSource (the shared `api` client is fetch,
 * not streaming); it's a GET, so it needs no CSRF header, only the cookie.
 */
export function useImportRun(onFinished: () => void) {
  const [run, setRun] = useState<RunState>(IDLE);
  const [lines, setLines] = useState<LogLine[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const interruptedRef = useRef(false);
  const lineSeq = useRef(0);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  const pushLine = useCallback((text: string, level: LogLevel) => {
    const line: LogLine = { id: ++lineSeq.current, text, level, at: Date.now() };
    setLines((prev) => (prev.length >= MAX_LINES ? [...prev.slice(prev.length - MAX_LINES + 1), line] : [...prev, line]));
  }, []);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  useEffect(() => closeStream, [closeStream]);

  const handleEvent = useCallback(
    (event: SseEvent) => {
      if (event.type === 'log') {
        pushLine(event.message, event.level ?? 'info');
      } else if (event.type === 'stats') {
        setRun((r) => ({ ...r, stats: event.stats }));
      } else if (event.type === 'status') {
        setRun((r) => ({ ...r, status: event.status }));
      } else if (event.type === 'done') {
        closeStream();
        setRun((r) => {
          const status = event.status || r.status || 'unknown';
          return {
            ...r,
            phase: 'done',
            status,
            stats: event.stats && Object.keys(event.stats).length > 0 ? event.stats : r.stats,
            errorMessage: event.error_message || null,
            finishedAt: Date.now(),
            streamInterrupted: false,
          };
        });
        pushLine(`— Koniec (${event.status || 'unknown'}) —`, event.status === 'completed' ? 'info' : 'error');
        window.setTimeout(() => onFinishedRef.current(), 600);
      }
    },
    [closeStream, pushLine],
  );

  const openStream = useCallback(
    (importId: number) => {
      closeStream();
      const es = new EventSource(`/api/import/${importId}/stream`, { withCredentials: true });
      esRef.current = es;
      interruptedRef.current = false;
      es.onmessage = (evt) => {
        if (interruptedRef.current) {
          interruptedRef.current = false;
          setRun((r) => ({ ...r, streamInterrupted: false }));
        }
        try {
          handleEvent(JSON.parse(evt.data) as SseEvent);
        } catch {
          /* malformed frame — ignored, same as the original page */
        }
      };
      es.onerror = () => {
        // EventSource reconnects by itself; only say so once per outage.
        if (esRef.current !== es || interruptedRef.current) return;
        interruptedRef.current = true;
        pushLine('Połączenie z logiem przerwane — ponawiam…', 'warning');
        setRun((r) => ({ ...r, streamInterrupted: true }));
      };
    },
    [closeStream, handleEvent, pushLine],
  );

  /** Returns an error message for the form, or null when the run started. */
  const start = useCallback(
    async (payload: StartPayload): Promise<string | null> => {
      closeStream();
      lineSeq.current = 0;
      setLines([]);
      setRun({ ...IDLE, phase: 'starting', dryRun: payload.dry_run, startedAt: Date.now(), status: 'running' });
      pushLine(payload.dry_run ? '— Start próby (bez zapisu do bazy) —' : '— Start importu —', 'info');
      try {
        const { import_id } = await dataImportApi.start(payload);
        setRun((r) => ({ ...r, phase: 'running', importId: import_id }));
        openStream(import_id);
        return null;
      } catch (err) {
        setRun(IDLE);
        setLines([]);
        if (err instanceof ApiError && err.status === 409) return 'Import już trwa — poczekaj na jego zakończenie.';
        return err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem.';
      }
    },
    [closeStream, openStream, pushLine],
  );

  const attach = useCallback(
    (importId: number, startedAtIso: string | null, dryRun: boolean) => {
      lineSeq.current = 0;
      setLines([]);
      setRun({
        ...IDLE,
        phase: 'running',
        importId,
        dryRun,
        status: 'running',
        startedAt: startedAtIso ? new Date(startedAtIso).getTime() : Date.now(),
        reattached: true,
      });
      pushLine(`— Podłączono do trwającego importu #${importId} (wcześniejsze wpisy logu nie są dostępne) —`, 'progress');
      openStream(importId);
    },
    [openStream, pushLine],
  );

  const reset = useCallback(() => {
    closeStream();
    setRun(IDLE);
    setLines([]);
  }, [closeStream]);

  return { run, lines, start, attach, reset };
}
