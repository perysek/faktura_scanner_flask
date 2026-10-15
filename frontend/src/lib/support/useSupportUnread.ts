import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useToast } from '../../components/feedback/ToastProvider';
import { useAuth } from '../../contexts/AuthContext';
import { supportApi } from '../api/support';

const POLL_MS = 60_000;

/**
 * How many of the user's support conversations carry an administrator answer they
 * haven't read (plan 261013 §8). Polled every minute while the tab is visible and on
 * every route change; a rise after the first load pops a toast, so an answer is
 * noticed even with the sidebar collapsed or on a phone.
 */
export function useSupportUnread() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const toast = useToast();
  const [unread, setUnread] = useState(0);
  const previous = useRef<number | null>(null);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const { unread: count } = await supportApi.unreadCount();
      if (previous.current !== null && count > previous.current) {
        toastRef.current.info('Administrator odpisał na Twoje zgłoszenie — zobacz przy ikonie telefonu.', 8000);
      }
      previous.current = count;
      setUnread(count);
    } catch {
      /* badge is best-effort; the next poll retries */
    }
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh, pathname]);

  useEffect(() => {
    if (!user) return undefined;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') refresh();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh, user]);

  return { unread, refresh };
}
