/** Quiet time after the last keystroke before a picker's list re-filters. Shared
 * by every employee/client picker so they all feel the same. */
export const SEARCH_DEBOUNCE_MS = 300;

/** Case-, diacritic- and `ł`-insensitive: "lukasz" finds "Łukasz Kowalski".
 * NFD alone doesn't split `ł` (it has no decomposition), hence the explicit swap. */
export function normalizeForSearch(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[łŁ]/g, 'l')
    .toLowerCase();
}

/** Keeps only items whose label CONTAINS the typed text. Empty query = all items. */
export function filterByLabel<T>(items: T[], query: string, getLabel: (item: T) => string): T[] {
  const needle = normalizeForSearch(query.trim());
  if (!needle) return items;
  return items.filter((item) => normalizeForSearch(getLabel(item)).includes(needle));
}
