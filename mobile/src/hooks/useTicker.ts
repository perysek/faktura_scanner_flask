import { useEffect, useState } from 'react';

/** Re-renders the calling component every `intervalMs`, returning the current
 * timestamp — drives the live countdown pills/screens without re-fetching. */
export function useTicker(intervalMs: number = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
