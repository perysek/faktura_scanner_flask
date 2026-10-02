import { useEffect, useLayoutEffect, useRef, useState } from 'react';

type Timer = ReturnType<typeof setTimeout>;

/**
 * The scroll-direction logic behind `useHideOnScroll`, with no React or DOM in it (the scroll position
 * and the clock are injected), so it can be tested on its own.
 *
 * A scroll that moves down past `revealAfterPx` hides; one that moves up shows. The decision is taken
 * `delayMs` after the last scroll event, and a few pixels of jitter (<= 8px) are ignored.
 *
 * `setPaused(true)` suspends it: scroll events are ignored and a pending decision is dropped. That is
 * for scrolling the PAGE did not ask for — the A–Z index jumps the list up and down under a held
 * finger, and read as scrolling each jump would flip the bar every ~120ms. Resuming forgets the
 * distance scrolled meanwhile (so the jump never counts as a gesture) and shows the element.
 */
export function createHideOnScroll(
  getY: () => number,
  onChange: (hidden: boolean) => void,
  delayMs = 120,
  revealAfterPx = 80,
  schedule: (fn: () => void, ms: number) => Timer = setTimeout,
  cancel: (t: Timer) => void = clearTimeout,
) {
  let lastY = getY();
  let timer: Timer | null = null;
  let paused = false;

  function drop() {
    if (timer) cancel(timer);
    timer = null;
  }

  return {
    onScroll() {
      if (paused) return;
      drop();
      timer = schedule(() => {
        timer = null;
        const y = getY();
        const delta = y - lastY;
        if (Math.abs(delta) > 8) {
          onChange(delta > 0 && y > revealAfterPx);
          lastY = y;
        }
      }, delayMs);
    },
    setPaused(next: boolean) {
      if (next === paused) return;
      paused = next;
      drop();
      lastY = getY();
      if (!next) onChange(false);
    },
    dispose: drop,
  };
}

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
 *
 * `paused` (default false) suspends it while true — scroll events are ignored — and on the way back
 * to false the caller is shown again, with the distance scrolled in between not counted. See
 * `createHideOnScroll`.
 */
export function useHideOnScroll(delayMs = 120, revealAfterPx = 80, paused = false): boolean {
  const [hidden, setHidden] = useState(false);
  const controllerRef = useRef<ReturnType<typeof createHideOnScroll> | null>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    const scroller: HTMLElement | Window = document.getElementById('main-content') ?? window;
    const getY = () => (scroller instanceof Window ? scroller.scrollY : scroller.scrollTop);
    const controller = createHideOnScroll(getY, setHidden, delayMs, revealAfterPx);
    controller.setPaused(pausedRef.current);
    controllerRef.current = controller;

    const onScroll = () => controller.onScroll();
    scroller.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      controller.dispose();
      controllerRef.current = null;
    };
  }, [delayMs, revealAfterPx]);

  // Layout effect: on resume the bar is shown before the next paint, not a frame later.
  useLayoutEffect(() => {
    controllerRef.current?.setPaused(paused);
  }, [paused]);

  return hidden;
}
