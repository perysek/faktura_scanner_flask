import { useEffect, useRef, useState } from 'react';

/**
 * Hides the caller while the page scrolls down past `revealAfterPx`, shows
 * it again the moment the user scrolls up — for a `position: fixed` bottom
 * bar that would otherwise sit permanently over page content on a phone.
 * No existing bar in this app did this before (confirmed against
 * users-list-page / user-view / user-edit, which all use a plain
 * `position: sticky` bar with no scroll-direction behavior) — this is a new
 * pattern, not a port of one. `delayMs` debounces the scroll handler so a
 * few pixels of jitter don't flicker the bar in and out.
 */
export function useHideOnScroll(delayMs = 120, revealAfterPx = 80): boolean {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    lastY.current = window.scrollY;
    function onScroll() {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const y = window.scrollY;
        const delta = y - lastY.current;
        if (Math.abs(delta) > 8) {
          setHidden(delta > 0 && y > revealAfterPx);
          lastY.current = y;
        }
      }, delayMs);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [delayMs, revealAfterPx]);

  return hidden;
}
