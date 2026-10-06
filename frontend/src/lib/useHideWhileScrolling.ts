import { useEffect, useLayoutEffect, useRef, useState } from 'react';

type Timer = ReturnType<typeof setTimeout>;

/**
 * The logic behind `useHideWhileScrolling`, with no React or DOM in it (the scroll position and the
 * clock are injected), so it can be tested on its own.
 *
 * Hidden WHILE the user is scrolling, back `idleMs` after the scrolling stops — unlike
 * `createHideOnScroll`, which waits for a scroll to end and then decides by its direction.
 *
 * It only reacts to scrolling a user caused (`gesture()`: a touch drag or the wheel). The page also
 * scrolls itself — `scrollIntoView` on load and on every day tap — and a bar that vanishes the moment
 * you tap it would be worse than one that never hides. A plain tap never counts either: that is a
 * touchstart/touchend with no touchmove between.
 *
 * - Hides once the position has moved more than `thresholdPx` from where the gesture began (jitter,
 *   or a layout shift nudging scrollTop, never flickers it).
 * - Comes back when no scroll event has arrived for `idleMs` AND no finger is down: a finger held still
 *   in the middle of a drag is not "stopped".
 * - `setPaused(true)` shows it at once and ignores scrolling until resumed (the caller is being used).
 */
export function createHideWhileScrolling(
  getY: () => number,
  onChange: (hidden: boolean) => void,
  idleMs = 220,
  thresholdPx = 6,
  schedule: (fn: () => void, ms: number) => Timer = setTimeout,
  cancel: (t: Timer) => void = clearTimeout,
) {
  let anchorY = getY();
  let hidden = false;
  // A user gesture is behind the scrolling right now (cleared when the scrolling settles).
  let intent = false;
  let touching = false;
  let paused = false;
  let timer: Timer | null = null;

  function drop() {
    if (timer) cancel(timer);
    timer = null;
  }

  function settle() {
    timer = null;
    // Finger still down: not stopped yet — look again in a moment.
    if (touching) {
      arm();
      return;
    }
    intent = false;
    anchorY = getY();
    if (hidden) {
      hidden = false;
      onChange(false);
    }
  }

  function arm() {
    drop();
    timer = schedule(settle, idleMs);
  }

  function beginIntent() {
    if (paused || intent) return;
    intent = true;
    // Measure from where this gesture starts, not from wherever the last one (or a programmatic scroll) left it.
    anchorY = getY();
  }

  return {
    /** A touch drag or wheel tick: the user, not the page, is scrolling. */
    gesture: beginIntent,
    /** A finger went down / came up on the scroller. Down alone is not intent: a tap is not a scroll. */
    touch(down: boolean) {
      touching = down;
      if (!down && !paused) arm();
    },
    onScroll() {
      if (paused || !intent) return;
      if (!hidden && Math.abs(getY() - anchorY) > thresholdPx) {
        hidden = true;
        onChange(true);
      }
      arm();
    },
    setPaused(next: boolean) {
      if (next === paused) return;
      paused = next;
      drop();
      intent = false;
      anchorY = getY();
      if (next && hidden) {
        hidden = false;
        onChange(false);
      }
    },
    dispose: drop,
  };
}

/**
 * Hides the caller (a fixed bar the user would rather not have sitting over the cards) while the page
 * is being scrolled by the user, and brings it back a moment after they stop. See
 * `createHideWhileScrolling` for the rules.
 *
 * Listens on `#main-content` (AppShell's `<main>`, the app's only real scroll region — the window never
 * scrolls), falling back to `window` outside the shell, like `useHideOnScroll`.
 *
 * `paused` (default false) shows the caller and ignores scrolling while true — for when it is open or
 * in use (a month grid, a picker sheet).
 */
export function useHideWhileScrolling(paused = false, idleMs = 220, thresholdPx = 6): boolean {
  const [hidden, setHidden] = useState(false);
  const controllerRef = useRef<ReturnType<typeof createHideWhileScrolling> | null>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    const scroller: HTMLElement | Window = document.getElementById('main-content') ?? window;
    const getY = () => (scroller instanceof Window ? scroller.scrollY : scroller.scrollTop);
    const controller = createHideWhileScrolling(getY, setHidden, idleMs, thresholdPx);
    controller.setPaused(pausedRef.current);
    controllerRef.current = controller;

    const onScroll = () => controller.onScroll();
    const onGesture = () => controller.gesture();
    const onTouchStart = () => controller.touch(true);
    const onTouchEnd = () => controller.touch(false);
    const passive = { passive: true } as const;
    scroller.addEventListener('scroll', onScroll, passive);
    scroller.addEventListener('wheel', onGesture, passive);
    scroller.addEventListener('touchmove', onGesture, passive);
    scroller.addEventListener('touchstart', onTouchStart, passive);
    scroller.addEventListener('touchend', onTouchEnd, passive);
    scroller.addEventListener('touchcancel', onTouchEnd, passive);
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      scroller.removeEventListener('wheel', onGesture);
      scroller.removeEventListener('touchmove', onGesture);
      scroller.removeEventListener('touchstart', onTouchStart);
      scroller.removeEventListener('touchend', onTouchEnd);
      scroller.removeEventListener('touchcancel', onTouchEnd);
      controller.dispose();
      controllerRef.current = null;
    };
  }, [idleMs, thresholdPx]);

  // Layout effect: on pause the bar is shown before the next paint, not a frame later.
  useLayoutEffect(() => {
    controllerRef.current?.setPaused(paused);
  }, [paused]);

  return hidden;
}
