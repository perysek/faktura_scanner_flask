import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useFocusTrap } from '../../lib/a11y/useFocusTrap';
import { ButtonLink } from '../ui/Button';
import { SupportLauncher } from '../support/SupportLauncher';
import { NAV_SECTIONS, NAV_STANDALONE_LINKS } from './navConfig';
import type { NavLinkConfig } from './navConfig';
import { NavIcon } from './NavIcon';
import { SidebarSection } from './SidebarSection';
import { ThemeSwitcher } from './ThemeSwitcher';

const ROLE_LABELS: Record<string, string> = {
  superuser: 'Superadmin',
  admin: 'Administrator',
  accountant: 'Księgowa',
  receptionist: 'Recepcjonistka',
  stylist: 'Stylistka',
};

export interface SidebarProps {
  isMobileOpen: boolean;
  onCloseMobile: () => void;
  /** The ticket pop-out is open: the phone button hides until it closes. */
  isSupportOpen: boolean;
  onOpenSupport: () => void;
}

/** One nav row — shared by the accordion sections and the top-level links so
 * the two can never drift apart in markup or active-state classes. */
function SidebarNavLink({ link }: { link: NavLinkConfig }) {
  const { pathname } = useLocation();
  if (link.variant === 'cta') {
    // On the page it opens, the CTA dissolves away (0.3s, space kept so nothing
    // below jumps) and materialises back as soon as you leave it.
    const away = pathname === link.to;
    return (
      <ButtonLink
        variant="primary"
        icon={link.glyph}
        to={link.to}
        className={`sidebar-cta${away ? ' sidebar-cta--away' : ''}`}
        tabIndex={away ? -1 : undefined}
        aria-hidden={away || undefined}
      >
        {link.label}
      </ButtonLink>
    );
  }
  return (
    <NavLink
      to={link.to}
      end
      className={({ isActive }) =>
        `sidebar-link ${isActive ? 'sidebar-link--active' : 'sidebar-link--default'}${link.mobileHide ? ' nav-mobile-hide' : ''}`
      }
    >
      {!link.iconAfter && <NavIcon path={link.iconPath} />}
      {link.label}
      {link.iconAfter && <NavIcon path={link.iconPath} />}
    </NavLink>
  );
}

/**
 * App-shell sidebar — DESIGN.md §13. Data-driven from `navConfig.ts`;
 * NEVER hardcode a link here (§13.5).
 */
export function Sidebar({ isMobileOpen, onCloseMobile, isSupportOpen, onOpenSupport }: SidebarProps) {
  const auth = useAuth();
  const location = useLocation();
  const asideRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const ctx = useMemo(
    () => ({
      user: auth.user,
      isSupervisor: auth.isSupervisor,
      hasLinkedEmployee: auth.hasLinkedEmployee,
      hasModuleAccess: auth.hasModuleAccess,
      hasModuleWrite: auth.hasModuleWrite,
      moduleFlags: auth.moduleFlags,
    }),
    [auth.user, auth.isSupervisor, auth.hasLinkedEmployee, auth.hasModuleAccess, auth.hasModuleWrite, auth.moduleFlags],
  );

  // Filter to only the links (and, transitively, only the non-empty
  // sections) the current user may see — recomputed every render, no
  // separate "admin sidebar config" to keep in sync (§13.5). A section's own
  // `visible` (when present) is a whole-section AND gate — it drops every
  // link regardless of each link's individual rule (e.g. Finanse requires
  // 'invoices' access outright, even for 'Panel danych', whose own `visible` is
  // otherwise unconditional).
  const visibleSections = useMemo(
    () =>
      NAV_SECTIONS.filter((section) => section.visible?.(ctx) ?? true)
        .map((section) => ({
          ...section,
          links: section.links.filter((link) => link.visible(ctx)),
        }))
        .filter((section) => section.links.length > 0),
    [ctx],
  );

  // Standalone links (outside any accordion section) get the same per-link filter.
  const visibleStandaloneLinks = useMemo(() => NAV_STANDALONE_LINKS.filter((link) => link.visible(ctx)), [ctx]);

  const [openSectionId, setOpenSectionId] = useState<string | null>(null);

  // The section containing the active route auto-opens on navigation (§13.2).
  useEffect(() => {
    const active = visibleSections.find((section) =>
      section.links.some((link) => location.pathname === link.to || location.pathname.startsWith(`${link.to}/`)),
    );
    if (active) setOpenSectionId(active.id);
  }, [location.pathname, visibleSections]);

  function toggleSection(id: string) {
    setOpenSectionId((current) => (current === id ? null : id));
  }

  // Mobile drawer: focus trap + Escape-claim while open, body scroll lock,
  // stays mounted at all times (off-canvas via CSS, not conditional render —
  // §13.4).
  useEscapeClaim(isMobileOpen);
  useFocusTrap(isMobileOpen, asideRef, returnFocusRef);

  useEffect(() => {
    document.body.classList.toggle('scroll-lock', isMobileOpen);
    return () => document.body.classList.remove('scroll-lock');
  }, [isMobileOpen]);

  useEffect(() => {
    if (!isMobileOpen) return;
    function handleKeydown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      onCloseMobile();
    }
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  }, [isMobileOpen, onCloseMobile]);

  // Close the mobile drawer automatically on route change.
  useEffect(() => {
    onCloseMobile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return (
    <>
      <aside ref={asideRef} className={`sidebar${isMobileOpen ? ' is-open' : ''}`} id="sidebar">
        <div className="sidebar-logo-block">
          <img src="/logo-inline.webp" alt="MyWay Nails &amp; Beauty" />
          <p className="sidebar-tagline">Beauty Salon Management</p>
        </div>

        <nav className="sidebar-nav" aria-label="Menu główne">
          {visibleSections.map((section) => (
            <SidebarSection
              key={section.id}
              id={section.id}
              title={section.title}
              isOpen={openSectionId === section.id}
              onToggle={() => toggleSection(section.id)}
            >
              {section.links.map((link) => (
                <SidebarNavLink key={link.to} link={link} />
              ))}
            </SidebarSection>
          ))}
          {visibleStandaloneLinks.length > 0 && (
            <div className="sidebar-nav-standalone">
              {visibleStandaloneLinks.map((link) => (
                <SidebarNavLink key={link.to} link={link} />
              ))}
            </div>
          )}
        </nav>

        {/* Outside the scrolling nav, so it stays put at the nav area's bottom-right, right above
            the user bar, however long the menu is. */}
        <SupportLauncher
          hidden={isSupportOpen}
          onOpen={() => {
            onCloseMobile();
            onOpenSupport();
          }}
        />

        {/* "Widok administratora"/"Dane własne" toggles removed — admin view
            is now permanently ON for every superuser (config/admin_view.py),
            and "Dane własne" moved to a long-press gesture on the mobile
            employee selector (MobileWizytyCalendarView.tsx). Nothing left to
            control from this sidebar. */}

        <div className="sidebar-footer">
          <div className="sidebar-user-row">
            <NavLink to="/profil" className="sidebar-user-link" aria-label={`Mój profil: ${auth.user?.full_name ?? ''}`}>
              <div className="sidebar-avatar">{(auth.user?.full_name ?? '').slice(0, 2).toUpperCase()}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p className="sidebar-user-name">{auth.user?.full_name}</p>
                <p className="sidebar-user-role">
                  {(auth.user && ROLE_LABELS[auth.user.role]) ?? auth.user?.role}
                </p>
              </div>
            </NavLink>
            <ThemeSwitcher />
            <button
              type="button"
              className="sidebar-icon-btn danger-hover"
              title="Wyloguj"
              aria-label="Wyloguj"
              onClick={() => auth.logout()}
            >
              <svg width="1.25rem" height="1.25rem" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </aside>
      <div className={`sidebar-backdrop${isMobileOpen ? ' is-open' : ''}`} aria-hidden="true" onClick={onCloseMobile} />
    </>
  );
}
