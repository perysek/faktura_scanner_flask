import { useEffect, useRef, useState } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { scrollParentOf } from '../../lib/accordionMotion';
import './sms.css';

/** Phone: the table is stacked cards with no header row, so the start of the list stands in for it. */
const HEADLESS_OFFSET = 160;

/**
 * Round "back to top" button that fades in once the table's header row has scrolled out of view, parked at the
 * bottom-right end of the table's right border. Render it as the LAST child of the element that holds the table
 * (a tabpanel): the zero-height sticky anchor then spans exactly the table's width, so the right alignment
 * needs no measuring, and it sits above the viewport bottom while the table runs on below.
 *
 * Clicking scrolls the page to the top and fades the button out; it only returns on the next scroll DOWN.
 */
export function TableScrollTop() {
  const anchorRef = useRef<HTMLDivElement>(null);
  const scrollerRef = useRef<HTMLElement | null>(null);
  const armed = useRef(true);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const anchor = anchorRef.current;
    const panel = anchor?.parentElement;
    const scroller = anchor ? scrollParentOf(anchor) : null;
    if (!anchor || !panel || !scroller) return;
    scrollerRef.current = scroller;
    let lastTop = scroller.scrollTop;
    let raf = 0;

    const evaluate = () => {
      raf = 0;
      const top = scroller.scrollTop;
      if (top > lastTop) armed.current = true; // a scroll down re-arms a button the click had put away
      lastTop = top;
      const viewTop = scroller.getBoundingClientRect().top;
      const head = panel.querySelector('thead');
      let off = false;
      if (head && head.getClientRects().length) {
        off = head.getBoundingClientRect().bottom <= viewTop;
      } else {
        const list = panel.querySelector('.table-container');
        if (list && list.getClientRects().length) off = list.getBoundingClientRect().top < viewTop - HEADLESS_OFFSET;
      }
      setVisible(off && armed.current); // a hidden tabpanel has neither: both rects are empty, so it stays hidden
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(evaluate);
    };
    scroller.addEventListener('scroll', schedule, { passive: true });
    const observer = new ResizeObserver(schedule); // tab switches, rows arriving, window resizes
    observer.observe(panel);
    evaluate();
    return () => {
      scroller.removeEventListener('scroll', schedule);
      observer.disconnect();
      cancelAnimationFrame(raf);
    };
  }, []);

  function toTop() {
    const scroller = scrollerRef.current;
    armed.current = false;
    setVisible(false);
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller?.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    scroller?.focus({ preventScroll: true }); // the focused button is about to vanish: keep keyboard users in the page
  }

  return (
    <div className="sms-scrolltop-anchor" ref={anchorRef}>
      <button
        type="button"
        className={`sms-scrolltop${visible ? ' visible' : ''}`}
        aria-label="Przewiń do góry"
        title="Przewiń do góry"
        aria-hidden={!visible}
        tabIndex={visible ? 0 : -1}
        onClick={toTop}
      >
        <Icon name="arrow_upward" />
      </button>
    </div>
  );
}
