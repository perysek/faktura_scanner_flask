import { useEffect } from 'react';

/**
 * Escape-key coordination — DESIGN.md §11.2, "the single most important
 * non-obvious pattern in this codebase". Multiple dismissible layers (a
 * popover, a modal, a mobile drawer, a page-level "back" binding) can be
 * mounted simultaneously. Without coordination, opening a small popover
 * while on a form and pressing Escape would close the popover AND navigate
 * away in the same keystroke.
 *
 * A tiny module-level depth counter is the fix:
 * - Any dismissible layer with its own open/closed state calls
 *   `useEscapeClaim(isOpen)` — this reserves the Escape key while open. It
 *   does NOT itself close anything; the layer's own Escape handler still has
 *   to exist (and should call `event.stopPropagation()` when it handles the
 *   key, as defense in depth alongside the claim).
 * - Any page-level "Escape = go back / cancel" binding uses
 *   `useEscapeAction(action, enabled)`, which checks `isEscapeClaimed()`
 *   first and silently no-ops if something more specific already owns the
 *   key.
 *
 * Rule: "one Escape closes one layer." Any new popover, dropdown, or
 * modal-like UI MUST call `useEscapeClaim` while open — skipping this is a
 * correctness bug, not a style nit.
 */
let claimDepth = 0;

export function isEscapeClaimed(): boolean {
  return claimDepth > 0;
}

export function useEscapeClaim(isOpen: boolean): void {
  useEffect(() => {
    if (!isOpen) return;
    claimDepth += 1;
    return () => {
      claimDepth -= 1;
    };
  }, [isOpen]);
}

/**
 * `guardTyping` (default true) skips the action while focus is inside an
 * INPUT/TEXTAREA/SELECT — ported from the original app's create/edit Escape
 * handlers (e.g. templates/employees/create.html), which never let Escape
 * discard an in-progress form field. Pass `false` for bindings that should
 * fire regardless (rare — most "go back"/"cancel" actions want the guard).
 */
export function useEscapeAction(action: () => void, enabled = true, guardTyping = true): void {
  useEffect(() => {
    if (!enabled) return;
    function handleKeydown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      if (isEscapeClaimed()) return;
      if (guardTyping) {
        const tag = (event.target as HTMLElement | null)?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      }
      action();
    }
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  }, [action, enabled, guardTyping]);
}
