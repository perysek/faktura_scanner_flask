import { useCallback, useEffect, useState } from 'react';

/**
 * Live pixel height of a DOM node, tracked via ResizeObserver — for layouts
 * that need a real number (not a CSS percentage) to size absolutely-
 * positioned children against, e.g. the day/week calendar grids' time-lane
 * math (CalendarWeekPage/CalendarDayPage — fix #5/#6, implementation-log.md
 * 2026-08-19 "dopasowanie wysokości siatki do viewportu"). `fallback` is what
 * callers get before the first real measurement, and also what the value
 * stably converges back to when the node has no externally-bounded height to
 * report (mobile, where `.page-fills-viewport` doesn't apply — DESIGN.md
 * §20.2 gates that to desktop only) — so callers should pass the OLD fixed
 * constant as `fallback` to keep today's mobile layout unchanged.
 *
 * Callback ref, not `useRef` — a plain ref's `.current` change doesn't
 * re-run effects, so a node that mounts later than this hook (e.g. behind a
 * `loading` guard, exactly the case here) would never get observed. The
 * callback fires whenever the node mounts/unmounts/swaps.
 *
 * Reported height is floored and given a 1px safety margin (fix #3e,
 * react-ui-corrections_19080026.txt: calendar still showed a vertical
 * scrollbar after the original height fix) — `getBoundingClientRect()`/
 * `ResizeObserver` can report a fractional value (e.g. `547.33px`), and
 * downstream consumers feed that straight into more floating-point math
 * (percentage-of-range × height) for absolutely-positioned children; any of
 * those roundtrips landing a fraction of a pixel ABOVE the true available
 * space is enough for `overflow: auto` to render a scrollbar even though
 * nothing is visibly cut off. Rounding down instead of to-nearest, plus the
 * 1px margin, guarantees every consumer's computed value stays at or under
 * the real bound, never over it.
 */
export function useElementHeight<T extends HTMLElement>(fallback: number): [(el: T | null) => void, number] {
  const [node, setNode] = useState<T | null>(null);
  const [height, setHeight] = useState(fallback);

  const ref = useCallback((el: T | null) => setNode(el), []);

  useEffect(() => {
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setHeight(Math.max(0, Math.floor(entry.contentRect.height) - 1));
    });
    observer.observe(node);
    setHeight(Math.max(0, Math.floor(node.getBoundingClientRect().height || fallback) - 1));
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node]);

  return [ref, height];
}
