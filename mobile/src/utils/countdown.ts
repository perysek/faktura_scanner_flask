/** Ported 1:1 from the design mockup's fmtCountdown — "H:MM:SS" once an hour
 * remains, else "M:SS" with no leading zero on minutes. */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return (h > 0 ? `${h}:${pad(m)}` : String(m)) + ':' + pad(s);
}
