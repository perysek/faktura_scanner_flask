import type { InputHTMLAttributes } from 'react';

interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'role' | 'className'> {
  small?: boolean;
}

/** On/off switch built on a real checkbox (`role="switch"`), so keyboard and
 * screen readers behave. The slider is decoration; put the whole control inside
 * a <label> so the entire row is the tap target, not just the track. */
export function Switch({ small, ...rest }: SwitchProps) {
  return (
    <span className={`toggle${small ? ' toggle-sm' : ''}`}>
      <input type="checkbox" role="switch" {...rest} />
      <span className="toggle-slider" aria-hidden="true" />
    </span>
  );
}
