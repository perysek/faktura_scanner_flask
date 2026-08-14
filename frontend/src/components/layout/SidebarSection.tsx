import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

export interface SidebarSectionProps {
  id: string;
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}

/**
 * One accordion section of the sidebar nav — DESIGN.md §13.2. Expand/collapse
 * animates via a measured `scrollHeight` → `max-height` transition (not
 * display:none/block), with a debounced resize re-measure while open so a
 * viewport rotation doesn't leave a stale collapsed/cut-off height cached.
 * Single-open state (`isOpen`/`onToggle`) is owned by the parent <Sidebar>.
 */
export function SidebarSection({ id, title, isOpen, onToggle, children }: SidebarSectionProps) {
  const itemsRef = useRef<HTMLDivElement>(null);
  const [maxHeight, setMaxHeight] = useState('0px');

  useEffect(() => {
    const el = itemsRef.current;
    if (!el) return;
    setMaxHeight(isOpen ? `${el.scrollHeight}px` : '0px');
  }, [isOpen, children]);

  useEffect(() => {
    if (!isOpen) return;
    let timer: number;
    function handleResize() {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (itemsRef.current) setMaxHeight(`${itemsRef.current.scrollHeight}px`);
      }, 120);
    }
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      window.clearTimeout(timer);
    };
  }, [isOpen]);

  const contentId = `sidebar-section-items-${id}`;

  return (
    <div className="sidebar-section" data-active={isOpen}>
      <button
        type="button"
        className="sidebar-section-header"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={onToggle}
      >
        <span>{title}</span>
        <svg
          className={`sidebar-chevron${isOpen ? ' rotate-180' : ''}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div id={contentId} role="region" aria-label={title} className="sidebar-section-items" ref={itemsRef} style={{ maxHeight }}>
        {children}
      </div>
    </div>
  );
}
