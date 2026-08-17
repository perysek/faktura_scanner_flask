import { useEffect } from 'react';
import type { RefObject } from 'react';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Traps Tab navigation inside a container while active and returns focus to
 * a specified element (or whatever had focus before the trap opened) on
 * close — DESIGN.md §11.3. Required for any full-overlay UI (modal, drawer);
 * do not let Tab escape into the page behind an open overlay (WCAG 2.4.3).
 *
 * On activation, focus moves to the first focusable element inside the
 * container — for the confirm dialog that's Cancel (DESIGN.md §8.2: "focus
 * starts on Cancel, the safe default"), simply because it renders first.
 */
export function useFocusTrap(
  active: boolean,
  containerRef: RefObject<HTMLElement | null>,
  returnFocusRef?: RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    function getFocusable(): HTMLElement[] {
      if (!container) return [];
      return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
        (el) => el.offsetParent !== null,
      );
    }

    const initial = getFocusable();
    (initial[0] ?? container).focus();

    function handleKeydown(event: KeyboardEvent) {
      if (event.key !== 'Tab') return;
      const items = getFocusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', handleKeydown);
    return () => {
      document.removeEventListener('keydown', handleKeydown);
      const returnTo = returnFocusRef?.current ?? previouslyFocused;
      returnTo?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);
}
