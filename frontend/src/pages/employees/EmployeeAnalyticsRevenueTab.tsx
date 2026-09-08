import { useApiData } from '../../lib/useApiData';
import { employeeAnalyticsApi } from '../../lib/api/employeeAnalytics';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import { formatPLN } from '../../lib/format';

/** "Przychody" tab — ported from analytics.js's `loadPrzychody()`: a
 * revenue+commission trend line and a base-salary-vs-commission stacked bar,
 * both over the same 12-month window. */
export function EmployeeAnalyticsRevenueTab({ employeeId }: { employeeId: number }) {
  const trendState = useApiData(() => employeeAnalyticsApi.revenueTrend(employeeId), [employeeId]);
  const commissionState = useApiData(() => employeeAnalyticsApi.commissionTrend(employeeId), [employeeId]);

  const trend = trendState.data ?? [];
  const commission = commissionState.data ?? [];
  const loading = trendState.loading || commissionState.loading;
  const error = trendState.error || commissionState.error;

  const revenueChartRef = useChartCanvas(() => {
    if (trend.length === 0) return null;
    return {
      type: 'line',
      data: {
        labels: trend.map((t) => t.month_label),
        datasets: [
          {
            label: 'Przychód',
            data: trend.map((t) => t.revenue),
            borderColor: CHART_COLORS.blue,
            backgroundColor: CHART_COLORS.blueFill,
            fill: true,
            tension: 0.3,
            pointRadius: 3,
          },
          {
            label: 'Prowizja',
            data: trend.map((t) => t.commission),
            borderColor: CHART_COLORS.purple,
            backgroundColor: CHART_COLORS.purpleFill,
            fill: true,
            tension: 0.3,
            pointRadius: 3,
          },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: {
          legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: (ctx) => ` ${formatPLN(ctx.raw as number)}` } },
        },
        scales: {
          y: { ticks: { callback: (v) => formatPLN(Number(v)) }, grid: { color: 'rgba(0,0,0,0.04)' } },
        },
      },
    };
  }, [trend]);

  const commissionChartRef = useChartCanvas(() => {
    if (commission.length === 0) return null;
    return {
      type: 'bar',
      data: {
        labels: commission.map((r) => r.month_label),
        datasets: [
          {
            label: 'Wynagrodzenie bazowe',
            data: commission.map((r) => r.base_salary),
            backgroundColor: CHART_COLORS.blueFill,
            borderColor: CHART_COLORS.blue,
            borderWidth: 1,
          },
          {
            label: 'Prowizja',
            data: commission.map((r) => r.commission_earned),
            backgroundColor: CHART_COLORS.purpleFill,
            borderColor: CHART_COLORS.purple,
            borderWidth: 1,
          },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: {
          legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { label: (ctx) => ` ${formatPLN(ctx.raw as number)}` } },
        },
        scales: {
          x: { stacked: true },
          y: { stacked: true, ticks: { callback: (v) => formatPLN(Number(v)) }, grid: { color: 'rgba(0,0,0,0.04)' } },
        },
      },
    };
  }, [commission]);

  if (loading) return <p className="analytics-loading">Ładowanie…</p>;
  if (error) return <p className="analytics-error">Błąd: {error.message}</p>;

  return (
    <div className="analytics-chart-grid">
      <div>
        <div className="analytics-chart-label">Przychód i prowizja (12 miesięcy)</div>
        <div className="analytics-chart-box">
          <canvas ref={revenueChartRef} role="img" aria-label="Wykres przychodu i prowizji z ostatnich 12 miesięcy" />
        </div>
      </div>
      <div>
        <div className="analytics-chart-label">Wynagrodzenie bazowe vs prowizja</div>
        <div className="analytics-chart-box">
          <canvas ref={commissionChartRef} role="img" aria-label="Wykres wynagrodzenia bazowego i prowizji z ostatnich 12 miesięcy" />
        </div>
      </div>
    </div>
  );
}
