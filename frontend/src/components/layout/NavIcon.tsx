export interface NavIconProps {
  /** A single 24×24 stroke path, or (rarely — e.g. "Ustawienia"'s gear+dot
   * glyph) more than one path drawn together. */
  path: string | string[];
  className?: string;
}

/**
 * Sidebar nav icon system — DESIGN.md §9. ViewBox `0 0 24 24`, stroke
 * (`stroke-width="2"`), used ONLY for sidebar nav links. Paths are passed
 * directly as a 24×24 stroke-path string per link config (navConfig.ts) —
 * no shared registry, since nav icons are page-specific.
 *
 * Ported 1:1 from `templates/components/sidebar.html`'s inline paths, which
 * already used this exact viewBox/stroke convention (implementation-log.md
 * Decision D6) — no new icon set had to be sourced.
 */
export function NavIcon({ path, className }: NavIconProps) {
  const paths = Array.isArray(path) ? path : [path];
  return (
    <svg
      className={`sidebar-nav-icon${className ? ` ${className}` : ''}`}
      width="1.25rem"
      height="1.25rem"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
      focusable="false"
    >
      {paths.map((d) => (
        <path key={d} strokeLinecap="round" strokeLinejoin="round" d={d} />
      ))}
    </svg>
  );
}
