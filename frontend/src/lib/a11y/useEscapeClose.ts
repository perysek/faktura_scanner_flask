import { useEffect } from 'react';
import { useEscapeClaim } from './escapeScope';

/**
 * Standard "this layer owns Escape while open" binding — DESIGN.md §11.2.
 * Claims the key (`useEscapeClaim`) so page-level `useEscapeAction`/
 * `useEscapeBack` bindings correctly back off (`isEscapeClaimed()`), AND
 * closes itself unconditionally on Escape while open — a layer never
 * gates its own dismissal behind the claim check, only other layers do.
 * Extracted from `ConfirmProvider`'s original inline effect (identical
 * logic); also used by any inline dismissible section that isn't a full
 * `Modal` — e.g. EmployeeDetailPage's "Dodaj usługę" form, where without
 * this the page's own `useEscapeBack` would otherwise navigate away
 * mid-edit on the very first Escape press.
 */
export function useEscapeClose(isOpen: boolean, onClose: () => void): void {
  useEscapeClaim(isOpen);
  useEffect(() => {
    if (!isOpen) return;
    function handleKeydown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      onClose();
    }
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  }, [isOpen, onClose]);
}
