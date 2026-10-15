import { Icon } from '../../lib/icons/Icon';

const HINT = 'Zgłoś problem lub zaproponuj, co zmienić czy dodać';

/** Id of the launcher's untransformed wrapper: supportCorner() reads its height. */
export const SUPPORT_LAUNCHER_ID = 'support-launcher';

export interface SupportLauncherProps {
  /** True while the ticket pop-out is on screen: the button steps aside and comes back on close. */
  hidden: boolean;
  onOpen: () => void;
  /** Conversations with an unread administrator answer → red dot + a different hint. */
  unread?: number;
}

/**
 * Round phone button at the bottom-right of the sidebar's nav area, just above
 * the user bar: the entry point to SupportTicketModal, which pops out at this
 * button's height.
 */
export function SupportLauncher({ hidden, onOpen, unread = 0 }: SupportLauncherProps) {
  const hint = unread > 0 ? `Administrator odpisał (${unread}) — kliknij, żeby przeczytać` : HINT;
  return (
    <div className="sidebar-support">
      {/* The wrapper is never transformed, so it measures true even while the button is shrunk away. */}
      <span id={SUPPORT_LAUNCHER_ID} className="support-fab-slot">
        <button
          type="button"
          className={`support-fab${hidden ? ' support-fab--hidden' : ''}`}
          aria-label={hint}
          aria-haspopup="dialog"
          tabIndex={hidden ? -1 : undefined}
          onClick={onOpen}
        >
          <Icon name="call" />
          {unread > 0 && <span className="support-fab-dot" aria-hidden="true" />}
          <span className="support-fab-hint" aria-hidden="true">
            {hint}
          </span>
        </button>
      </span>
    </div>
  );
}
