/** Types for the Usługi + kategorie module — Faza 2. Cztery pod-strony
 * (lista, create/edit, szczegóły z historią cen + mikrousługami, kategorie)
 * — moduł-inventory.md korekta w toku (etykieta "Średnia" jak przy
 * Sprzedawcach okazała się zaniżona, patrz implementation-log.md). */

export type ServiceType = 'main' | 'addon';

export interface Service {
  id: number;
  name: string;
  description: string | null;
  category: string | null;
  duration_minutes: number;
  formatted_duration: string;
  price: number;
  currency: string;
  formatted_price: string;
  service_type: ServiceType;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  last_price_change_date?: string | null;
}

export interface ServiceFormValues {
  name: string;
  description: string | null;
  category?: string;
  duration_minutes: number;
  price: number;
  currency?: string;
  service_type: ServiceType;
  is_active?: boolean;
  change_reason?: string | null;
}

export interface ServiceStatistics {
  total_services?: number;
  active_services?: number;
  avg_price?: number;
}

export interface ServiceCategory {
  id: number;
  name: string;
  additional_description: string | null;
  service_count?: number;
}

export interface ServicePriceHistoryEntry {
  id: number;
  price: number;
  currency: string;
  effective_from: string | null;
  effective_to: string | null;
  changed_by_name: string | null;
  change_reason: string | null;
}

/** Raw addon/main-service row from ServiceAddonRepository — `dict(row)` off
 * the DB, not routed through row_to_service, so the field set is narrower. */
export interface CompatibleAddon {
  id: number;
  name: string;
  price: number;
  formatted_price?: string | null;
  duration_minutes: number;
  formatted_duration?: string | null;
  is_active: boolean;
}

export interface AddonRule {
  main_service_id: number;
}

export interface CategoryServiceRow {
  id: number;
  name: string;
  price: number;
  duration_minutes: number;
  service_type: ServiceType;
  is_active: boolean;
}
