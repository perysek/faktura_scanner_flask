import { SUPPORT_LAUNCHER_ID } from './SupportLauncher';

/** Gap between the ticket pop-out and <main>'s left edge. */
export const SUPPORT_GAP_PX = 16;

export interface SupportCorner {
  left: number;
  bottom: number;
}

/**
 * Where the ticket pop-out grows from, as fixed `left`/`bottom` offsets: <main>'s
 * left edge, at the height of the sidebar's phone button (the panel's bottom lines
 * up with the button's bottom). Without a measurable button, it falls back to
 * <main>'s bottom-left corner, kept above the phone tab bar. The tab bar is in the
 * DOM on desktop too, just display:none, with an all-zero rect: it only counts
 * when it is actually rendered.
 */
export function supportCorner(): SupportCorner {
  const main = document.getElementById('main-content');
  if (!main) return { left: SUPPORT_GAP_PX, bottom: SUPPORT_GAP_PX };
  const rect = main.getBoundingClientRect();
  const left = Math.max(rect.left, 0) + SUPPORT_GAP_PX;

  const launcher = document.getElementById(SUPPORT_LAUNCHER_ID)?.getBoundingClientRect();
  if (launcher && launcher.height > 0 && launcher.bottom > 0 && launcher.bottom <= window.innerHeight) {
    return { left, bottom: window.innerHeight - launcher.bottom };
  }

  let floor = Math.min(rect.bottom, window.innerHeight);
  const tabBar = document.querySelector('.mw-tabbar')?.getBoundingClientRect();
  if (tabBar && tabBar.height > 0) floor = Math.min(floor, tabBar.top);
  return { left, bottom: window.innerHeight - floor + SUPPORT_GAP_PX };
}
