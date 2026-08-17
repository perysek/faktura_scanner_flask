import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';

const THEME_KEY = 'theme';

const THEMES: Array<{ value: string; label: string; swatch: string }> = [
  { value: '', label: 'Jasny', swatch: 'light' },
  { value: 'blue', label: 'Niebieski', swatch: 'blue' },
  { value: 'green', label: 'Zielony', swatch: 'green' },
  { value: 'graphite', label: 'Grafitowy', swatch: 'graphite' },
];

function applyTheme(value: string) {
  if (value) {
    document.documentElement.setAttribute('data-theme', value);
    try {
      localStorage.setItem(THEME_KEY, value);
    } catch {
      /* private browsing / storage disabled — theme just won't persist */
    }
  } else {
    document.documentElement.removeAttribute('data-theme');
    try {
      localStorage.removeItem(THEME_KEY);
    } catch {
      /* ignore */
    }
  }
}

/**
 * Theme-switcher popover — DESIGN.md §4 rule 6. The one sanctioned
 * trigger-button + role="menu" popover idiom in the system; reuse this exact
 * pattern for any future small-footprint settings control (§17).
 */
export function ThemeSwitcher() {
  const [isOpen, setIsOpen] = useState(false);
  const [current, setCurrent] = useState(() => document.documentElement.getAttribute('data-theme') ?? '');
  const menuRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEscapeClaim(isOpen);

  function close(returnFocus: boolean) {
    setIsOpen(false);
    if (returnFocus) btnRef.current?.focus();
  }

  useEffect(() => {
    if (!isOpen) return;
    function onDocClick(event: MouseEvent) {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || btnRef.current?.contains(target)) return;
      close(false);
    }
    document.addEventListener('click', onDocClick, true);
    return () => document.removeEventListener('click', onDocClick, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const activeIndex = THEMES.findIndex((t) => t.value === current);
    itemRefs.current[activeIndex >= 0 ? activeIndex : 0]?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const idx = itemRefs.current.findIndex((el) => el === document.activeElement);
    if (event.key === 'Escape') {
      event.stopPropagation(); // don't also trigger a page-level Escape binding
      close(true);
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      itemRefs.current[(idx + 1 + THEMES.length) % THEMES.length]?.focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      itemRefs.current[(idx - 1 + THEMES.length) % THEMES.length]?.focus();
    } else if (event.key === 'Home') {
      event.preventDefault();
      itemRefs.current[0]?.focus();
    } else if (event.key === 'End') {
      event.preventDefault();
      itemRefs.current[THEMES.length - 1]?.focus();
    }
  }

  function selectTheme(value: string) {
    applyTheme(value);
    setCurrent(value);
    close(true);
  }

  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <button
        type="button"
        ref={btnRef}
        className="sidebar-icon-btn"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls="theme-menu"
        title="Zmień motyw kolorystyczny"
        aria-label="Zmień motyw kolorystyczny"
        onClick={() => setIsOpen((o) => !o)}
      >
        <Icon name="palette" />
      </button>
      {isOpen && (
        <div
          id="theme-menu"
          ref={menuRef}
          className="theme-menu"
          role="menu"
          aria-label="Motyw kolorystyczny"
          onKeyDown={handleKeyDown}
        >
          {THEMES.map((theme, i) => (
            <button
              key={theme.value || 'light'}
              type="button"
              ref={(el) => {
                itemRefs.current[i] = el;
              }}
              className="theme-menu-item"
              role="menuitemradio"
              aria-checked={current === theme.value}
              onClick={() => selectTheme(theme.value)}
            >
              <span className="theme-swatch" data-swatch={theme.swatch} aria-hidden="true" />
              <span style={{ flex: 1, textAlign: 'left' }}>{theme.label}</span>
              <Icon name="check" className="theme-menu-check" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
