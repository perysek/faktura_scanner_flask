import { useState } from 'react';
import { useApiData } from '../../lib/useApiData';
import { employeeAnalyticsApi } from '../../lib/api/employeeAnalytics';
import { formatPLN } from '../../lib/format';
import { EmployeeAnalyticsRevenueTab } from './EmployeeAnalyticsRevenueTab';
import { EmployeeAnalyticsVisitsTab } from './EmployeeAnalyticsVisitsTab';
import { EmployeeAnalyticsSkillsTab } from './EmployeeAnalyticsSkillsTab';
import { EmployeeAnalyticsSatisfactionTab } from './EmployeeAnalyticsSatisfactionTab';

type TabKey = 'overview' | 'przychody' | 'wizyty' | 'umiejetnosci' | 'satysfakcja';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Przegląd' },
  { key: 'przychody', label: 'Przychody' },
  { key: 'wizyty', label: 'Wizyty' },
  { key: 'umiejetnosci', label: 'Umiejętności' },
  { key: 'satysfakcja', label: 'Satysfakcja' },
];

/**
 * "Analizy i wyniki" — ported from `templates/employees/view.html` +
 * `static/js/employees/analytics.js` on the `invoices-app` branch (the
 * Flask/Jinja original this SPA is replacing tab-by-tab). Same 5 tabs, same
 * `/api/employees/<id>/analytics/*` + `/services-with-ratings` endpoints
 * (both blueprints are shared, unchanged, between branches) — re-implemented
 * as React components instead of `loadTab()` + manual DOM writes, with
 * Chart.js driven by the `useChartCanvas` hook instead of a global `charts`
 * registry keyed by canvas id.
 *
 * One deliberate deviation from the original: instead of the original's
 * mobile hack (CSS hides the tab bar below 640px and force-shows the
 * Przychody + Wizyty panels stacked, silently dropping Przegląd/Umiejętności/
 * Satysfakcja from phones), the tab bar here scrolls horizontally on narrow
 * viewports — all 5 tabs stay reachable on every screen size.
 */
export function EmployeeAnalyticsSection({ employeeId }: { employeeId: number }) {
  const [active, setActive] = useState<TabKey>('overview');

  return (
    <div className="refined-card" id="analytics-section">
      <h2 className="section-title">Analizy i wyniki</h2>

      <div className="analytics-tabs" role="tablist" aria-label="Analizy i wyniki">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active === tab.key}
            className={`analytics-tab-btn${active === tab.key ? ' analytics-tab-active' : ''}`}
            onClick={() => setActive(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {active === 'overview' && <OverviewTab employeeId={employeeId} />}
      {active === 'przychody' && <EmployeeAnalyticsRevenueTab employeeId={employeeId} />}
      {active === 'wizyty' && <EmployeeAnalyticsVisitsTab employeeId={employeeId} />}
      {active === 'umiejetnosci' && <EmployeeAnalyticsSkillsTab employeeId={employeeId} />}
      {active === 'satysfakcja' && <EmployeeAnalyticsSatisfactionTab employeeId={employeeId} />}
    </div>
  );
}

/** "Przegląd" tab — 4 KPI cards, no chart. Ported from analytics.js's
 * `loadOverview()`. Kept inline here (rather than its own file) since it's
 * the only tab with no chart and no local state beyond the fetch itself. */
function OverviewTab({ employeeId }: { employeeId: number }) {
  const { data, loading, error } = useApiData(() => employeeAnalyticsApi.summary(employeeId), [employeeId]);

  if (loading) return <p className="analytics-loading">Ładowanie…</p>;
  if (error) return <p className="analytics-error">Błąd: {error.message}</p>;
  if (!data) return null;

  return (
    <div className="analytics-kpi-grid">
      <div className="analytics-kpi-card" style={{ background: 'rgba(37,99,235,0.05)', borderColor: 'rgba(37,99,235,0.15)' }}>
        <div className="analytics-kpi-label" style={{ color: 'var(--color-status-scheduled)' }}>
          Przychód
        </div>
        <div className="analytics-kpi-value">{formatPLN(data.total_revenue)}</div>
        <div className="analytics-kpi-sub">łącznie (12 mies.)</div>
      </div>
      <div className="analytics-kpi-card" style={{ background: 'rgba(155,44,44,0.05)', borderColor: 'rgba(155,44,44,0.15)' }}>
        <div className="analytics-kpi-label" style={{ color: 'var(--color-error)' }}>
          Koszt pracodawcy
        </div>
        <div className="analytics-kpi-value">{formatPLN(data.employer_cost)}</div>
        <div className="analytics-kpi-sub">wynagrodzenie + ZUS</div>
      </div>
      <div className="analytics-kpi-card" style={{ background: 'rgba(45,106,79,0.05)', borderColor: 'rgba(45,106,79,0.15)' }}>
        <div className="analytics-kpi-label" style={{ color: 'var(--color-success)' }}>
          Zysk netto
        </div>
        <div className="analytics-kpi-value" style={{ color: data.net_profit >= 0 ? 'var(--color-success)' : 'var(--color-error)' }}>
          {formatPLN(data.net_profit)}
        </div>
        <div className="analytics-kpi-sub">przychód − koszt</div>
      </div>
      <div className="analytics-kpi-card" style={{ background: 'rgba(126,34,206,0.05)', borderColor: 'rgba(126,34,206,0.15)' }}>
        <div className="analytics-kpi-label" style={{ color: 'var(--color-purple)' }}>
          Śr. wizyta
        </div>
        <div className="analytics-kpi-value">{formatPLN(data.avg_ticket)}</div>
        <div className="analytics-kpi-sub">{data.total_appointments} wizyt łącznie</div>
      </div>
    </div>
  );
}
