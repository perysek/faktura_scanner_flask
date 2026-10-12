import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, Ref } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';

/** Same contract as SearchableSelectHandle: open = focus + month grid shown, ready for keys. */
export interface DatePickerHandle {
  open: () => void;
  focus: () => void;
}

export interface DatePickerProps {
  id?: string;
  /** YYYY-MM-DD, '' = nothing picked. */
  value: string;
  onChange: (value: string) => void;
  /** After a day was picked (Enter or click) and the grid closed. */
  onPicked?: (value: string) => void;
  required?: boolean;
  disabled?: boolean;
  invalid?: boolean;
  handleRef?: Ref<DatePickerHandle>;
}

const MONTHS = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień'];
const WEEKDAYS = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'So', 'Nd'];
const WEEKDAYS_LONG = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota'];

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function parse(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d);
}
function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}
function addMonths(d: Date, n: number): Date {
  // Clamp the day so 31 Jan + 1 month lands on the last day of February, not in March.
  const last = new Date(d.getFullYear(), d.getMonth() + n + 1, 0).getDate();
  return new Date(d.getFullYear(), d.getMonth() + n, Math.min(d.getDate(), last));
}

function displayLabel(value: string): string {
  const d = parse(value);
  if (!d) return '';
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}, ${WEEKDAYS_LONG[d.getDay()]}`;
}

/**
 * Date field whose open state IS a month grid (Monday-first), keyboard-first:
 * ←/→ ±1 day, ↑/↓ ±1 week, PageUp/PageDown ±1 month, Home/End start/end of
 * week, Enter picks, Escape closes, Tab closes and moves on. Opening puts the
 * cursor on the current value (defaulting to today), so Enter alone confirms it.
 * Built instead of the native <input type="date"> because its popup can't be
 * opened programmatically on focus (showPicker() needs a fresh user gesture)
 * nor driven consistently across browsers.
 */
export function DatePicker({ id, value, onChange, onPicked, required, disabled, invalid, handleRef }: DatePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const todayIso = useMemo(() => iso(new Date()), []);
  const [cursor, setCursor] = useState<Date>(() => parse(value) ?? new Date());

  useEscapeClaim(isOpen);

  const open = useCallback(() => {
    if (disabled) return;
    setCursor(parse(value) ?? new Date());
    setIsOpen(true);
  }, [disabled, value]);

  const close = useCallback((returnFocus: boolean) => {
    setIsOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  useImperativeHandle(handleRef, () => ({ open, focus: () => triggerRef.current?.focus() }), [open]);

  // The grid takes focus as soon as it is shown, so arrows work immediately.
  useEffect(() => {
    if (isOpen) gridRef.current?.focus({ preventScroll: true });
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) close(false);
    }
    document.addEventListener('mousedown', onDocClick, true);
    return () => document.removeEventListener('mousedown', onDocClick, true);
  }, [isOpen, close]);

  function pick(d: Date) {
    const next = iso(d);
    onChange(next);
    close(true);
    onPicked?.(next);
  }

  function handleGridKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, () => Date> = {
      ArrowLeft: () => addDays(cursor, -1),
      ArrowRight: () => addDays(cursor, 1),
      ArrowUp: () => addDays(cursor, -7),
      ArrowDown: () => addDays(cursor, 7),
      PageUp: () => addMonths(cursor, -1),
      PageDown: () => addMonths(cursor, 1),
      Home: () => addDays(cursor, -((cursor.getDay() + 6) % 7)),
      End: () => addDays(cursor, 6 - ((cursor.getDay() + 6) % 7)),
    };
    if (moves[event.key]) {
      event.preventDefault();
      setCursor(moves[event.key]());
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); // never submit the surrounding <form>
      pick(cursor);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.key === 'Tab') {
      close(false);
    }
  }

  // 6 rows × 7 days, starting on the Monday on/before the 1st of the cursor's month.
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const gridStart = addDays(first, -((first.getDay() + 6) % 7));
  const days = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  const cursorIso = iso(cursor);

  return (
    <div className="dpk-root" ref={rootRef}>
      <button
        type="button"
        ref={triggerRef}
        id={id}
        className={`ssel-trigger form-select dpk-trigger${invalid ? ' error' : ''}`}
        disabled={disabled}
        aria-haspopup="grid"
        aria-expanded={isOpen}
        onClick={() => (isOpen ? close(true) : open())}
        onKeyDown={(event) => {
          if (!isOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
            event.preventDefault();
            open();
          }
        }}
      >
        <span className={`ssel-value${value ? '' : ' is-placeholder'}`}>{displayLabel(value) || 'Wybierz datę'}</span>
        <Icon name="calendar_today" className="ssel-chevron" />
      </button>
      {required && <input className="ssel-required-proxy" tabIndex={-1} aria-hidden="true" required value={value} onChange={() => {}} />}

      {isOpen && (
        <div className="dpk-panel">
          <div className="dpk-head">
            <button type="button" className="dpk-nav" tabIndex={-1} aria-label="Poprzedni miesiąc" onMouseDown={(e) => e.preventDefault()} onClick={() => setCursor((c) => addMonths(c, -1))}>
              <Icon name="chevron_left" />
            </button>
            <span className="dpk-month">
              {MONTHS[cursor.getMonth()]} {cursor.getFullYear()}
            </span>
            <button type="button" className="dpk-nav" tabIndex={-1} aria-label="Następny miesiąc" onMouseDown={(e) => e.preventDefault()} onClick={() => setCursor((c) => addMonths(c, 1))}>
              <Icon name="chevron_right" />
            </button>
          </div>
          <div
            ref={gridRef}
            className="dpk-grid"
            role="grid"
            tabIndex={0}
            aria-label={`${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`}
            aria-activedescendant={`dpk-${cursorIso}`}
            onKeyDown={handleGridKeyDown}
          >
            {WEEKDAYS.map((w) => (
              <span key={w} className="dpk-weekday" role="columnheader">
                {w}
              </span>
            ))}
            {days.map((d) => {
              const dIso = iso(d);
              const cls = [
                'dpk-day',
                d.getMonth() !== cursor.getMonth() && 'is-outside',
                dIso === todayIso && 'is-today',
                dIso === value && 'is-selected',
                dIso === cursorIso && 'is-cursor',
              ]
                .filter(Boolean)
                .join(' ');
              return (
                <span
                  key={dIso}
                  id={`dpk-${dIso}`}
                  role="gridcell"
                  aria-selected={dIso === value}
                  className={cls}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(d)}
                >
                  {d.getDate()}
                </span>
              );
            })}
          </div>
          <p className="dpk-hint">←→↑↓ dzień · PgUp/PgDn miesiąc · Enter wybiera</p>
        </div>
      )}
    </div>
  );
}
