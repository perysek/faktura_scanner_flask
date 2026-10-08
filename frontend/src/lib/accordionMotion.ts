/**
 * Accordion motion — one clock for the panel heights AND the page scroll.
 *
 * A CSS height transition plus a separately-timed scroll animation start and end a frame or more
 * apart, and the panel edge visibly slides against the scroll. So a single requestAnimationFrame
 * loop writes every height and the scroll position from the same eased value, in the same frame:
 * both finish on the same frame by construction.
 *
 * Because every quantity is linear in that eased value, the scroll target only has to be right at
 * the end points: pre-calculate where the page must finish (`revealScrollTarget`), then interpolate.
 */

export const ACCORDION_MS = 340; // = --dur-card in styles/tokens.css
/** Matches the 1rem the page keeps under its last element (.refined-page padding-bottom). */
export const REVEAL_BOTTOM_GAP = 16;
export const REVEAL_TOP_GAP = 8;

/** 1 - (1-t)^4 — the closed form of --ease-out-quart. */
export function easeOutQuart(t: number): number {
  const u = 1 - Math.min(1, Math.max(0, t));
  return 1 - u * u * u * u;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export interface RevealInput {
  scrollTop: number;
  /** Visible height of the scroller — its bottom edge is the line right above the page footer. */
  viewportHeight: number;
  scrollHeight: number;
  /** The expanding card as laid out right now, in scroller-content coordinates. */
  targetTop: number;
  targetHeight: number;
  /** How much taller the expanding card is about to get. */
  targetGrowth: number;
  /** Summed height change of every card ABOVE the target (negative = they collapse, pulling it up). */
  growthAbove: number;
  /** Summed height change of all moving cards — the document's height change. */
  growthTotal: number;
  bottomGap: number;
  topGap: number;
}

/**
 * Where the scroller must finish for the expanded card's bottom border to sit right above the footer.
 * Returns the scroll position unchanged when the card fits without help.
 *
 *  1. Anchor: a card collapsing above the target pulls it up; cancel that, so the clicked header
 *     stays under the pointer.
 *  2. Overlap: if the card's final bottom border would sit below the footer line, scroll just far
 *     enough to put it on that line.
 *  3. A card taller than the viewport is pinned by its header instead — the header never leaves.
 */
export function revealScrollTarget(i: RevealInput): number {
  const finalTop = i.targetTop + i.growthAbove;
  const finalBottom = finalTop + i.targetHeight + i.targetGrowth;
  const visible = i.viewportHeight - i.bottomGap;

  let next = i.scrollTop + i.growthAbove;
  if (finalBottom > next + visible) next = finalBottom - visible;
  next = Math.min(next, finalTop - i.topGap);

  return clamp(next, 0, Math.max(0, i.scrollHeight + i.growthTotal - i.viewportHeight));
}

/** Parts of one panel the driver needs. `body` is the height-animated clip box, `inner` its natural-height content. */
export interface PanelEls {
  card: HTMLElement;
  body: HTMLElement;
  inner: HTMLElement;
}

/** Steady state: open = natural height and nothing clipped (focus rings!), closed = collapsed and out of the tab order. */
export function settlePanel(body: HTMLElement, open: boolean) {
  body.style.height = open ? 'auto' : '0px';
  body.style.overflow = open ? 'visible' : 'hidden';
  body.style.visibility = open ? 'visible' : 'hidden';
}

export interface MotionPlan {
  scroller: HTMLElement;
  tweens: { body: HTMLElement; from: number; to: number }[];
  /** null = leave the scroll position alone. */
  scrollTo: number | null;
  durationMs: number;
}

export function scrollParentOf(el: HTMLElement): HTMLElement | null {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const overflowY = getComputedStyle(p).overflowY;
    if (overflowY === 'auto' || overflowY === 'scroll') return p;
  }
  return null;
}

/**
 * Reads the layout (nothing is written) and decides what every panel should do so that only
 * `openKey` is open. Panels are re-planned from their *current* heights, so an animation the user
 * interrupts simply continues towards its state in the new plan.
 */
export function planAccordion<K>(panels: ReadonlyMap<K, PanelEls>, openKey: K | null, reducedMotion: boolean): MotionPlan | null {
  const ordered = [...panels.entries()].sort(([, a], [, b]) =>
    a.card.compareDocumentPosition(b.card) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
  );
  if (!ordered.length) return null;
  const scroller = scrollParentOf(ordered[0][1].card);
  if (!scroller) return null;

  const scrollerTop = scroller.getBoundingClientRect().top;
  const rows = ordered.map(([key, els]) => {
    const rect = els.card.getBoundingClientRect();
    const from = els.body.getBoundingClientRect().height;
    return {
      key,
      body: els.body,
      from,
      to: key === openKey ? els.inner.offsetHeight : 0,
      top: rect.top - scrollerTop + scroller.scrollTop,
      height: rect.height,
    };
  });
  const moving = rows.filter((r) => Math.abs(r.to - r.from) > 0.5);
  if (!moving.length) return null;

  let scrollTo: number | null = null;
  const targetIndex = rows.findIndex((r) => r.key === openKey && r.to - r.from > 0.5);
  if (targetIndex >= 0) {
    const target = rows[targetIndex];
    const next = revealScrollTarget({
      scrollTop: scroller.scrollTop,
      viewportHeight: scroller.clientHeight,
      scrollHeight: scroller.scrollHeight,
      targetTop: target.top,
      targetHeight: target.height,
      targetGrowth: target.to - target.from,
      growthAbove: rows.slice(0, targetIndex).reduce((sum, r) => sum + r.to - r.from, 0),
      growthTotal: rows.reduce((sum, r) => sum + r.to - r.from, 0),
      bottomGap: REVEAL_BOTTOM_GAP,
      topGap: REVEAL_TOP_GAP,
    });
    if (Math.abs(next - scroller.scrollTop) > 0.5) scrollTo = next;
  }

  return {
    scroller,
    tweens: moving.map((r) => ({ body: r.body, from: r.from, to: r.to })),
    scrollTo,
    durationMs: reducedMotion ? 0 : ACCORDION_MS,
  };
}

/** Runs a plan. Returns a canceller that stops where it is (the next plan starts from there). */
export function playMotion({ scroller, tweens, scrollTo, durationMs }: MotionPlan): () => void {
  const scrollFrom = scroller.scrollTop;
  const anchorBefore = scroller.style.overflowAnchor;
  scroller.style.overflowAnchor = 'none'; // the browser's own scroll anchoring would fight the manual scroll

  for (const t of tweens) {
    t.body.style.overflow = 'hidden';
    t.body.style.visibility = 'visible';
    t.body.style.height = `${t.from}px`;
  }

  let raf = 0;
  let scrolling = scrollTo !== null;
  const yieldToUser = () => {
    scrolling = false; // someone grabbed the scroll — the heights finish, the scroll is theirs
  };
  scroller.addEventListener('wheel', yieldToUser, { passive: true, once: true });
  scroller.addEventListener('touchstart', yieldToUser, { passive: true, once: true });

  const stop = () => {
    cancelAnimationFrame(raf);
    scroller.removeEventListener('wheel', yieldToUser);
    scroller.removeEventListener('touchstart', yieldToUser);
    scroller.style.overflowAnchor = anchorBefore;
  };
  const finish = () => {
    for (const t of tweens) settlePanel(t.body, t.to > 0);
    if (scrolling && scrollTo !== null) scroller.scrollTo({ top: scrollTo, behavior: 'instant' });
    stop();
  };

  if (durationMs <= 0) {
    finish();
    return stop;
  }

  let startedAt: number | null = null;
  const frame = (now: number) => {
    startedAt ??= now;
    const elapsed = now - startedAt;
    if (elapsed >= durationMs) {
      finish();
      return;
    }
    const e = easeOutQuart(elapsed / durationMs);
    for (const t of tweens) t.body.style.height = `${t.from + (t.to - t.from) * e}px`;
    if (scrolling && scrollTo !== null) scroller.scrollTo({ top: scrollFrom + (scrollTo - scrollFrom) * e, behavior: 'instant' });
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  return stop;
}
