import { useEffect, useRef, useState } from 'react';

/**
 * Hides the caller while the page scrolls down past `revealAfterPx`, shows
 * it again the moment the user scrolls up — for a `position: sticky` bottom
 * bar the caller wants to temporarily slide out of the way instead of
 * sitting permanently over content while scrolling.
 *
 * Listens on `#main-content` (AppShell.tsx's `<main>`), not `window`: this
 * app's shell is a fixed-height flex frame where `<main>` owns the only
 * real scroll region (`.app-shell-content { overflow: auto }`, unconditional
 * — the window/document itself never scrolls here). A `window` scroll
 * listener would simply never fire. Falls back to `window` if that element
 * isn't mounted yet, so the hook still degrades gracefully outside AppShell.
 *
 * `delayMs` debounces the scroll handler so a few pixels of jitter don't
 * flicker the bar in and out.
 */
export function useHideOnScroll(delayMs = 120, revealAfterPx = 80): boolean {
  const [hidden, setHidden] = useState(false);
  const lastY = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const scroller: HTMLElement | Window = document.getElementById('main-content') ?? window;
    const getY = () => (scroller instanceof Window ? scroller.scrollY : scroller.scrollTop);
    lastY.current = getY();

    function onScroll() {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const y = getY();
        const delta = y - lastY.current;
        if (Math.abs(delta) > 8) {
          setHidden(delta > 0 && y > revealAfterPx);
          lastY.current = y;
        }
      }, delayMs);
    }

    scroller.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [delayMs, revealAfterPx]);

  return hidden;
}
