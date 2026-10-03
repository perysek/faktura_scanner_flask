/**
 * Eased scrolling that CHASES a moving target — for the A–Z index, where the target changes with every
 * letter the finger crosses.
 *
 * A fixed-duration tween would restart on each change (stutter, or lag behind the finger). This instead
 * moves the real scroll position a fraction of the remaining distance each frame, with a time constant
 * (`tauMs`) that makes it frame-rate independent: retargeting just changes where it is heading, with no
 * reset, so dragging across ten letters is one continuous glide. It decelerates into the target (no
 * overshoot, no bounce), and a very distant target is first jumped to within `teleportViewports`
 * viewports of itself, so the glide is always short: a screenful settles in ~0.35s, and the arrow to
 * the very top of a long list takes no longer than one letter does. (Time to settle from distance d is
 * about tau * ln(d / SNAP_PX); the long tail of the last few pixels is below what the eye can see.)
 *
 * Framework-free: the scroll position, the viewport and the frame clock are injected (see GlideHost),
 * so it is tested without a DOM.
 */
export interface GlideHost {
  getTop(): number;
  setTop(y: number): void;
  /** Largest scrollTop the container can reach. */
  maxTop(): number;
  /** Visible height of the container. */
  viewport(): number;
}

export interface GlideEnd {
  from: number;
  to: number;
  /** true when stopped early (the user took over, or the controller was disposed). */
  interrupted: boolean;
}

export interface GlideOptions {
  /** Time constant: ~63% of the remaining distance per tau (default 60ms: a screenful settles in ~0.35s,
   * inside the 300–500ms a large movement gets, and a touch shorter for a phone). */
  tauMs?: number;
  /** A target farther than this many viewports away is first jumped to within it (default 1). */
  teleportViewports?: number;
  /** Returns true when the user asked for reduced motion: then it just jumps. */
  reduced?: () => boolean;
  onStart?: (from: number) => void;
  onEnd?: (end: GlideEnd) => void;
  raf?: (cb: (t: number) => void) => number;
  cancelRaf?: (id: number) => void;
}

/** Within this the glide snaps to the target (2px is under what the eye registers at the end of a glide). */
const SNAP_PX = 2;
/** Minimum step per frame: browsers round scrollTop to a device pixel, so a step smaller than that
 * would round to zero and stall the glide a couple of pixels short. */
const MIN_STEP_PX = 1;
/** Longest frame gap the maths will integrate (a backgrounded tab returns with a huge one). */
const MAX_DT_MS = 48;
/** Safety net: a glide never runs longer than this, whatever the host does with setTop. */
const MAX_RUN_MS = 1500;

export function createGlide(host: GlideHost, options: GlideOptions = {}) {
  const tau = options.tauMs ?? 60;
  const teleport = options.teleportViewports ?? 1;
  const raf = options.raf ?? ((cb: (t: number) => void) => requestAnimationFrame(cb));
  const cancelRaf = options.cancelRaf ?? ((id: number) => cancelAnimationFrame(id));

  let rafId: number | null = null;
  let target = 0;
  let from = 0;
  let lastT: number | null = null;
  let startT: number | null = null;

  function end(interrupted: boolean) {
    if (rafId !== null) cancelRaf(rafId);
    rafId = null;
    lastT = null;
    startT = null;
    if (!interrupted) host.setTop(target);
    options.onEnd?.({ from, to: interrupted ? host.getTop() : target, interrupted });
  }

  function frame(t: number) {
    rafId = null;
    if (startT === null) startT = t;
    const dt = lastT === null ? 16 : Math.min(t - lastT, MAX_DT_MS);
    lastT = t;

    const cur = host.getTop();
    const remaining = target - cur;
    if (Math.abs(remaining) <= SNAP_PX || t - startT > MAX_RUN_MS) {
      end(false);
      return;
    }
    const eased = remaining * (1 - Math.exp(-dt / tau));
    const step = Math.sign(remaining) * Math.min(Math.abs(remaining), Math.max(Math.abs(eased), MIN_STEP_PX));
    host.setTop(cur + step);
    rafId = raf(frame);
  }

  return {
    /** Glide to `top` (clamped to the scrollable range). Safe to call again mid-glide to retarget. */
    to(top: number) {
      const next = Math.min(Math.max(0, top), Math.max(0, host.maxTop()));
      if (options.reduced?.()) {
        if (rafId !== null) end(true);
        host.setTop(next);
        return;
      }
      const cur = host.getTop();
      const limit = teleport * host.viewport();
      const gap = next - cur;
      if (Math.abs(gap) > limit) host.setTop(next - Math.sign(gap) * limit);
      target = next;
      if (rafId === null) {
        from = cur;
        lastT = null;
        startT = null;
        options.onStart?.(from);
        rafId = raf(frame);
      }
    },
    /** Stop where it is (the user grabbed the list). */
    stop() {
      if (rafId !== null) end(true);
    },
    active: () => rafId !== null,
  };
}
