import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useFocusTrap } from '../../lib/a11y/useFocusTrap';

export type ConfirmType = 'danger' | 'warning' | 'info';

export interface ConfirmOptions {
  title: string;
  message: string;
  type?: ConfirmType;
  confirmText?: string;
  cancelText?: string;
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (value: boolean) => void;
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

const ICON_BY_TYPE: Record<ConfirmType, string> = {
  danger: 'warning',
  warning: 'warning_amber',
  info: 'info',
};

/**
 * Promise-based confirm dialog — DESIGN.md §8.2. `const ok = await confirm({...})`.
 * Use for EVERY destructive/consequential action; never the browser's native
 * confirm()/alert() (§16 Forbidden). Mounted once near the app root; consume
 * via `useConfirm()`.
 *
 * A11y: role="dialog", aria-modal, aria-labelledby → title; focus starts on
 * Cancel (renders first in the footer, so useFocusTrap's "first focusable"
 * picks it up automatically); full focus trap while open; closes on Escape
 * or backdrop click; returns focus to the triggering element on close
 * (useFocusTrap handles both via its own effect cleanup).
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const isOpen = pending !== null;

  useEscapeClaim(isOpen);
  useFocusTrap(isOpen, panelRef);

  const close = useCallback(
    (result: boolean) => {
      pending?.resolve(result);
      setPending(null);
    },
    [pending],
  );

  // The layer's own Escape handler — useEscapeClaim above only reserves the
  // key so nothing else fires; this is what actually closes the dialog.
  useEffect(() => {
    if (!isOpen) return;
    function handleKeydown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      close(false);
    }
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  }, [isOpen, close]);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setPending({ ...options, resolve });
    });
  }, []);

  const value = useMemo<ConfirmContextValue>(() => ({ confirm }), [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending && (
        <div
          className="modal-overlay"
          onClick={(event) => {
            if (event.target === event.currentTarget) close(false);
          }}
        >
          <div
            ref={panelRef}
            className="modal-content"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
          >
            <div className="modal-body" style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
              <div className={`cm-icon-badge cm-${pending.type ?? 'danger'}`}>
                <Icon name={ICON_BY_TYPE[pending.type ?? 'danger']} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3
                  id="confirm-dialog-title"
                  style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: 'var(--color-ink)' }}
                >
                  {pending.title}
                </h3>
                <p style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--color-ink-muted)', lineHeight: 1.5 }}>
                  {pending.message}
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="cm-btn cm-btn-cancel" onClick={() => close(false)}>
                {pending.cancelText ?? 'Anuluj'}
              </button>
              <button
                type="button"
                className={`cm-btn cm-btn-confirm cm-${pending.type ?? 'danger'}`}
                onClick={() => close(true)}
              >
                {pending.confirmText ?? 'Potwierdź'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): (options: ConfirmOptions) => Promise<boolean> {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within a ConfirmProvider');
  return ctx.confirm;
}
