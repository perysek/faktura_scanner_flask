import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Icon } from '../../lib/icons/Icon';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

/** One inline action on a toast — e.g. "Cofnij" after a soft delete
 * (gui-components/undo-toast.md). The toast closes once it resolves. */
export interface ToastAction {
  label: string;
  onClick: () => void | Promise<void>;
}

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
  action?: ToastAction;
}

interface ToastContextValue {
  show: (message: string, type?: ToastType, duration?: number, action?: ToastAction) => void;
  success: (message: string, duration?: number, action?: ToastAction) => void;
  error: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
  info: (message: string, duration?: number, action?: ToastAction) => void;
  clear: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const MAX_TOASTS = 3;
// DESIGN.md §8.1 says 4000ms; today's static/js/notifications.js uses 3000ms —
// deliberately following DESIGN.md, see implementation-log.md Decision D5.
const DEFAULT_DURATION = 4000;
/** A toast with an action stays up long enough to reach it (undo-toast.md: 8s). */
const ACTION_DURATION = 8000;

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
    (message: string, type: ToastType = 'info', duration?: number, action?: ToastAction) => {
      const id = ++nextId.current;
      const ms = duration ?? (action ? ACTION_DURATION : DEFAULT_DURATION);
      // Max 3 stacked; oldest is silently dropped when a 4th arrives (§8.1).
      setToasts((current) => {
        const trimmed = current.length >= MAX_TOASTS ? current.slice(current.length - MAX_TOASTS + 1) : current;
        return [...trimmed, { id, type, message, action }];
      });
      if (ms > 0) {
        setTimeout(() => remove(id), ms);
      }
    },
    [remove],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      show,
      success: (message, duration, action) => show(message, 'success', duration, action),
      error: (message, duration) => show(message, 'error', duration),
      warning: (message, duration) => show(message, 'warning', duration),
      info: (message, duration, action) => show(message, 'info', duration, action),
      clear: () => setToasts([]),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live="polite" so screen readers announce new toasts without
          interrupting (§8.1). Positioned fixed bottom-right via .toast-stack;
          on phones it docks full-width above the bottom bars (P1, mobile.css). */}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast-${toast.type}`} role="status">
            <Icon name={ICON_BY_TYPE[toast.type]} />
            <div style={{ flex: 1 }}>
              <p className="toast-message">{toast.message}</p>
            </div>
            {toast.action && <ToastActionButton action={toast.action} onDone={() => remove(toast.id)} />}
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

function ToastActionButton({ action, onDone }: { action: ToastAction; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      className="toast-action"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await action.onClick();
        } finally {
          onDone();
        }
      }}
    >
      {action.label}
    </button>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within a ToastProvider');
  return ctx;
}
