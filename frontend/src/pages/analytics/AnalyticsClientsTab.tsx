import { Link } from 'react-router-dom';
import { useApiData } from '../../lib/useApiData';
import { analyticsDashboardApi } from '../../lib/api/analyticsDashboard';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import { formatPLN, formatDate } from '../../lib/format';
import type { PeriodParams } from '../../types/analyticsDashboard';

/** "Klienci" tab — client split + retention, top-10 clients, at-risk list (now
 * linked to `/klienci/:id`, unlike the legacy plain-text row — the query already
 * selects `c.id`, it just went unused), plus two rolling charts: new-clients
 * (already existed) and visit-frequency (backend-ready, never wired up before). */
export function AnalyticsClientsTab({ period }: { period: PeriodParams }) {
  const deps = [period.period, period.startDate, period.endDate];
  const clientsState = useApiData(() => analyticsDashboardApi.clients(period), deps);
  const topClientsState = useApiData(() => analyticsDashboardApi.topClients(period), deps);
  const newClientsState = useApiData(() => analyticsDashboardApi.rollingNewClients(), []);
  const visitFreqState = useApiData(() => analyticsDashboardApi.rollingVisitFrequency(), []);

  const metrics = clientsState.data?.metrics;
  const topClients = topClientsState.data?.clients ?? [];
  const newClientsMonths = newClientsState.data?.months ?? [];
  const visitFreq = visitFreqState.data?.distribution ?? [];

  const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
  const monthLabel = (monthStart: string) => {
    const [y, mo] = monthStart.split('-').map(Number);
    return `${PL_MONTHS[mo - 1]} ${y}`;
  };

  const splitChartRef = useChartCanvas(() => {
    if (!metrics) return null;
    const { new_clients, returning_clients } = metrics;
    if (new_clients === 0 && returning_clients === 0) return null;
    return {
      type: 'doughnut',
      data: { labels: ['Nowi klienci', 'Powracający'], datasets: [{ data: [new_clients, returning_clients], backgroundColor: [CHART_COLORS.blue, CHART_COLORS.green] }] },
      options: { responsive: true, maintainAspectRatio: false },
    };
  }, [metrics]);

  const newClientsChartRef = useChartCanvas(() => {
    if (newClientsMonths.length === 0) return null;
    return {
      type: 'line',
      data: { labels: newClientsMonths.map((m) => monthLabel(m.month_start)), datasets: [{ label: 'Nowi klienci', data: newClientsMonths.map((m) => m.new_clients), borderColor: CHART_COLORS.green, backgroundColor: CHART_COLORS.greenFill, borderWidth: 2, pointRadius: 4, fill: true, tension: 0.3 }] },
      options: { ...CHART_BASE_OPTIONS, plugins: { tooltip: { callbacks: { label: (ctx) => `Nowi klienci: ${ctx.parsed.y}` } } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
    };
  }, [newClientsMonths]);

  const visitFreqChartRef = useChartCanvas(() => {
    if (visitFreq.length === 0) return null;
    // 10+ visits collapse into one bucket, matching the backend's own JS-side grouping comment.
    const buckets = new Map<string, number>();
    for (const row of visitFreq) {
      const key = row.visit_count >= 10 ? '10+' : String(row.visit_count);
      buckets.set(key, (buckets.get(key) ?? 0) + row.client_count);
    }
    const labels = [...Array.from({ length: 9 }, (_, i) => String(i + 1)), '10+'].filter((k) => buckets.has(k));
    return {
      type: 'bar',
      data: { labels: labels.map((l) => `${l} wizyt`), datasets: [{ data: labels.map((l) => buckets.get(l) ?? 0), backgroundColor: CHART_COLORS.purpleFill, borderColor: CHART_COLORS.purple, borderWidth: 1, borderRadius: 2 }] },
      options: { ...CHART_BASE_OPTIONS, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y} klientów` } } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
    };
  }, [visitFreq]);

  if (clientsState.loading) return <p className="analytics-loading">Ładowanie…</p>;

  return (
    <div>
      <div className="analytics-chart-grid analytics-chart-grid-2 mb-6" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
        <div className="refined-card">
          <h3 className="section-title">Nowi vs. powracający klienci</h3>
          {metrics && (metrics.new_clients > 0 || metrics.returning_clients > 0) ? (
            <div className="analytics-chart-box">
              <canvas ref={splitChartRef} role="img" aria-label="Wykres podziału na nowych i powracających klientów" />
            </div>
          ) : (
            <p className="analytics-empty">Brak danych w wybranym okresie</p>
          )}
          <div className="abiz-mini-stat-row">
            <div className="abiz-mini-stat">
              <div className="abiz-mini-stat-label">Wskaźnik retencji (90 dni)</div>
              <div className="abiz-mini-stat-value">{metrics?.retention_rate != null ? `${Number(metrics.retention_rate).toFixed(1)}%` : '—'}</div>
            </div>
          </div>
        </div>

        <div className="refined-card">
          <h3 className="section-title">Top 10 klientów</h3>
          <p className="analytics-chart-label" style={{ marginBottom: '0.5rem' }}>Ranking wg wyniku: wizyty × przychód</p>
          {topClients.length === 0 ? (
            <p className="analytics-empty">Brak danych</p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {topClients.map((c, i) => (
                  <tr key={i} className="border-b border-[var(--color-border-subtle)]">
                    <td className="py-1.5 text-[var(--color-ink-subtle)] text-xs">{i + 1}</td>
                    <td className="py-1.5 font-medium">{c.client_name}</td>
                    <td className="py-1.5 text-right text-[var(--color-ink-muted)]">{c.visits}</td>
                    <td className="py-1.5 text-right text-[var(--color-ink-muted)]">{formatPLN(c.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="refined-card">
          <h3 className="section-title">Klienci zagrożeni utratą</h3>
          {!metrics || metrics.at_risk_clients.length === 0 ? (
            <p className="analytics-empty">Brak klientów zagrożonych utratą</p>
          ) : (
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {metrics.at_risk_clients.map((c) => (
                <div key={c.id} className="flex justify-between items-center p-2 border-b border-[var(--color-border-subtle)]">
                  <div>
                    <Link to={`/klienci/${c.id}`} className="abiz-employee-link font-medium">
                      {c.client_name}
                    </Link>
                    <div className="text-sm text-[var(--color-ink-subtle)]">Ostatnia wizyta: {formatDate(c.last_visit_date)}</div>
                  </div>
                  <div className="text-sm" style={{ color: 'var(--color-error)' }}>{Math.floor(c.days_since_visit)} dni</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="analytics-chart-grid analytics-chart-grid-2">
        <div>
          <div className="analytics-chart-label">Nowi klienci / miesiąc (12 mies.)</div>
          {newClientsMonths.length === 0 ? <p className="analytics-empty">Brak danych</p> : (
            <div className="analytics-chart-box">
              <canvas ref={newClientsChartRef} role="img" aria-label="Wykres nowych klientów na miesiąc" />
            </div>
          )}
        </div>
        <div>
          <div className="analytics-chart-label">Częstotliwość wizyt klientów (12 mies.)</div>
          {visitFreq.length === 0 ? <p className="analytics-empty">Brak danych</p> : (
            <div className="analytics-chart-box">
              <canvas ref={visitFreqChartRef} role="img" aria-label="Histogram częstotliwości wizyt klientów" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
