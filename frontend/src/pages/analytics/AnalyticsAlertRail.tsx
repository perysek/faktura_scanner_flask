import { useApiData } from '../../lib/useApiData';
import { analyticsDashboardApi } from '../../lib/api/analyticsDashboard';
import { Icon } from '../../lib/icons/Icon';
import { formatPLN } from '../../lib/format';
import type { PeriodParams } from '../../types/analyticsDashboard';
import type { AnalyticsTabKey } from './AnalyticsDashboardPage';

/**
 * "Wymaga uwagi" — risk-first alert rail pinned above the tabs. BeCreative
 * ideation pick (2026-09-22): a salon owner's morning priority is what needs
 * action, not an arbitrary section order, so the things that used to be
 * buried mid-scroll (at-risk clients, elevated no-shows, unpaid invoices, a
 * loss-making period) surface first. Every figure here is already fetched
 * for other cards elsewhere on the page — no new backend, no duplicate logic.
 */
export function AnalyticsAlertRail({ period, onNavigateTab }: { period: PeriodParams; onNavigateTab: (tab: AnalyticsTabKey) => void }) {
  const profitState = useApiData(() => analyticsDashboardApi.profit(period), [period.period, period.startDate, period.endDate]);
  const occupancyState = useApiData(() => analyticsDashboardApi.occupancy(period), [period.period, period.startDate, period.endDate]);
  const clientsState = useApiData(() => analyticsDashboardApi.clients(period), [period.period, period.startDate, period.endDate]);

  const profit = profitState.data;
  const occupancy = occupancyState.data;
  const clients = clientsState.data?.metrics;

  if (profitState.loading || occupancyState.loading || clientsState.loading) return null;

  type Pill = { key: string; severity: 'error' | 'warning' | 'ok'; icon: string; label: string; tab: AnalyticsTabKey };
  const pills: Pill[] = [];

  if (profit && profit.net_profit < 0) {
    pills.push({ key: 'loss', severity: 'error', icon: 'error', label: `Strata netto: ${formatPLN(profit.net_profit)}`, tab: 'overview' });
  }
  if (profit && profit.invoice_details.unpaid_count > 0) {
    pills.push({
      key: 'unpaid',
      severity: 'warning',
      icon: 'payments',
      label: `${profit.invoice_details.unpaid_count} niezapłaconych faktur (${formatPLN(profit.invoice_details.unpaid_amount)})`,
      tab: 'overview',
    });
  }
  if (occupancy && occupancy.no_show_rate > 10) {
    pills.push({ key: 'noshow', severity: 'warning', icon: 'warning', label: `Nieobecności ${occupancy.no_show_rate.toFixed(1)}% (${occupancy.no_shows})`, tab: 'occupancy' });
  }
  if (occupancy && occupancy.cancellation_rate > 15) {
    pills.push({ key: 'cancel', severity: 'warning', icon: 'schedule', label: `Odwołania ${occupancy.cancellation_rate.toFixed(1)}% (${occupancy.cancelled})`, tab: 'occupancy' });
  }
  if (clients && clients.at_risk_clients.length > 0) {
    pills.push({
      key: 'at-risk',
      severity: clients.at_risk_clients.length > 3 ? 'error' : 'warning',
      icon: 'person',
      label: `${clients.at_risk_clients.length} klientów zagrożonych utratą`,
      tab: 'clients',
    });
  }

  if (pills.length === 0) {
    pills.push({ key: 'ok', severity: 'ok', icon: 'check_circle', label: 'Brak pilnych spraw w tym okresie', tab: 'overview' });
  }

  return (
    <div className="abiz-alert-rail" aria-label="Wymaga uwagi">
      {pills.map((p) => (
        <button key={p.key} type="button" className={`abiz-alert-pill severity-${p.severity}`} onClick={() => onNavigateTab(p.tab)}>
          <Icon name={p.icon} />
          {p.label}
        </button>
      ))}
    </div>
  );
}
