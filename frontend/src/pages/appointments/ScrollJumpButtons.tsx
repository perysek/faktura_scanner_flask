import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { Icon } from '../../lib/icons/Icon';

/** How far from an edge still counts as "at" that edge. */
const EDGE_PX = 24;

interface ScrollJumpButtonsProps {
  /** The page's own scroll box, when it has one (the desktop list's `.table-container`,
   * which only scrolls on viewport-bounded layouts). When it isn't actually overflowing
   * the button drives AppShell's `<main class="app-shell-content">` instead — the real
   * page scroller everywhere else, the phone included. */
  innerScrollerRef?: RefObject<HTMLElement>;
  /** Slide the button away (and make it unreachable) — the phone view ties this to its bottom
   * bars, so the button leaves and returns with them. */
  hidden?: boolean;
}

/** Single floating scroll button for long lists. It is only there at an edge: at the top it
 * points down and jumps to the end, at the bottom it points up and jumps to the start.
 * Anywhere in between (and when nothing overflows) it fades out. While faded it keeps the
 * last arrow, so the icon never flips mid-fade.
 * Placement (fixed vs. anchored inside `.cal-main`) is CSS only — see Appointments.css. */
export function ScrollJumpButtons({ innerScrollerRef, hidden = false }: ScrollJumpButtonsProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  // `dir` is only rewritten when the button becomes visible at an edge (one update, so the
  // arrow and the fade-in land together); a fade-out keeps the previous arrow.
  const [{ visible, dir }, setState] = useState<{ visible: boolean; dir: 'down' | 'up' }>({ visible: false, dir: 'down' });

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
      const overflow = el ? el.scrollHeight - el.clientHeight : 0;
      const hide = (s: { visible: boolean; dir: 'down' | 'up' }) => (s.visible ? { ...s, visible: false } : s);
      if (!el || overflow <= 1) setState(hide);
      else if (el.scrollTop <= EDGE_PX) setState((s) => (s.visible && s.dir === 'down' ? s : { visible: true, dir: 'down' }));
      else if (overflow - el.scrollTop <= EDGE_PX) setState((s) => (s.visible && s.dir === 'up' ? s : { visible: true, dir: 'up' }));
      else setState(hide);
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

  function jump() {
    const el = getScroller();
    if (!el) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollTo({ top: dir === 'up' ? 0 : el.scrollHeight, behavior: reduceMotion ? 'auto' : 'smooth' });
  }

  return (
    <div className={`scroll-jump${hidden ? ' scroll-jump--hidden' : ''}`} ref={rootRef}>
      <button
        type="button"
        className={`scroll-jump-btn${visible ? '' : ' scroll-jump-btn--hidden'}`}
        onClick={jump}
        aria-label={dir === 'up' ? 'Przewiń na początek listy' : 'Przewiń na koniec listy'}
        title={dir === 'up' ? 'Na początek' : 'Na koniec'}
        aria-hidden={visible ? undefined : true}
        tabIndex={visible ? 0 : -1}
      >
        <Icon name={dir === 'up' ? 'arrow_upward' : 'arrow_downward'} />
      </button>
    </div>
  );
}
