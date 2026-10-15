/** Gap between the support FAB / pop-out and <main>'s bottom-left corner. */
export const SUPPORT_GAP_PX = 16;

export interface SupportCorner {
  left: number;
  bottom: number;
}

/**
 * Bottom-left corner of <main>, as fixed `left`/`bottom` offsets. The FAB sits
 * here and the ticket pop-out grows out of the very same spot. Where the page
 * itself scrolls (<main> taller than the viewport) the bottom is clamped to the
 * viewport, and on phones it stays above the bottom tab bar.
 */
export function supportCorner(): SupportCorner {
  const main = document.getElementById('main-content');
  if (!main) return { left: SUPPORT_GAP_PX, bottom: SUPPORT_GAP_PX };
  const rect = main.getBoundingClientRect();
  let floor = Math.min(rect.bottom, window.innerHeight);
  const tabBar = document.querySelector('.mw-tabbar');
  if (tabBar) floor = Math.min(floor, tabBar.getBoundingClientRect().top);
  return {
    left: Math.max(rect.left, 0) + SUPPORT_GAP_PX,
    bottom: window.innerHeight - floor + SUPPORT_GAP_PX,
  };
}
