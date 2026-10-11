/** Compact client label of the calendar visit bars (day, week and month views):
 * first name cut to its initial, then the rest — "Aneta Kozłowska" → "A. Kozłowska".
 *
 * The list payload only carries the concatenated `client_name`, so the split is positional:
 * first word = first name, everything after it = last name. A one-word name stays as is,
 * no client gives "Bez klienta". */
export function clientLabel(name: string | null): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return 'Bez klienta';
  if (words.length === 1) return words[0];
  // Array.from keeps a surrogate pair whole; pl-PL uppercasing handles ś/ł/ż initials.
  const initial = Array.from(words[0])[0].toLocaleUpperCase('pl-PL');
  return `${initial}. ${words.slice(1).join(' ')}`;
}
