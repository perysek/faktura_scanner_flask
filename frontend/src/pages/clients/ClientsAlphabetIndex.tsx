import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';

/** The bell the finger draws over the slots: the one under it slides out to the left (so the thumb
 * doesn't hide it) and grows; its neighbours follow with a smooth fall-off. All in slot heights, so
 * it scales with however many letters the list has. */
const MAX_SHIFT_PX = 37;
const MAX_GROW = 1.04;
const SIGMA = 1.4;

/** 1 right under the finger, easing to 0 a few slots away (Gaussian; distance in slots). */
function bell(distanceInSlots: number): number {
  return Math.exp(-(distanceInSlots * distanceInSlots) / (2 * SIGMA * SIGMA));
}

/** Key of the "scroll to the very top" slot — can never collide with a letter. */
const TOP = '^top';

interface Finger {
  /** Pointer position inside the bar, px from its top. */
  y: number;
  /** Height of one slot, px. */
  slot: number;
}

export interface ClientsAlphabetIndexProps {
  letters: string[];
  /** Fired when the finger lands on, or slides onto, a different letter. */
  onSelect: (letter: string) => void;
  /** Fired when the finger lands on, or slides onto, the arrow above "A". */
  onTop: () => void;
  /** Slid in (true) or slid out of the way (false). Stays mounted either way so it can animate. */
  visible: boolean;
  /** Viewport px the bar keeps clear above / below (sticky toolbar, bottom action bar). */
  top: number;
  bottom: number;
}

/**
 * Right-edge index: a bold arrow on top, then A–Z. Tap or drag along it: the first client under the
 * letter scrolls to the top of the list (the host does the scrolling; the arrow goes to the very
 * top), and the slots bulge toward the finger along a smooth bell curve, springing back when it
 * lifts. Pointer events + `touch-action: none`, so dragging the bar never scrolls the page itself;
 * the slots are real buttons too, for keyboard users.
 */
export function ClientsAlphabetIndex({ letters, onSelect, onTop, visible, top, bottom }: ClientsAlphabetIndexProps) {
  const barRef = useRef<HTMLDivElement>(null);
  const [finger, setFinger] = useState<Finger | null>(null);
  const [current, setCurrent] = useState<string | null>(null);
  const lastRef = useRef<string | null>(null);

  // Slot 0 is the arrow; letters follow.
  const keys = [TOP, ...letters];

  function select(key: string) {
    if (key === TOP) onTop();
    else onSelect(key);
  }

  function track(e: PointerEvent<HTMLDivElement>) {
    const bar = barRef.current;
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    const y = Math.min(Math.max(e.clientY - rect.top, 0), rect.height);
    const slot = rect.height / keys.length;
    const key = keys[Math.min(keys.length - 1, Math.floor(y / slot))];
    setFinger({ y, slot });
    setCurrent(key);
    if (key !== lastRef.current) {
      lastRef.current = key;
      select(key);
    }
  }

  function release() {
    lastRef.current = null;
    setFinger(null);
    setCurrent(null);
  }

  function slotStyle(i: number) {
    if (!finger) return undefined;
    const influence = bell(((i + 0.5) * finger.slot - finger.y) / finger.slot);
    return { transform: `translateX(${-MAX_SHIFT_PX * influence}px) scale(${1 + MAX_GROW * influence})` };
  }

  return (
    <div
      ref={barRef}
      className={`clients-alpha${finger ? ' is-active' : ''}${visible ? '' : ' is-hidden'}`}
      style={{ top, bottom }}
      role="group"
      aria-label="Skocz do litery"
      aria-hidden={!visible}
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        lastRef.current = null;
        track(e);
      }}
      onPointerMove={(e) => {
        if (e.currentTarget.hasPointerCapture(e.pointerId)) track(e);
      }}
      onPointerUp={release}
      onPointerCancel={release}
    >
      {keys.map((key, i) => (
        <button
          key={key}
          type="button"
          className={`clients-alpha-letter${key === TOP ? ' clients-alpha-top' : ''}${current === key ? ' is-current' : ''}`}
          aria-label={key === TOP ? 'Na początek listy' : `Litera ${key}`}
          // A real pointer press is handled on the bar above; this only runs for keyboard activation.
          onClick={(e) => {
            if (e.detail === 0) select(key);
          }}
        >
          <span className="clients-alpha-glyph" style={slotStyle(i)}>
            {key === TOP ? (
              // Bold arrow: a heavy stroke, not an icon-font glyph, so it matches the bold letters.
              <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" strokeWidth={3.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
                <path d="M12 20V5M5.5 11.5 12 5l6.5 6.5" />
              </svg>
            ) : (
              key
            )}
          </span>
        </button>
      ))}
    </div>
  );
}
