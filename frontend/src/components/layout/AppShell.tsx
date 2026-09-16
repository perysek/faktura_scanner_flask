import { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { pageTitleFor } from '../../config/pageTitles';
import { Sidebar } from './Sidebar';

/**
 * App shell — DESIGN.md §12. Fixed-height viewport frame (`.app-shell`);
 * <main> owns its own scroll region, the frame itself never scrolls (§5).
 */
export function AppShell() {
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const isFirstMount = useRef(true);

  // SPA route-change focus management (§11.4): a client-side navigation
  // never fires a browser "page load" event, so screen readers get no
  // signal anything happened unless focus visibly moves. Skip the very
  // first mount — only real navigations move focus.
  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

  // No automatic "Widok administratora"/"Dane własne" route-based default
  // here any more (removed) — this was the actual root cause of a whole
  // string of "stuck toggle" / "page keeps reloading" reports that earlier
  // fixes in MobileWizytyCalendarView.tsx never touched, because this
  // effect lives in a completely different file and nobody had traced it
  // this far back. It forced own_data=true every time a superuser landed
  // on /wizyty on mobile — including right after a manual toggle-off's own
  // reload landed back on that same route — which is exactly why turning
  // "Dane własne" off via the sidebar never stuck: this effect flipped it
  // back on again on the very next reload, sometimes visibly (a flash of
  // the correct view, then a second reload reverting it). Scope toggles are
  // now purely manual via the Sidebar's own switches — no page auto-applies
  // a default for them.
  const title = pageTitleFor(location.pathname);

  return (
    <div className="app-shell">
      <Sidebar isMobileOpen={isMobileOpen} onCloseMobile={() => setIsMobileOpen(false)} />
      <div className="app-shell-main">
        <header className="app-shell-header">
          <button
            type="button"
            className="mobile-menu-btn"
            aria-label="Otwórz menu"
            aria-expanded={isMobileOpen}
            aria-controls="sidebar"
            onClick={() => setIsMobileOpen((open) => !open)}
          >
            <svg width="1.5rem" height="1.5rem" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          {/* Mobile page context: logo + current page title, < lg only.
              Logo is decorative — the adjacent text names the page (§12). */}
          <div className="mobile-title-wrap">
            <img src="/logo-inline.webp" alt="" aria-hidden="true" />
            <span className="mobile-title-text">{title}</span>
          </div>
          {/* Empty by default — a page can portal mobile-only header actions
              in here (e.g. Wizyty's "Rozlicz przeszłe wizyty", kept
              reachable while its own page header is dropped on mobile to
              reclaim viewport height). Takes no space when empty. */}
          <div id="mobile-header-actions" className="mobile-header-actions" />
        </header>

        <main id="main-content" className="app-shell-content" tabIndex={-1} ref={mainRef}>
          <Outlet />
        </main>

        <footer className="app-shell-footer">
          &copy; {new Date().getFullYear()} MyWay Beauty Salon. Wszelkie prawa zastrzeżone.
        </footer>
      </div>
    </div>
  );
}
