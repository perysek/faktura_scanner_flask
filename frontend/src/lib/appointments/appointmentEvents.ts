import { useEffect, useRef } from 'react';

/** "Visits changed somewhere" bus — anything on screen that is derived from
 * visits (calendar blocks, the income footers) subscribes instead of each
 * mutation site having to know who is listening.
 *
 * Emitted from exactly two places: `lib/api/client.ts` after ANY successful
 * non-GET under `/api/appointments` (so every status change, edit, completion,
 * reschedule, delete/restore and past-visit settlement in this tab is covered
 * without touching its call site), and `StatusEventsPoller` when the server
 * reports status changes made elsewhere (another user, another tab, a client's
 * SMS reply). */
const EVENT = 'appointments:changed';

export function notifyAppointmentsChanged(): void {
  window.dispatchEvent(new Event(EVENT));
}

/** Calls `handler` after the bus goes quiet for `debounceMs` — a bulk save of a
 * dozen visits fires a dozen events but should cause one refetch. */
export function useAppointmentsChanged(handler: () => void, debounceMs = 300): void {
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  });

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onChange = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => handlerRef.current(), debounceMs);
    };
    window.addEventListener(EVENT, onChange);
    return () => {
      window.removeEventListener(EVENT, onChange);
      if (timer) clearTimeout(timer);
    };
  }, [debounceMs]);
}
