import { useEffect } from 'react';
import type { RefObject } from 'react';

/**
 * Visits list (desktop, >= 1024px): centres the floating row (scroll pair + "+") on the gap
 * between the list's bottom edge and AppShell's footer, without changing that gap.
 *
 * The buttons are taller than the gap, so they hang over both edges — and both the page root
 * (`.page-fills-viewport { overflow: hidden }`) and `<main>` (`overflow: auto`) would clip
 * an absolutely positioned float there. So the floats go `position: fixed` (Appointments.css
 * `.cal-main--floats-gap`), and this hook feeds them the geometry as CSS variables on `.cal-main`:
 * `--floats-cy` = the gap's vertical centre, `--floats-right` = distance from `.cal-main`'s
 * right edge to the viewport's. Re-measured when `.cal-main` resizes (window, collapsed month
 * sidebar, hidden nav sidebar).
 */
export function useFloatsInFooterGap(calMainRef: RefObject<HTMLElement>, enabled: boolean) {
  useEffect(() => {
    const main = calMainRef.current;
    if (!enabled || !main) return;
    const footer = document.querySelector<HTMLElement>('.app-shell-footer');
    let frame = 0;
    const measure = () => {
      frame = 0;
      const box = main.getBoundingClientRect();
      const footerTop = footer && footer.offsetParent !== null ? footer.getBoundingClientRect().top : window.innerHeight;
      main.style.setProperty('--floats-cy', `${(box.bottom + footerTop) / 2}px`);
      main.style.setProperty('--floats-right', `${document.documentElement.clientWidth - box.right}px`);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(main);
    window.addEventListener('resize', schedule);
    measure();
    main.classList.add('cal-main--floats-gap');
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', schedule);
      if (frame) cancelAnimationFrame(frame);
      main.classList.remove('cal-main--floats-gap');
      main.style.removeProperty('--floats-cy');
      main.style.removeProperty('--floats-right');
    };
  }, [calMainRef, enabled]);
}
