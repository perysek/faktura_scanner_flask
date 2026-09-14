export interface SwitchProps {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
  /** Visible row label — `aria-label` alone (below) is not enough here since
   * both mobile toggles need on-screen Polish text, not just an a11y name. */
  hint?: string;
}

/**
 * Sliding left-right switch — NOT a native checkbox. DESIGN.md's global radius
 * scale tops out at `--radius-sm` (2px); a pill-shaped toggle track/thumb
 * would silently blow past that on every other component in the system, so
 * every sub-element here (track, thumb, focus ring) is pinned to
 * `var(--radius-sm)` explicitly rather than the rounder defaults a "switch"
 * usually gets.
 */
export function Switch({ id, checked, onChange, disabled, label, hint }: SwitchProps) {
  return (
    <label htmlFor={id} className={`ui-switch-row${disabled ? ' is-disabled' : ''}`}>
      <span className="ui-switch-text">
        <span className="ui-switch-label">{label}</span>
        {hint && <span className="ui-switch-hint">{hint}</span>}
      </span>
      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        className={`ui-switch-track${checked ? ' is-on' : ''}`}
        onClick={() => {
          if (disabled) return;
          onChange(!checked);
        }}
      >
        <span className="ui-switch-thumb" />
      </button>
    </label>
  );
}
