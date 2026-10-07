import type { KeyboardEvent } from 'react';
import './sms.css';

export interface SmsTabDef<K extends string> {
  key: K;
  label: string;
  /** Shown as a count pill; `null`/`undefined` hides it (count not known yet). */
  count?: number | null;
}

export interface SmsTabsProps<K extends string> {
  tabs: SmsTabDef<K>[];
  active: K;
  onChange: (key: K) => void;
  ariaLabel: string;
  /** Unique per page: ids the tabpanel references (`tabId` / `panelId`). */
  idPrefix: string;
}

export const tabId = (prefix: string, key: string) => `${prefix}-tab-${key}`;
export const panelId = (prefix: string, key: string) => `${prefix}-panel-${key}`;

/**
 * Two-or-more-tab strip in the app's `ab-tabs` / `analytics-tabs` idiom, with real tablist semantics:
 * roving tabindex (only the active tab is in the tab order) and Left/Right/Home/End to move.
 * The caller renders the panel: `<div role="tabpanel" id={panelId(...)} aria-labelledby={tabId(...)}>`.
 */
export function SmsTabs<K extends string>({ tabs, active, onChange, ariaLabel, idPrefix }: SmsTabsProps<K>) {
  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = -1;
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    if (next < 0) return;
    e.preventDefault();
    onChange(tabs[next].key);
    document.getElementById(tabId(idPrefix, tabs[next].key))?.focus();
  }

  return (
    <div className="sms-tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab, i) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            id={tabId(idPrefix, tab.key)}
            aria-selected={isActive}
            aria-controls={panelId(idPrefix, tab.key)}
            tabIndex={isActive ? 0 : -1}
            className={`sms-tab${isActive ? ' active' : ''}`}
            onClick={() => onChange(tab.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {tab.label}
            {tab.count != null && <span className={`sms-tab-count${tab.count === 0 ? ' zero' : ''}`}>{tab.count}</span>}
          </button>
        );
      })}
    </div>
  );
}
