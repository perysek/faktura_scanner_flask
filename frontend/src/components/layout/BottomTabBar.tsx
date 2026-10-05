import { useMemo } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { NAV_SECTIONS } from './navConfig';
import type { NavLinkConfig } from './navConfig';
import { NavIcon } from './NavIcon';

/** The daily pages, in tab order. Label, icon and visibility come from the
 * drawer's own config (navConfig.ts), so a tab can never show a page the
 * drawer would hide (§13.5). */
const TAB_ROUTES = ['/wizyty', '/klienci', '/pracownicy'];

const MENU_ICON = 'M4 6h16M4 12h16M4 18h16';

/** Create/edit routes keep the whole bottom edge for their own save bar. */
export function showsTabBar(pathname: string): boolean {
  return !/\/(nowa|nowy|edytuj)$/.test(pathname);
}

interface BottomTabBarProps {
  isMenuOpen: boolean;
  onMenu: () => void;
}

/**
 * P2 · Bottom tab bar (Mobile Design System) — phones only (CSS hides it
 * above 640px). Wizyty, Klienci and Pracownicy sat two taps deep in the
 * drawer; here they are one tap away, and "Menu" opens the same drawer for
 * everything else. Rendered in flow under <main>, so every page's sticky
 * bottom bar lands above it without knowing it exists.
 */
export function BottomTabBar({ isMenuOpen, onMenu }: BottomTabBarProps) {
  const auth = useAuth();
  const tabs = useMemo(() => {
    const links = NAV_SECTIONS.filter((section) => section.visible?.(auth) ?? true).flatMap((section) => section.links);
    return TAB_ROUTES.map((to) => links.find((link) => link.to === to)).filter((link): link is NavLinkConfig => !!link && link.visible(auth));
  }, [auth]);

  return (
    <nav className="mw-tabbar" aria-label="Główne sekcje">
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} className={({ isActive }) => `mw-tab${isActive && !isMenuOpen ? ' is-on' : ''}`}>
          <NavIcon path={tab.iconPath} />
          <span className="mw-tab__label">{tab.label}</span>
        </NavLink>
      ))}
      <button type="button" className={`mw-tab${isMenuOpen ? ' is-on' : ''}`} aria-expanded={isMenuOpen} aria-controls="sidebar" onClick={onMenu}>
        <NavIcon path={MENU_ICON} />
        <span className="mw-tab__label">Menu</span>
      </button>
    </nav>
  );
}
