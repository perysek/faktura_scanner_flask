import { useRef } from 'react';
import type { ReactNode } from 'react';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useFocusTrap } from '../../lib/a11y/useFocusTrap';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  size?: 'medium' | 'large';
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * Generic content modal — `.modal-*` classes (components.css), same chrome
 * `ConfirmProvider` uses internally. DESIGN.md §8.3: `Modals.show()` has no
 * ready-made 1:1 React component — every call site is judged individually;
 * this is the shared shell for the ones that turn out to be a real custom
 * modal (not a confirm/cancel), first needed by the Sprzedawcy PDF-passwords
 * panel and the NIP-conflict picker (Faza 2).
 */
export function Modal({ isOpen, onClose, title, size = 'medium', children, footer }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useEscapeClaim(isOpen);

  useFocusTrap(isOpen, panelRef);

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <div ref={panelRef} className={`modal-content modal-size-${size}`} role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-header">
          <h3 id="modal-title">{title}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Zamknij">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ width: '1.125rem', height: '1.125rem' }}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
