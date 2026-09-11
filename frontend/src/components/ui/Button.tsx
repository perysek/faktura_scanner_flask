import { Link } from 'react-router-dom';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import type { LinkProps } from 'react-router-dom';
import { Icon } from '../../lib/icons/Icon';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'brand';

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'refined-btn-primary',
  secondary: 'refined-btn-secondary',
  ghost: 'refined-btn-ghost',
  danger: 'refined-btn-danger',
  brand: 'refined-btn-brand',
};

function buildClassName(variant: ButtonVariant, small: boolean | undefined, className: string | undefined) {
  return [VARIANT_CLASS[variant], 'btn-press', small && 'refined-btn-sm', className].filter(Boolean).join(' ');
}

/**
 * Busy indicator for `isLoading` (DESIGN.md §6 gap, audit finding #6,
 * mobile-audit-wizyty-list.md) — a swapped label alone is easy to miss,
 * especially for screen-reader users or on a slow connection. Rotation
 * only (compositor-friendly, respects prefers-reduced-motion via
 * `.btn-spinner`'s own rule in components.css); decorative, so the
 * button's `aria-busy` carries the actual state to assistive tech.
 */
function Spinner() {
  return (
    <svg className="icon btn-spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="42.5 56.5" />
    </svg>
  );
}

interface SharedProps {
  variant?: ButtonVariant;
  /** Tightens padding/font-size for inline/table-adjacent actions (§6) —
   * never for primary page-level CTAs. */
  small?: boolean;
  /** Glyph icon name (DESIGN.md §9) rendered before the label. */
  icon?: string;
  children?: ReactNode;
}

export interface ButtonProps extends SharedProps, Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'className' | 'children'> {
  className?: string;
  isLoading?: boolean;
  loadingText?: string;
}

/**
 * Canonical Button component — DESIGN.md §6. Always use `<Button variant="…">`,
 * never hand-roll button styling inline. Default to `secondary` unless there's
 * a clear reason for stronger (`primary`) or weaker (`ghost`) emphasis;
 * `brand` is reserved for the login CTA (§15.5).
 */
export function Button({
  variant = 'secondary',
  small,
  icon,
  children,
  className,
  disabled,
  isLoading,
  loadingText,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buildClassName(variant, small, className)}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      {...rest}
    >
      {isLoading ? <Spinner /> : icon && <Icon name={icon} />}
      {isLoading ? loadingText ?? children : children}
    </button>
  );
}

export interface ButtonLinkProps extends SharedProps, Omit<LinkProps, 'className' | 'children'> {
  className?: string;
}

/** Same visual language as <Button>, for navigation ("Anuluj", "Zobacz", …). */
export function ButtonLink({ variant = 'secondary', small, icon, children, className, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buildClassName(variant, small, className)} {...rest}>
      {icon && <Icon name={icon} />}
      {children}
    </Link>
  );
}
