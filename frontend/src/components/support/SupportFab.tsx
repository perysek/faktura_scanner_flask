import { useLayoutEffect, useState } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { supportCorner } from './supportCorner';
import type { SupportCorner } from './supportCorner';

const HINT = 'Zgłoś problem lub zaproponuj, co zmienić czy dodać';

export interface SupportFabProps {
  /** True while the ticket pop-out is on screen: the FAB steps aside and comes back on close. */
  hidden: boolean;
  onOpen: () => void;
}

/**
 * Round phone button in <main>'s bottom-left corner: the entry point to
 * SupportTicketModal, which pops out of this same corner. Re-measured whenever
 * <main> changes size (sidebar hidden/shown, window resized, tab bar on/off).
 */
export function SupportFab({ hidden, onOpen }: SupportFabProps) {
  const [corner, setCorner] = useState<SupportCorner | null>(null);

  useLayoutEffect(() => {
    const update = () => setCorner(supportCorner());
    update();
    const main = document.getElementById('main-content');
    const observer = new ResizeObserver(update);
    if (main) observer.observe(main);
    window.addEventListener('resize', update);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', update);
    };
  }, []);

  if (!corner) return null;

  return (
    <button
      type="button"
      className={`support-fab${hidden ? ' support-fab--hidden' : ''}`}
      style={{ left: corner.left, bottom: corner.bottom }}
      aria-label={HINT}
      aria-haspopup="dialog"
      tabIndex={hidden ? -1 : undefined}
      onClick={onOpen}
    >
      <Icon name="call" />
      <span className="support-fab-hint" aria-hidden="true">
        {HINT}
      </span>
    </button>
  );
}
