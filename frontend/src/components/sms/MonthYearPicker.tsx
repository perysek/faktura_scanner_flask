import { useEffect, useId, useRef, useState } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { MAX_MONTH, MIN_MONTH, MONTH_ABBR, fmtMonthYear, monthOf, shiftMonth } from './smsFormat';
import './sms.css';

export interface MonthYearPickerProps {
  /** "YYYY-MM". */
  value: string;
  onChange: (month: string) => void;
  label?: string;
  /** Earliest / latest month that can be picked ("YYYY-MM"); default: the range the server accepts. Months outside
   * are disabled everywhere: the arrows, the year arrows and the month grid. */
  min?: string;
  max?: string;
}

/**
 * "Pokaż wiadomości od [‹] [📅 październik 2026] [›]" — the arrows move one month and apply at once; the
 * calendar button opens a year + month grid for longer jumps. Native `<input type="month">` is not an option:
 * Firefox desktop still renders it as a plain text box.
 */
export function MonthYearPicker({ value, onChange, label = 'Pokaż wiadomości od', min = MIN_MONTH, max = MAX_MONTH }: MonthYearPickerProps) {
  const minYear = Number(min.slice(0, 4));
  const maxYear = Number(max.slice(0, 4));
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(() => Number(value.slice(0, 4)));
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const labelId = useId();

  function toggle() {
    setYear(Number(value.slice(0, 4))); // always open on the year being shown
    setOpen((isOpen) => !isOpen);
  }

  function pick(monthIndex: number) {
    onChange(monthOf(year, monthIndex));
    setOpen(false);
    triggerRef.current?.focus();
  }

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    // Keyboard users land on the month in use (or the first one when the grid shows another year).
    const pop = popRef.current;
    (pop?.querySelector<HTMLButtonElement>('[aria-pressed="true"]') ?? pop?.querySelector<HTMLButtonElement>('.sms-month-cell:not(:disabled)'))?.focus();
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div className="sms-month" ref={rootRef}>
      <span className="sms-month-label" id={labelId}>
        {label}
      </span>
      <div className="sms-month-ctrl" role="group" aria-labelledby={labelId}>
        <button type="button" className="sms-month-step" aria-label="Poprzedni miesiąc" disabled={value <= min} onClick={() => onChange(shiftMonth(value, -1))}>
          <Icon name="chevron_left" />
        </button>
        <button type="button" ref={triggerRef} className="sms-month-current" aria-haspopup="dialog" aria-expanded={open} onClick={toggle}>
          <Icon name="calendar_month" />
          <span>{fmtMonthYear(value)}</span>
        </button>
        <button type="button" className="sms-month-step" aria-label="Następny miesiąc" disabled={value >= max} onClick={() => onChange(shiftMonth(value, 1))}>
          <Icon name="chevron_right" />
        </button>
      </div>

      {open && (
        <div className="sms-month-pop" role="dialog" aria-label="Wybierz miesiąc i rok" ref={popRef}>
          <div className="sms-month-year">
            <button type="button" className="sms-month-step" aria-label="Poprzedni rok" disabled={year <= minYear} onClick={() => setYear((y) => y - 1)}>
              <Icon name="chevron_left" />
            </button>
            <strong aria-live="polite">{year}</strong>
            <button type="button" className="sms-month-step" aria-label="Następny rok" disabled={year >= maxYear} onClick={() => setYear((y) => y + 1)}>
              <Icon name="chevron_right" />
            </button>
          </div>
          <div className="sms-month-grid">
            {MONTH_ABBR.map((abbr, i) => {
              const ym = monthOf(year, i);
              const selected = ym === value;
              return (
                <button key={ym} type="button" className={`sms-month-cell${selected ? ' selected' : ''}`} aria-pressed={selected} aria-label={fmtMonthYear(ym)} disabled={ym < min || ym > max} onClick={() => pick(i)}>
                  {abbr}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
