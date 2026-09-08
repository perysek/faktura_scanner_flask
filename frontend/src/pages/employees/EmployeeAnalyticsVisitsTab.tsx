import { useApiData } from '../../lib/useApiData';
import { employeeAnalyticsApi } from '../../lib/api/employeeAnalytics';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import type { EmployeePeakHourCell } from '../../types/employeeAnalytics';

const DOUGHNUT_PALETTE = [CHART_COLORS.blue, CHART_COLORS.green, CHART_COLORS.purple, CHART_COLORS.amber, CHART_COLORS.teal, CHART_COLORS.red, CHART_COLORS.orange, CHART_COLORS.emerald];

const DAY_NAMES = ['Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb', 'Nd'];
const WORK_HOURS = Array.from({ length: 14 }, (_, i) => i + 7); // 7–20

/** "Wizyty" tab — ported from analytics.js's `loadWizyty()`: appointment
 * volume, new-vs-returning client split, top-8 services mix, and a
 * day×hour peak-hours heatmap. The heatmap is a plain HTML table (not a
 * canvas) in the original too — a Chart.js matrix chart would need an extra
 * plugin for 7×14 discrete cells with numeric labels, and gains nothing a
 * styled `<table>` doesn't already give for free (native accessibility,
 * `title` tooltips, no canvas hit-testing). */
export function EmployeeAnalyticsVisitsTab({ employeeId }: { employeeId: number }) {
  const trendState = useApiData(() => employeeAnalyticsApi.revenueTrend(employeeId), [employeeId]);
  const splitState = useApiData(() => employeeAnalyticsApi.clientSplit(employeeId), [employeeId]);
  const mixState = useApiData(() => employeeAnalyticsApi.servicesMix(employeeId), [employeeId]);
  const peakState = useApiData(() => employeeAnalyticsApi.peakHours(employeeId), [employeeId]);

  const trend = trendState.data ?? [];
  const split = splitState.data ?? [];
  const mix = (mixState.data ?? []).slice(0, 8);
  const peak = peakState.data ?? [];
  const loading = trendState.loading || splitState.loading || mixState.loading || peakState.loading;
  const error = trendState.error || splitState.error || mixState.error || peakState.error;

  const appointmentsChartRef = useChartCanvas(() => {
    if (trend.length === 0) return null;
    return {
      type: 'line',
      data: {
        labels: trend.map((t) => t.month_label),
        datasets: [
          {
            label: 'Wizyty',
            data: trend.map((t) => t.appointments),
            borderColor: CHART_COLORS.green,
            backgroundColor: CHART_COLORS.greenFill,
            fill: true,
            tension: 0.3,
            pointRadius: 3,
          },
        ],
      },
      options: { ...CHART_BASE_OPTIONS, scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } } } },
    };
  }, [trend]);

  const clientSplitChartRef = useChartCanvas(() => {
    if (split.length === 0) return null;
    return {
      type: 'bar',
      data: {
        labels: split.map((r) => r.month_label),
        datasets: [
          { label: 'Nowi klienci', data: split.map((r) => r.new_clients), backgroundColor: CHART_COLORS.tealFill, borderColor: CHART_COLORS.teal, borderWidth: 1 },
          { label: 'Powracający', data: split.map((r) => r.returning_clients), backgroundColor: CHART_COLORS.greenFill, borderColor: CHART_COLORS.green, borderWidth: 1 },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: { legend: { display: true, position: 'top', align: 'end', labels: { boxWidth: 12, font: { size: 11 } } } },
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' } } },
      },
    };
  }, [split]);

  const servicesMixChartRef = useChartCanvas(() => {
    if (mix.length === 0) return null;
    return {
      type: 'doughnut',
      data: {
        labels: mix.map((s) => s.service_name),
        datasets: [{ data: mix.map((s) => s.appointment_count), backgroundColor: DOUGHNUT_PALETTE, borderWidth: 1, borderColor: 'white' }],
      },
      options: { ...CHART_BASE_OPTIONS, plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } },
    };
  }, [mix]);

  if (loading) return <p className="analytics-loading">Ładowanie…</p>;
  if (error) return <p className="analytics-error">Błąd: {error.message}</p>;

  return (
    <>
      <div className="analytics-chart-grid analytics-chart-grid-2" style={{ marginBottom: '1.25rem' }}>
        <div>
          <div className="analytics-chart-label">Liczba wizyt</div>
          <div className="analytics-chart-box">
            <canvas ref={appointmentsChartRef} role="img" aria-label="Wykres liczby wizyt z ostatnich 12 miesięcy" />
          </div>
        </div>
        <div>
          <div className="analytics-chart-label">Nowi vs powracający klienci</div>
          <div className="analytics-chart-box">
            <canvas ref={clientSplitChartRef} role="img" aria-label="Wykres podziału na nowych i powracających klientów" />
          </div>
        </div>
      </div>
      <div className="analytics-chart-grid analytics-services-peak-grid">
        <div style={{ minWidth: 0 }}>
          <div className="analytics-chart-label">Mix usług (top 8)</div>
          {mix.length > 0 ? (
            <div className="analytics-chart-box">
              <canvas ref={servicesMixChartRef} role="img" aria-label="Wykres mixu usług" />
            </div>
          ) : (
            <p className="analytics-empty">Brak danych o usługach</p>
          )}
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="analytics-chart-label">Godziny szczytowe</div>
          <PeakHoursHeatmap data={peak} />
        </div>
      </div>
    </>
  );
}

function PeakHoursHeatmap({ data }: { data: EmployeePeakHourCell[] }) {
  const matrix = new Map<string, number>();
  let maxCount = 0;
  for (const r of data) {
    matrix.set(`${r.day_of_week}-${r.hour_of_day}`, r.appointment_count);
    if (r.appointment_count > maxCount) maxCount = r.appointment_count;
  }

  if (maxCount === 0) {
    return <p className="analytics-empty">Brak danych o godzinach szczytowych</p>;
  }

  return (
    <div className="peak-hours-heatmap-scroll">
      <table className="peak-hours-heatmap">
        <thead>
          <tr>
            <th />
            {WORK_HOURS.map((h) => (
              <th key={h}>{h}:00</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DAY_NAMES.map((dayName, i) => {
            const day = i + 1;
            return (
              <tr key={day}>
                <td className="peak-hours-day-label">{dayName}</td>
                {WORK_HOURS.map((hour) => {
                  const count = matrix.get(`${day}-${hour}`) ?? 0;
                  const opacity = count > 0 ? 0.15 + (count / maxCount) * 0.75 : 0;
                  const title = count > 0 ? `${dayName} ${hour}:00 — ${count} wizyt` : undefined;
                  return (
                    <td key={hour} title={title} style={{ background: `rgba(37,99,235,${opacity})`, color: count > 0 ? (opacity > 0.5 ? 'white' : 'var(--color-ink)') : 'transparent' }}>
                      {count > 0 ? count : ''}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
