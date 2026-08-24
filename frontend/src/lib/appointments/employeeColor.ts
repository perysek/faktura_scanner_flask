/** Ported 1:1 from `static/js/employee-filter.js`'s `EMP_COLORS`/`empColor()` —
 * shared across every Wizyty page (list, 3 calendar views, detail hero avatar)
 * so "which employee is this" reads as the same colour everywhere. */
export const EMP_COLORS = ['#1d4ed8', '#047857', '#7e22ce', '#b45309', '#0e7490', '#be185d', '#4338ca', '#15803d'];

export function empColor(id: number | string | null | undefined): string {
  if (id === null || id === undefined || id === '') return '#9ca3af';
  return EMP_COLORS[Math.abs(Number(id)) % EMP_COLORS.length];
}
