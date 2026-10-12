/** First word cut to its initial, then the rest, joined by `sep`.
 *
 * The list payload only carries the concatenated name, so the split is positional:
 * first word = first name, everything after it = last name. A one-word name stays as is;
 * no name gives null (each caller has its own placeholder). */
function initialThenRest(name: string | null, sep: string): string | null {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  if (words.length === 1) return words[0];
  // Array.from keeps a surrogate pair whole; pl-PL uppercasing handles ś/ł/ż initials.
  const initial = Array.from(words[0])[0].toLocaleUpperCase('pl-PL');
  return `${initial}.${sep}${words.slice(1).join(' ')}`;
}

/** Compact client label of the calendar visit bars (day, week and month views):
 * "Aneta Kozłowska" → "A. Kozłowska"; no client gives "Bez klienta". */
export function clientLabel(name: string | null): string {
  return initialThenRest(name, ' ') ?? 'Bez klienta';
}

/** Compact employee label of the visits list's "Pracownik" column:
 * "Aneta Kozłowska" → "A.Kozłowska" (no space); no employee gives "—". */
export function employeeShortLabel(name: string | null): string {
  return initialThenRest(name, '') ?? '—';
}
