import { useState } from 'react';
import '../employees/EmployeesListPage.css';
import './AnalyticsDashboardPage.css';
import { useAnalyticsPeriod } from './useAnalyticsPeriod';
import { AnalyticsPeriodBar } from './AnalyticsPeriodBar';
import { AnalyticsAlertRail } from './AnalyticsAlertRail';
import { AnalyticsOverviewTab } from './AnalyticsOverviewTab';
import { AnalyticsEmployeesTab } from './AnalyticsEmployeesTab';
import { AnalyticsClientsTab } from './AnalyticsClientsTab';
import { AnalyticsOccupancyTab } from './AnalyticsOccupancyTab';
import { AnalyticsServicesTab } from './AnalyticsServicesTab';
import { ScrollTopButton } from '../../components/ui/ScrollTopButton';
import type { PeriodParams } from '../../types/analyticsDashboard';

export type AnalyticsTabKey = 'overview' | 'employees' | 'clients' | 'occupancy' | 'services';

const TABS: { key: AnalyticsTabKey; label: string }[] = [
  { key: 'overview', label: 'Przegląd' },
  { key: 'employees', label: 'Pracownicy' },
  { key: 'clients', label: 'Klienci' },
  { key: 'occupancy', label: 'Obłożenie i szczyty' },
  { key: 'services', label: 'Ceny usług' },
];

/**
 * Analiza biznesowa — React port of `templates/analytics/dashboard.html` +
 * `static/js/analytics/dashboard.js` (449 + 1,475 lines, `/api/analytics/*`
 * already fully JSON, no backend changes). Deliberately NOT a 1:1 port —
 * BeCreative ideation (2026-09-22) picked a risk-first restructure over the
 * legacy's single 2000px scroll + jump-nav:
 *
 *  - A "Wymaga uwagi" alert rail sits above everything, surfacing at-risk
 *    clients / elevated no-shows / unpaid invoices / a loss-making period —
 *    all data already fetched for other cards, nothing new on the backend.
 *  - Real tabs replace the flat scroll; each of the 8 previously-orphaned
 *    "Trendy roczne" rolling charts moved into its matching tab instead of a
 *    disconnected zone that ignored the period selector.
 *  - Two rolling endpoints (`employee-utilisation`, `visit-frequency`) and the
 *    per-employee analytics API (`/employees/<id>/analytics/*`, already built
 *    for `EmployeeDetailPage`) existed in the backend but were never wired
 *    into this dashboard at all — both are live here now: the employee table
 *    links each row to its own full analytics page instead of duplicating it.
 */
export function AnalyticsDashboardPage() {
  const periodState = useAnalyticsPeriod();
  const [activeTab, setActiveTab] = useState<AnalyticsTabKey>('overview');

  const period: PeriodParams = { period: periodState.period, startDate: periodState.startDate, endDate: periodState.endDate };

  return (
    <div className="refined-page animate-fade-up">
      <div className="page-header">
        <div>
          <h1 className="page-title">Analiza biznesowa</h1>
        </div>
      </div>

      <AnalyticsPeriodBar periodState={periodState} />
      <AnalyticsAlertRail period={period} onNavigateTab={setActiveTab} />

      <div className="analytics-tabs" role="tablist" aria-label="Analiza biznesowa">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`analytics-tab-btn${activeTab === tab.key ? ' analytics-tab-active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <AnalyticsOverviewTab period={period} />}
      {activeTab === 'employees' && <AnalyticsEmployeesTab period={period} />}
      {activeTab === 'clients' && <AnalyticsClientsTab period={period} />}
      {activeTab === 'occupancy' && <AnalyticsOccupancyTab period={period} />}
      {activeTab === 'services' && <AnalyticsServicesTab period={period} />}

      <ScrollTopButton />
    </div>
  );
}
