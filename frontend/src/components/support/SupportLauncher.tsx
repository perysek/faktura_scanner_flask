import { Icon } from '../../lib/icons/Icon';

const HINT = 'Zgłoś problem lub zaproponuj, co zmienić czy dodać';

/** Id of the launcher's untransformed wrapper: supportCorner() reads its height. */
export const SUPPORT_LAUNCHER_ID = 'support-launcher';

export interface SupportLauncherProps {
  /** True while the ticket pop-out is on screen: the button steps aside and comes back on close. */
  hidden: boolean;
  onOpen: () => void;
}

/**
 * Round phone button at the bottom-right of the sidebar's nav area, just above
 * the user bar: the entry point to SupportTicketModal, which pops out at this
 * button's height.
 */
export function SupportLauncher({ hidden, onOpen }: SupportLauncherProps) {
  return (
    <div className="sidebar-support">
      {/* The wrapper is never transformed, so it measures true even while the button is shrunk away. */}
      <span id={SUPPORT_LAUNCHER_ID} className="support-fab-slot">
        <button
          type="button"
          className={`support-fab${hidden ? ' support-fab--hidden' : ''}`}
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
      </span>
    </div>
  );
}
