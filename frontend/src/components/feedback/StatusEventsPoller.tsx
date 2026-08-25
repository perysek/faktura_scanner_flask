import { useEffect, useRef } from 'react';
import { appointmentsApi } from '../../lib/api/appointments';
import { useToast } from './ToastProvider';
import { useAuth } from '../../contexts/AuthContext';

const STATUS_LABELS: Record<string, string> = {
  in_progress: 'W trakcie',
  completed: 'Zakończona',
  cancelled: 'Anulowana',
};

const POLL_INTERVAL_MS = 5000;

/**
 * Global real-time toast when an appointment's status changes anywhere in
 * the app (another tab, another user, the client-facing `/rate`/`/visit`
 * pages) — dobudowane 2026-08-25, ported from `templates/base.html`'s "P10c"
 * inline script, which is still live for the legacy Jinja pages (same
 * `GET /api/appointments/status-events?since=` endpoint, same
 * `since`/`server_time` catch-up contract, so the two poll independently
 * without stepping on each other).
 *
 * Renders nothing — mount once near the app root, inside both AuthProvider
 * (gates polling on a real session, matching base.html's
 * `current_user.is_authenticated` guard) and ToastProvider (delivers via
 * `toast.info`, which already caps at 3 stacked + auto-dismiss — no need to
 * reimplement base.html's DOM-fallback toast bookkeeping here).
 *
 * Paused while the tab is hidden (network/battery), with an immediate
 * catch-up poll on return — `since=` covers whatever gap that leaves, so no
 * event is missed, just delayed.
 */
export function StatusEventsPoller() {
  const auth = useAuth();
  const toast = useToast();
  // Set once at mount, not per-poll — matches the legacy script's "only
  // surface events from after this page loaded" intent.
  const lastPollRef = useRef<string>(new Date().toISOString());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!auth.user) return;

    async function poll() {
      try {
        const data = await appointmentsApi.statusEvents(lastPollRef.current);
        lastPollRef.current = data.server_time;
        data.events.forEach((evt) => {
          const label = STATUS_LABELS[evt.new_status] ?? evt.new_status;
          toast.info(`Wizyta — ${evt.client_name ?? '—'}: status → "${label}"`);
        });
      } catch {
        /* non-critical — silence network errors, same as the legacy poller */
      }
    }

    function start() {
      if (timerRef.current) return;
      timerRef.current = setInterval(poll, POLL_INTERVAL_MS);
    }
    function stop() {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    function handleVisibilityChange() {
      if (document.hidden) {
        stop();
      } else {
        poll(); // immediate catch-up
        start();
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);
    if (!document.hidden) start();

    return () => {
      stop();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.user, toast]);

  return null;
}
