import type { CSSProperties } from 'react';
import { isVipClient } from '../../components/clients/TrendSparkline';
import type { Client } from '../../types/client';

/** State + helpers shared by the desktop table (ClientsListPage) and the phone
 * card list (ClientsMobileView), so the two renderings can't drift apart. */

export type FilterKey = 'active' | 'vip' | 'inactive';
export type SortField = 'full_name' | 'last_visit_date' | 'next_visit_date' | 'completed_visits' | 'no_show_count' | 'is_active';

export interface SortState {
  field: SortField;
  dir: 'asc' | 'desc';
}

/** First direction when a field is picked from the phone sort sheet: the one a person
 * actually wants to see first (newest visit, nearest booking, A→Z, biggest counts). */
export const DEFAULT_SORT_DIR: Record<SortField, SortState['dir']> = {
  full_name: 'asc',
  last_visit_date: 'desc',
  next_visit_date: 'asc',
  completed_visits: 'desc',
  no_show_count: 'desc',
  is_active: 'desc',
};

/** Tomorrow as YYYY-MM-DD in the LOCAL calendar (toISOString() would be UTC and can land on the wrong day). */
export function tomorrowIso(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/**
 * "Umów wizytę" target: the new-visit form with the client, tomorrow's date, the logged-in
 * user's own employee (only if their account is linked to one) and the service of the client's
 * last visit (only if they have one) already filled in. `from=klienci` makes the form's cancel
 * come back to the clients list. The form itself drops a service the employee doesn't offer.
 */
export function newVisitHref(client: Client, linkedEmployeeId: number | null): string {
  const params = new URLSearchParams({ client_id: String(client.id), date: tomorrowIso(), from: 'klienci' });
  if (linkedEmployeeId) params.set('employee_id', String(linkedEmployeeId));
  if (client.last_service_id) params.set('service_id', String(client.last_service_id));
  return `/wizyty/nowa?${params}`;
}

/** Index bucket for non-letters (a name starting with a digit or symbol). */
export const OTHER_LETTER = '#';

/** The alphabet-index letter a client files under: the first letter of the name shown on the card
 * (upper-cased in Polish, so ł → Ł; Polish letters with diacritics are letters of their own). */
export function clientLetter(client: Client): string {
  const first = client.full_name.trim().charAt(0).toLocaleUpperCase('pl');
  return /\p{L}/u.test(first) ? first : OTHER_LETTER;
}

/** The letters present in the list, in Polish alphabetical order (A, Ą, B, … Ż), "#" last — only
 * letters that have a client, so the index never offers a dead tap. */
export function alphabetLetters(clients: Client[]): string[] {
  const collator = new Intl.Collator('pl');
  return [...new Set(clients.map(clientLetter))].sort((a, b) => {
    if (a === OTHER_LETTER) return 1;
    if (b === OTHER_LETTER) return -1;
    return collator.compare(a, b);
  });
}

export function clientInitials(client: Client): string {
  return `${client.first_name.charAt(0)}${(client.last_name || '').charAt(0)}`.toUpperCase();
}

/** Avatar ring: red for a no-show risk (> 2), accent for VIP, none otherwise. */
export function clientRingStyle(client: Client): CSSProperties | undefined {
  const isRisk = (client.no_show_count ?? 0) > 2;
  const color = isRisk ? 'var(--color-error)' : isVipClient(client) ? 'var(--color-accent)' : null;
  return color ? { boxShadow: `0 0 0 2px #fff, 0 0 0 3.5px ${color}` } : undefined;
}
