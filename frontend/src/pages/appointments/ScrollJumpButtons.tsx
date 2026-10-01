import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { Icon } from '../../lib/icons/Icon';

/** How far from an edge still counts as "at" that edge. */
const EDGE_PX = 24;

interface ScrollJumpButtonsProps {
  /** The page's own scroll box, when it has one (the desktop list's `.table-container`,
   * which only scrolls on viewport-bounded layouts). When it isn't actually overflowing
   * the buttons drive AppShell's `<main class="app-shell-content">` instead — the real
   * page scroller everywhere else, the phone included. */
  innerScrollerRef?: RefObject<HTMLElement>;
}

/** Floating "scroll to start" / "scroll to end" pair for long lists. Each button shows
 * only while its target is somewhere else: up when not at the top, down when not at the
 * end — so both are visible mid-list. Both keep their slot (hidden via `visibility`) so
 * the pair sits side by side at one height and never shifts when one of them toggles.
 * Placement (fixed vs. anchored inside `.cal-main`) is CSS only — see Appointments.css. */
export function ScrollJumpButtons({ innerScrollerRef }: ScrollJumpButtonsProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [canUp, setCanUp] = useState(false);
  const [canDown, setCanDown] = useState(false);

  const getScroller = useCallback((): HTMLElement | null => {
    const inner = innerScrollerRef?.current;
    if (inner && inner.scrollHeight - inner.clientHeight > 1) return inner;
    return rootRef.current?.closest<HTMLElement>('.app-shell-content') ?? null;
  }, [innerScrollerRef]);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = getScroller();
      if (!el) {
        setCanUp(false);
        setCanDown(false);
        return;
      }
      setCanUp(el.scrollTop > EDGE_PX);
      setCanDown(el.scrollHeight - el.clientHeight - el.scrollTop > EDGE_PX);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    // `scroll` doesn't bubble, but a capture listener on the document still sees it from
    // whichever element scrolls (inner box or shell). Content growing/shrinking (list
    // loaded, "Pokaż kolejny dzień", filters) changes the end without any scroll event,
    // hence the observer + resize.
    document.addEventListener('scroll', schedule, { capture: true, passive: true });
    window.addEventListener('resize', schedule);
    const shell = rootRef.current?.closest('.app-shell-content');
    const observer = shell ? new MutationObserver(schedule) : null;
    if (shell && observer) observer.observe(shell, { childList: true, subtree: true });
    schedule();
    return () => {
      document.removeEventListener('scroll', schedule, true);
      window.removeEventListener('resize', schedule);
      observer?.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [getScroller]);

  function jump(to: 'start' | 'end') {
    const el = getScroller();
    if (!el) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollTo({ top: to === 'start' ? 0 : el.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
  }

  return (
    <div className="scroll-jump" ref={rootRef}>
      <button
        type="button"
        className={`scroll-jump-btn${canUp ? '' : ' scroll-jump-btn--hidden'}`}
        onClick={() => jump('start')}
        aria-label="Przewiń na początek listy"
        title="Na początek"
        tabIndex={canUp ? 0 : -1}
      >
        <Icon name="arrow_upward" />
      </button>
      <button
        type="button"
        className={`scroll-jump-btn${canDown ? '' : ' scroll-jump-btn--hidden'}`}
        onClick={() => jump('end')}
        aria-label="Przewiń na koniec listy"
        title="Na koniec"
        tabIndex={canDown ? 0 : -1}
      >
        <Icon name="arrow_downward" />
      </button>
    </div>
  );
}
