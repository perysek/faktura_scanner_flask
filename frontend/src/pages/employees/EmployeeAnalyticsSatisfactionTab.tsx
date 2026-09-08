import { useApiData } from '../../lib/useApiData';
import { employeeAnalyticsApi } from '../../lib/api/employeeAnalytics';
import { CHART_BASE_OPTIONS, useChartCanvas } from '../../lib/useChartCanvas';

/** "Satysfakcja" tab — ported from analytics.js's `loadSatysfakcja()`: KPI
 * row (avg score, rated-visit count, star-distribution bars), a per-category
 * breakdown table, and a 12-month average-rating trend line. */
export function EmployeeAnalyticsSatisfactionTab({ employeeId }: { employeeId: number }) {
  const state = useApiData(() => employeeAnalyticsApi.satisfaction(employeeId), [employeeId]);
  const d = state.data;

  const trendRef = useChartCanvas(() => {
    if (!d || d.monthly_trend.length === 0) return null;
    return {
      type: 'line',
      data: {
        labels: d.monthly_trend.map((r) => r.month_label),
        datasets: [
          {
            label: 'Śr. ocena',
            data: d.monthly_trend.map((r) => r.avg_score),
            borderColor: '#f59e0b',
            backgroundColor: 'rgba(245,158,11,0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            spanGaps: true,
          },
        ],
      },
      options: { ...CHART_BASE_OPTIONS, scales: { y: { min: 0, max: 5, ticks: { stepSize: 1 }, grid: { color: 'rgba(0,0,0,0.04)' } } } },
    };
  }, [d]);

  if (state.loading) return <p className="analytics-loading">Ładowanie…</p>;
  if (state.error) return <p className="analytics-error">Błąd: {state.error.message}</p>;
  if (!d) return null;

  return (
    <div>
      <div className="analytics-kpi-grid analytics-kpi-grid-3" style={{ marginBottom: '1.5rem' }}>
        <div className="analytics-kpi-card" style={{ background: 'rgba(245,158,11,0.05)', borderColor: 'rgba(245,158,11,0.2)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-status-in-progress)' }}>
            Śr. ocena
          </div>
          <div className="analytics-kpi-value" style={{ fontSize: '1.5rem' }}>
            {d.avg_score ? `${d.avg_score} ★` : '—'}
          </div>
          <div className="analytics-kpi-sub">na 5 gwiazdek</div>
        </div>
        <div className="analytics-kpi-card" style={{ background: 'rgba(37,99,235,0.05)', borderColor: 'rgba(37,99,235,0.15)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-status-scheduled)' }}>
            Ocenionych wizyt
          </div>
          <div className="analytics-kpi-value" style={{ fontSize: '1.5rem' }}>
            {d.total_scored}
          </div>
          <div className="analytics-kpi-sub">z oceną klienta</div>
        </div>
        <div className="analytics-kpi-card" style={{ background: 'rgba(45,106,79,0.05)', borderColor: 'rgba(45,106,79,0.15)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-success)' }}>
            Rozkład ocen
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-ink)', lineHeight: 1.6, marginTop: '0.375rem' }}>
            {[5, 4, 3, 2, 1].map((n) => {
              const count = d.distribution[String(n)] ?? 0;
              const pct = d.total_scored > 0 ? Math.round((count / d.total_scored) * 100) : 0;
              return (
                <div key={n} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                  <span style={{ width: '2.5rem', fontSize: '0.6875rem', color: 'var(--color-ink-subtle)' }}>{'★'.repeat(n)}</span>
                  <div style={{ flex: 1, background: 'var(--color-border-subtle)', borderRadius: 2, height: 6, overflow: 'hidden' }}>
                    <div style={{ background: 'rgba(245,158,11,0.7)', width: `${pct}%`, height: '100%', borderRadius: 2 }} />
                  </div>
                  <span style={{ width: '1.5rem', textAlign: 'right', fontSize: '0.6875rem', color: 'var(--color-ink-subtle)' }}>{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <div className="analytics-chart-label">Ocena wg kategorii usług</div>
        {d.by_service_category.length === 0 ? (
          <p className="analytics-empty">Brak danych</p>
        ) : (
          <div className="table-container">
            <table className="refined-table stack-cards">
              <thead>
                <tr>
                  <th>Kategoria</th>
                  <th>Śr. ocena</th>
                  <th>Wizyt</th>
                </tr>
              </thead>
              <tbody>
                {d.by_service_category.map((r) => {
                  const stars = r.avg_score ? Math.round(r.avg_score) : 0;
                  return (
                    <tr key={r.category}>
                      <td className="cell-name" data-label="Kategoria">
                        {r.category}
                      </td>
                      <td data-label="Śr. ocena" style={{ color: 'var(--color-status-in-progress)' }}>
                        {'★'.repeat(stars)}
                        {'☆'.repeat(5 - stars)} <span style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>({r.avg_score ?? '—'})</span>
                      </td>
                      <td data-label="Wizyt" style={{ color: 'var(--color-ink-subtle)' }}>
                        {r.count}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <div className="analytics-chart-label">Trend ocen (12 miesięcy)</div>
        {d.monthly_trend.length > 0 ? (
          <div className="analytics-chart-box" style={{ height: 220 }}>
            <canvas ref={trendRef} role="img" aria-label="Wykres trendu ocen satysfakcji z ostatnich 12 miesięcy" />
          </div>
        ) : (
          <p className="analytics-empty">Brak danych</p>
        )}
      </div>
    </div>
  );
}
