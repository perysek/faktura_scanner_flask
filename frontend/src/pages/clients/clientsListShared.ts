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

export function clientInitials(client: Client): string {
  return `${client.first_name.charAt(0)}${(client.last_name || '').charAt(0)}`.toUpperCase();
}

/** Avatar ring: red for a no-show risk (> 2), accent for VIP, none otherwise. */
export function clientRingStyle(client: Client): CSSProperties | undefined {
  const isRisk = (client.no_show_count ?? 0) > 2;
  const color = isRisk ? 'var(--color-error)' : isVipClient(client) ? 'var(--color-accent)' : null;
  return color ? { boxShadow: `0 0 0 2px #fff, 0 0 0 3.5px ${color}` } : undefined;
}
