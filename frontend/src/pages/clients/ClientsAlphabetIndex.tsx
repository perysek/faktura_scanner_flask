import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';

/** The bell the finger draws over the letters: the letter under it slides out to the left (so the
 * thumb doesn't hide it) and grows; its neighbours follow with a smooth fall-off. All in letter
 * heights, so it scales with however many letters the list has. */
const MAX_SHIFT_PX = 32;
const MAX_GROW = 0.9;
const SIGMA = 1.4;

/** 1 right under the finger, easing to 0 a few letters away (Gaussian; distance in letter slots). */
function bell(distanceInSlots: number): number {
  return Math.exp(-(distanceInSlots * distanceInSlots) / (2 * SIGMA * SIGMA));
}

interface Finger {
  /** Pointer position inside the bar, px from its top. */
  y: number;
  /** Height of one letter slot, px. */
  slot: number;
}

export interface ClientsAlphabetIndexProps {
  letters: string[];
  /** Fired when the finger lands on, or slides onto, a different letter. */
  onSelect: (letter: string) => void;
  /** Viewport px the bar keeps clear above / below (sticky toolbar, bottom action bar). */
  top: number;
  bottom: number;
}

/**
 * Right-edge A–Z index. Tap or drag along it: the first client under the letter scrolls to the top
 * of the list (the host does the scrolling), and the letters bulge toward the finger along a smooth
 * bell curve, springing back when it lifts. Pointer events + `touch-action: none`, so dragging the
 * bar never scrolls the page itself; the letters are real buttons too, for keyboard users.
 */
export function ClientsAlphabetIndex({ letters, onSelect, top, bottom }: ClientsAlphabetIndexProps) {
  const barRef = useRef<HTMLDivElement>(null);
  const [finger, setFinger] = useState<Finger | null>(null);
  const [current, setCurrent] = useState<string | null>(null);
  const lastRef = useRef<string | null>(null);

  function track(e: PointerEvent<HTMLDivElement>) {
    const bar = barRef.current;
    if (!bar || letters.length === 0) return;
    const rect = bar.getBoundingClientRect();
    const y = Math.min(Math.max(e.clientY - rect.top, 0), rect.height);
    const slot = rect.height / letters.length;
    const letter = letters[Math.min(letters.length - 1, Math.floor(y / slot))];
    setFinger({ y, slot });
    setCurrent(letter);
    if (letter !== lastRef.current) {
      lastRef.current = letter;
      onSelect(letter);
    }
  }

  function release() {
    lastRef.current = null;
    setFinger(null);
    setCurrent(null);
  }

  return (
    <div
      ref={barRef}
      className={`clients-alpha${finger ? ' is-active' : ''}`}
      style={{ top, bottom }}
      role="group"
      aria-label="Skocz do litery"
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
      {letters.map((letter, i) => {
        const influence = finger ? bell(((i + 0.5) * finger.slot - finger.y) / finger.slot) : 0;
        return (
          <button
            key={letter}
            type="button"
            className={`clients-alpha-letter${current === letter ? ' is-current' : ''}`}
            aria-label={`Litera ${letter}`}
            // A real pointer press is handled on the bar above; this only runs for keyboard activation.
            onClick={(e) => {
              if (e.detail === 0) onSelect(letter);
            }}
          >
            <span
              className="clients-alpha-glyph"
              style={{ transform: finger ? `translateX(${-MAX_SHIFT_PX * influence}px) scale(${1 + MAX_GROW * influence})` : undefined }}
            >
              {letter}
            </span>
          </button>
        );
      })}
    </div>
  );
}
