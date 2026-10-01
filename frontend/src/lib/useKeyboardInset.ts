import { useEffect, useState } from 'react';

export interface KeyboardInset {
  /** Pixels between the layout viewport's bottom edge and the visible area's
   * bottom edge — i.e. how much of the screen the on-screen keyboard covers. 0 when closed. */
  bottom: number;
  /** Height of the visible area (keyboard excluded), or null when unknown. */
  visibleHeight: number | null;
}

// A real soft keyboard is 200px+; anything smaller is browser-chrome jitter
// (collapsing URL bar etc.) and must not shift the sheet.
const KEYBOARD_MIN_PX = 100;

/**
 * For bottom-anchored `position: fixed` sheets with a text field: iOS Safari and
 * Android Chrome shrink only the VISUAL viewport when the keyboard opens, so a
 * `bottom: 0` fixed sheet ends up hidden behind it. Offset the sheet by `bottom`
 * (and cap its height with `visibleHeight`) to keep it above the keyboard.
 */
export function useKeyboardInset(active: boolean): KeyboardInset {
  const [state, setState] = useState<KeyboardInset>({ bottom: 0, visibleHeight: null });

  useEffect(() => {
    const vv = window.visualViewport;
    if (!active || !vv) {
      setState({ bottom: 0, visibleHeight: null });
      return;
    }
    const update = () => {
      const covered = Math.round(window.innerHeight - (vv.offsetTop + vv.height));
      setState(covered > KEYBOARD_MIN_PX ? { bottom: covered, visibleHeight: Math.round(vv.height) } : { bottom: 0, visibleHeight: null });
    };
    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
    };
  }, [active]);

  return state;
}
