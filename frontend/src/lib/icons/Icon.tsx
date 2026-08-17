import { ICON_PATHS } from './paths';

export interface IconProps {
  name: string;
  className?: string;
  size?: number | string;
}

/**
 * Glyph icon system — DESIGN.md §9. ViewBox `0 -960 960 960`, filled. Use for
 * everything EXCEPT sidebar nav rows (those use <NavIcon>, a different
 * coordinate space — never mix the two).
 *
 * Always `aria-hidden` (icons are decorative); the interactive element that
 * hosts one is responsible for its own `aria-label` if it has no visible text.
 */
export function Icon({ name, className, size }: IconProps) {
  const d = ICON_PATHS[name] ?? ICON_PATHS.info;
  return (
    <svg
      className={`icon${className ? ` ${className}` : ''}`}
      viewBox="0 -960 960 960"
      fill="currentColor"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
    >
      <path d={d} />
    </svg>
  );
}
