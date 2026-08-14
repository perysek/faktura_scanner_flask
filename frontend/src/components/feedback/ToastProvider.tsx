import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Icon } from '../../lib/icons/Icon';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  show: (message: string, type?: ToastType, duration?: number) => void;
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
  clear: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const MAX_TOASTS = 3;
// DESIGN.md §8.1 says 4000ms; today's static/js/notifications.js uses 3000ms —
// deliberately following DESIGN.md, see implementation-log.md Decision D5.
const DEFAULT_DURATION = 4000;

const ICON_BY_TYPE: Record<ToastType, string> = {
  success: 'check_circle',
  error: 'error',
  warning: 'warning',
  info: 'info',
};

/**
 * Toast notification system — DESIGN.md §8.1. Mounted once near the app
 * root; consume via `useToast()`. Never instantiate a second toast stack.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (message: string, type: ToastType = 'info', duration: number = DEFAULT_DURATION) => {
      const id = ++nextId.current;
      // Max 3 stacked; oldest is silently dropped when a 4th arrives (§8.1).
      setToasts((current) => {
        const trimmed = current.length >= MAX_TOASTS ? current.slice(current.length - MAX_TOASTS + 1) : current;
        return [...trimmed, { id, type, message }];
      });
      if (duration > 0) {
        setTimeout(() => remove(id), duration);
      }
    },
    [remove],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      show,
      success: (message, duration) => show(message, 'success', duration),
      error: (message, duration) => show(message, 'error', duration),
      warning: (message, duration) => show(message, 'warning', duration),
      info: (message, duration) => show(message, 'info', duration),
      clear: () => setToasts([]),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live="polite" so screen readers announce new toasts without
          interrupting (§8.1). Positioned fixed bottom-right via .toast-stack. */}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast-${toast.type}`} role="status">
            <Icon name={ICON_BY_TYPE[toast.type]} />
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-ink)' }}>
                {toast.message}
              </p>
            </div>
            <button
              type="button"
              className="toast-close"
              aria-label="Zamknij powiadomienie"
              onClick={() => remove(toast.id)}
            >
              <Icon name="close" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}
