import { useCallback, useId, useLayoutEffect, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, RefObject } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useDebouncedValue } from '../../lib/useDebouncedValue';
import { filterByLabel, SEARCH_DEBOUNCE_MS } from '../../lib/searchOptions';

export interface SearchableSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SearchableSelectProps {
  id?: string;
  /** Selected option's `value` ('' = nothing selected). */
  value: string;
  onChange: (value: string) => void;
  options: SearchableSelectOption[];
  /** Trigger text while nothing is selected. When the field is NOT `required` it
   * also becomes the first list item — the "clear" choice, like a native
   * <select>'s empty <option>. */
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  autoFocus?: boolean;
  invalid?: boolean;
  /** Skin for the trigger button: `form-select` (default) or `refined-select`. */
  triggerClassName?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  /** Accessible name for label-less uses (filters); the selected value is appended. */
  'aria-label'?: string;
}

/** Room below which a panel prefers flipping above the trigger. */
const COMFORTABLE_PX = 220;
const MAX_PANEL_PX = 340;
const MIN_PANEL_WIDTH_PX = 208;
const GAP_PX = 4;
const EDGE_PX = 8;

function firstEnabledIndex(list: SearchableSelectOption[]): number {
  return list.findIndex((o) => !o.disabled);
}

function stepEnabled(list: SearchableSelectOption[], from: number, dir: 1 | -1): number {
  for (let i = from + dir; i >= 0 && i < list.length; i += dir) {
    if (!list[i].disabled) return i;
  }
  return from;
}

interface PanelProps {
  triggerRef: RefObject<HTMLButtonElement | null>;
  listboxId: string;
  options: SearchableSelectOption[];
  value: string;
  searchPlaceholder: string;
  emptyText: string;
  focusSearch: boolean;
  onPick: (value: string) => void;
  onClose: (returnFocus: boolean) => void;
}

/**
 * Mounted only while the dropdown is open, so the query (and its debounce) start
 * empty on every open without any reset logic.
 */
function SearchableSelectPanel({ triggerRef, listboxId, options, value, searchPlaceholder, emptyText, focusSearch, onPick, onClose }: PanelProps) {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, SEARCH_DEBOUNCE_MS);
  const filtered = useMemo(() => filterByLabel(options, debouncedQuery, (o) => o.label), [options, debouncedQuery]);

  const [activeIndex, setActiveIndex] = useState(() => {
    const selected = options.findIndex((o) => o.value === value && !o.disabled);
    return selected >= 0 ? selected : firstEnabledIndex(options);
  });
  // Re-filtering invalidates the old index: jump to the first match (render-phase
  // state adjustment, so there is never a frame with a stale highlight).
  const [seenQuery, setSeenQuery] = useState(debouncedQuery);
  if (seenQuery !== debouncedQuery) {
    setSeenQuery(debouncedQuery);
    setActiveIndex(firstEnabledIndex(filtered));
  }

  const panelRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // One Escape closes one layer — see lib/a11y/escapeScope.ts.
  useEscapeClaim(true);

  const reposition = useCallback(() => {
    const trigger = triggerRef.current;
    const panel = panelRef.current;
    if (!trigger || !panel) return;

    const vv = window.visualViewport;
    const viewTop = vv?.offsetTop ?? 0;
    const viewBottom = viewTop + (vv?.height ?? window.innerHeight);
    const rect = trigger.getBoundingClientRect();

    const below = viewBottom - rect.bottom - GAP_PX - EDGE_PX;
    const above = rect.top - viewTop - GAP_PX - EDGE_PX;
    const flipUp = below < COMFORTABLE_PX && above > below;
    const room = Math.max(flipUp ? above : below, 120);

    const width = Math.max(rect.width, MIN_PANEL_WIDTH_PX);
    const left = Math.max(EDGE_PX, Math.min(rect.left, window.innerWidth - width - EDGE_PX));
    const top = flipUp ? rect.top - GAP_PX : rect.bottom + GAP_PX;

    panel.style.width = `${width}px`;
    panel.style.maxHeight = `${Math.min(MAX_PANEL_PX, room)}px`;
    panel.style.transform = flipUp ? 'translateY(-100%)' : '';
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;

    // `position: fixed` is measured from the viewport unless an ancestor has a
    // transform/filter, which silently re-bases it. Measure where the panel
    // really landed and absorb any offset, so it can't drift off its trigger.
    const landed = panel.getBoundingClientRect();
    const dx = landed.left - left;
    const dy = landed.top - (flipUp ? top - landed.height : top);
    if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
      panel.style.left = `${left - dx}px`;
      panel.style.top = `${top - dy}px`;
    }
  }, [triggerRef]);

  // Before paint, and again whenever filtering changes the panel's height.
  useLayoutEffect(() => {
    reposition();
  }, [reposition, filtered.length]);

  useEffect(() => {
    function onViewportChange(event: Event) {
      // The option list scrolling inside the panel must not re-anchor the panel.
      if (event.target instanceof Node && panelRef.current?.contains(event.target)) return;
      reposition();
    }
    const vv = window.visualViewport;
    window.addEventListener('scroll', onViewportChange, true);
    window.addEventListener('resize', onViewportChange);
    vv?.addEventListener('resize', onViewportChange);
    vv?.addEventListener('scroll', onViewportChange);
    return () => {
      window.removeEventListener('scroll', onViewportChange, true);
      window.removeEventListener('resize', onViewportChange);
      vv?.removeEventListener('resize', onViewportChange);
      vv?.removeEventListener('scroll', onViewportChange);
    };
  }, [reposition]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      onClose(false);
    }
    document.addEventListener('click', onDocClick, true);
    return () => document.removeEventListener('click', onDocClick, true);
  }, [onClose, triggerRef]);

  useEffect(() => {
    if (focusSearch) searchRef.current?.focus({ preventScroll: true });
  }, [focusSearch]);

  // Keep the highlighted row visible. Manual scrollTop (not scrollIntoView) so
  // the page behind never scrolls as a side effect.
  useEffect(() => {
    const list = listRef.current;
    const row = list?.children[activeIndex] as HTMLElement | undefined;
    if (!list || !row) return;
    if (row.offsetTop < list.scrollTop) list.scrollTop = row.offsetTop;
    else if (row.offsetTop + row.offsetHeight > list.scrollTop + list.clientHeight) list.scrollTop = row.offsetTop + row.offsetHeight - list.clientHeight;
  }, [activeIndex, filtered]);

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((i) => stepEnabled(filtered, i, 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((i) => stepEnabled(filtered, i, -1));
    } else if (event.key === 'Enter') {
      // Never let Enter submit the <form> this dropdown lives in.
      event.preventDefault();
      // Typed less than SEARCH_DEBOUNCE_MS ago: the visible list is still the
      // previous one, so act on what the user has actually typed, not on the stale rows.
      const inSync = query === debouncedQuery;
      const list = inSync ? filtered : filterByLabel(options, query, (o) => o.label);
      const picked = list[inSync ? activeIndex : firstEnabledIndex(list)];
      if (picked && !picked.disabled) onPick(picked.value);
    } else if (event.key === 'Tab') {
      onClose(false);
    }
  }

  const activeId = activeIndex >= 0 && activeIndex < filtered.length ? `${listboxId}-opt-${activeIndex}` : undefined;

  return (
    <div ref={panelRef} className="ssel-panel">
      <div className="ssel-search">
        <Icon name="search" />
        <input
          ref={searchRef}
          type="text"
          className="ssel-search-input"
          role="combobox"
          aria-expanded="true"
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={activeId}
          aria-label={searchPlaceholder}
          placeholder={searchPlaceholder}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
        />
      </div>
      <ul ref={listRef} id={listboxId} role="listbox" className="ssel-list">
        {filtered.length === 0 ? (
          <li className="ssel-empty" role="presentation">
            {emptyText}
          </li>
        ) : (
          filtered.map((option, i) => {
            const selected = option.value === value;
            return (
              <li
                key={option.value}
                id={`${listboxId}-opt-${i}`}
                role="option"
                aria-selected={selected}
                aria-disabled={option.disabled || undefined}
                className={`ssel-option${i === activeIndex ? ' is-active' : ''}${selected ? ' is-selected' : ''}`}
                // Keep focus in the search box (and the phone keyboard up) while tapping a row.
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => !option.disabled && setActiveIndex(i)}
                onClick={() => !option.disabled && onPick(option.value)}
              >
                <span className="ssel-option-label">{option.label}</span>
                {selected && <Icon name="check" className="ssel-option-check" />}
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}

/**
 * Drop-in replacement for a native <select> that adds a type-to-filter search box
 * above the list (debounced, see SEARCH_DEBOUNCE_MS). Used for every employee and
 * client picker. Same value-in/value-out contract as the rest of the form
 * primitives, but `onChange` receives the new value directly instead of an event.
 */
export function SearchableSelect({
  id,
  value,
  onChange,
  options,
  placeholder,
  required,
  disabled,
  autoFocus,
  invalid,
  triggerClassName = 'form-select',
  searchPlaceholder = 'Szukaj…',
  emptyText = 'Brak wyników',
  'aria-label': ariaLabel,
}: SearchableSelectProps) {
  const generatedId = useId();
  const listboxId = `${id ?? generatedId}-listbox`;
  const [isOpen, setIsOpen] = useState(false);
  const [focusSearch, setFocusSearch] = useState(true);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const listOptions = useMemo(() => {
    const hasEmptyChoice = options.some((o) => o.value === '');
    return placeholder !== undefined && !required && !hasEmptyChoice ? [{ value: '', label: placeholder }, ...options] : options;
  }, [options, placeholder, required]);

  const selected = options.find((o) => o.value === value);
  const triggerText = selected?.label ?? placeholder ?? '';

  const close = useCallback((returnFocus: boolean) => {
    setIsOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  function open(withSearchFocus: boolean) {
    if (disabled) return;
    setFocusSearch(withSearchFocus);
    setIsOpen(true);
  }

  function handlePick(next: string) {
    onChange(next);
    close(true);
  }

  return (
    <div
      className="ssel-root"
      onKeyDown={(event) => {
        if (isOpen && event.key === 'Escape') {
          event.stopPropagation();
          close(true);
        }
      }}
    >
      <button
        type="button"
        ref={triggerRef}
        id={id}
        className={`ssel-trigger ${triggerClassName}${invalid ? ' error' : ''}`}
        disabled={disabled}
        autoFocus={autoFocus}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={isOpen ? listboxId : undefined}
        aria-label={ariaLabel ? `${ariaLabel}: ${triggerText}` : undefined}
        onClick={(event) => {
          if (isOpen) return close(true);
          // A finger tap on a phone must not summon the keyboard before the user
          // has even seen the list; keyboard-initiated opens (detail === 0) always focus search.
          const touchTap = event.detail > 0 && window.matchMedia('(pointer: coarse)').matches;
          open(!touchTap);
        }}
        onKeyDown={(event) => {
          if (!isOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
            event.preventDefault();
            open(true);
          }
        }}
      >
        <span className={`ssel-value${selected ? '' : ' is-placeholder'}`}>{triggerText || ' '}</span>
        <Icon name="expand_more" className="ssel-chevron" />
      </button>

      {/* A <button> can't carry `required`, so mirror the value into an invisible
          native input laid exactly over the trigger: the browser's own "fill out
          this field" validation keeps working as it did with <select required>,
          and its bubble points at the control. When validation focuses this proxy
          (instead of the trigger) the open keys still work and `:focus-within`
          paints the trigger's focus ring. */}
      {required && (
        <input
          className="ssel-required-proxy"
          tabIndex={-1}
          aria-hidden="true"
          required
          value={value}
          onChange={() => {}}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
              event.preventDefault(); // Enter must not submit the form from here
              open(true);
            }
          }}
        />
      )}

      {isOpen && (
        <SearchableSelectPanel
          triggerRef={triggerRef}
          listboxId={listboxId}
          options={listOptions}
          value={value}
          searchPlaceholder={searchPlaceholder}
          emptyText={emptyText}
          focusSearch={focusSearch}
          onPick={handlePick}
          onClose={close}
        />
      )}
    </div>
  );
}
