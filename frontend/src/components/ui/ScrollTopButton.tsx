import { useEffect, useState } from 'react';
import { Icon } from '../../lib/icons/Icon';

/**
 * Floating "scroll to top" button, mobile stack-cards pages only — ported
 * from static/js/utils.js's initScrollToTopButton(). Scrolls #main-content
 * (the app shell's own scroll region, DESIGN.md §5), not the window.
 */
export function ScrollTopButton({ threshold = 400 }: { threshold?: number }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const scroller = document.getElementById('main-content');
    if (!scroller) return;
    function handleScroll() {
      setVisible((scroller as HTMLElement).scrollTop > threshold);
    }
    scroller.addEventListener('scroll', handleScroll, { passive: true });
    return () => scroller.removeEventListener('scroll', handleScroll);
  }, [threshold]);

  function handleClick() {
    document.getElementById('main-content')?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return (
    <button
      type="button"
      className={`scroll-top-btn${visible ? ' visible' : ''}`}
      aria-label="Przewiń do góry"
      title="Przewiń do góry"
      onClick={handleClick}
    >
      <Icon name="arrow_upward" />
    </button>
  );
}
