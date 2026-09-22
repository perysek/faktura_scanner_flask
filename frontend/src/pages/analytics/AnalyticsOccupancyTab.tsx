import { useApiData } from '../../lib/useApiData';
import { analyticsDashboardApi } from '../../lib/api/analyticsDashboard';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import { formatPLN } from '../../lib/format';
import type { PeakHourCell, PeriodParams } from '../../types/analyticsDashboard';

const DAY_LABELS = ['Nd', 'Pn', 'Wt', 'Śr', 'Cz', 'Pt', 'Sb']; // 0=Nd..6=Sb, matches EXTRACT(DOW)
const DISPLAY_DAYS = [1, 2, 3, 4, 5, 6]; // Mon–Sat, same as the legacy dashboard
const HOURS = Array.from({ length: 13 }, (_, i) => i + 8); // 8..20

function occupancyStatColor(rate: number, threshold: number) {
  return rate > threshold ? 'var(--color-error)' : 'var(--color-ink)';
}

/** "Obłożenie" tab — occupancy/cancellation/no-show KPI badges, the peak-hours
 * heatmap (re-rendered as JSX instead of the legacy's innerHTML string-build,
 * same hour-rows × day-columns layout and Postgres DOW convention), a new
 * "busiest vs. quietest day" mini-card derived client-side from the same
 * peak-hours payload (no new backend), and the cancellation/no-show rolling
 * trend that used to live disconnected at the bottom of the page. */
export function AnalyticsOccupancyTab({ period }: { period: PeriodParams }) {
  const deps = [period.period, period.startDate, period.endDate];
  const occupancyState = useApiData(() => analyticsDashboardApi.occupancy(period), deps);
  const peakHoursState = useApiData(() => analyticsDashboardApi.peakHours(period), deps);
  const cancellationState = useApiData(() => analyticsDashboardApi.rollingCancellationRate(), []);

  const occupancy = occupancyState.data;
  const peakHours = peakHoursState.data?.data ?? [];
  const cancellationMonths = cancellationState.data?.months ?? [];

  const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
  const monthLabel = (monthStart: string) => {
    const [y, mo] = monthStart.split('-').map(Number);
    return `${PL_MONTHS[mo - 1]} ${y}`;
  };

  const cancellationChartRef = useChartCanvas(() => {
    if (cancellationMonths.length === 0) return null;
    return {
      type: 'line',
      data: {
        labels: cancellationMonths.map((m) => monthLabel(m.month_start)),
        datasets: [
          { label: 'Odwołania', data: cancellationMonths.map((m) => m.cancellation_pct), borderColor: CHART_COLORS.amber, backgroundColor: CHART_COLORS.amberFill, borderWidth: 2, pointRadius: 4, fill: false, tension: 0.3 },
          { label: 'Nieobecności', data: cancellationMonths.map((m) => m.noshow_pct), borderColor: CHART_COLORS.red, backgroundColor: CHART_COLORS.redFill, borderWidth: 2, pointRadius: 4, fill: false, tension: 0.3 },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        interaction: { mode: 'index' as const, intersect: false },
        plugins: { legend: { display: true, position: 'bottom' as const }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${(ctx.parsed.y as number).toFixed(1)}%` } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${v}%` } } },
      },
    };
  }, [cancellationMonths]);

  // Busiest / quietest day (by revenue) — new card, derived client-side from
  // the same peak-hours payload the heatmap already fetches.
  const dayRevenue = new Map<number, number>();
  for (const cell of peakHours) {
    dayRevenue.set(cell.day_of_week, (dayRevenue.get(cell.day_of_week) ?? 0) + cell.revenue);
  }
  let busiestDay: number | null = null;
  let quietestDay: number | null = null;
  for (const [day, rev] of dayRevenue) {
    if (busiestDay === null || rev > (dayRevenue.get(busiestDay) ?? 0)) busiestDay = day;
    if (quietestDay === null || rev < (dayRevenue.get(quietestDay) ?? 0)) quietestDay = day;
  }

  if (occupancyState.loading) return <p className="analytics-loading">Ładowanie…</p>;

  return (
    <div>
      {occupancy && (
        <div className="refined-card mb-6" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="analytics-kpi-grid analytics-kpi-grid-3" style={{ gap: 0 }}>
            <div style={{ padding: '1.25rem', borderTop: '4px solid var(--color-info)' }}>
              <div className="analytics-kpi-label">Obłożenie salonu</div>
              <div className="analytics-kpi-value" style={{ color: 'var(--color-info)' }}>{occupancy.occupancy_rate.toFixed(1)}%</div>
              <div className="analytics-kpi-sub">{occupancy.booked_hours.toFixed(0)} godz. z {occupancy.theoretical_capacity.toFixed(0)} dostępnych</div>
            </div>
            <div style={{ padding: '1.25rem', borderTop: '4px solid var(--color-warning)' }}>
              <div className="analytics-kpi-label">Wskaźnik odwołań</div>
              <div className="analytics-kpi-value" style={{ color: occupancyStatColor(occupancy.cancellation_rate, 15) }}>{occupancy.cancellation_rate.toFixed(1)}%</div>
              <div className="analytics-kpi-sub">{occupancy.cancelled} odwołań</div>
            </div>
            <div style={{ padding: '1.25rem', borderTop: '4px solid var(--color-error)' }}>
              <div className="analytics-kpi-label">Nieobecności (no-show)</div>
              <div className="analytics-kpi-value" style={{ color: occupancyStatColor(occupancy.no_show_rate, 10) }}>{occupancy.no_show_rate.toFixed(1)}%</div>
              <div className="analytics-kpi-sub">{occupancy.no_shows} nieobecności</div>
            </div>
          </div>
        </div>
      )}

      <div className="refined-card mb-6">
        <h3 className="section-title">Szczyty rezerwacji</h3>
        <PeakHoursHeatmap data={peakHours} />
        {busiestDay !== null && quietestDay !== null && (
          <div className="abiz-mini-stat-row">
            <div className="abiz-mini-stat">
              <div className="abiz-mini-stat-label">Najbardziej dochodowy dzień</div>
              <div className="abiz-mini-stat-value">{DAY_LABELS[busiestDay]} · {formatPLN(dayRevenue.get(busiestDay) ?? 0)}</div>
            </div>
            <div className="abiz-mini-stat">
              <div className="abiz-mini-stat-label">Najmniej dochodowy dzień</div>
              <div className="abiz-mini-stat-value">{DAY_LABELS[quietestDay]} · {formatPLN(dayRevenue.get(quietestDay) ?? 0)}</div>
            </div>
          </div>
        )}
      </div>

      <div className="refined-card">
        <div className="analytics-chart-label">Wskaźnik odwołań i nieobecności (12 mies.)</div>
        {cancellationMonths.length === 0 ? (
          <p className="analytics-empty">Brak danych</p>
        ) : (
          <div className="analytics-chart-box">
            <canvas ref={cancellationChartRef} role="img" aria-label="Wykres wskaźnika odwołań i nieobecności" />
          </div>
        )}
      </div>
    </div>
  );
}

function PeakHoursHeatmap({ data }: { data: PeakHourCell[] }) {
  const grid = new Map<string, number>();
  let maxCount = 0;
  for (const row of data) {
    const key = `${row.day_of_week}-${row.hour_of_day}`;
    const total = (grid.get(key) ?? 0) + row.appointment_count;
    grid.set(key, total);
    if (total > maxCount) maxCount = total;
  }

  if (maxCount === 0) {
    return <p className="analytics-empty">Brak danych</p>;
  }

  return (
    <div className="peak-hours-heatmap-scroll">
      <table className="peak-hours-heatmap">
        <thead>
          <tr>
            <th style={{ textAlign: 'right' }}>Godz.</th>
            {DISPLAY_DAYS.map((d) => (
              <th key={d}>{DAY_LABELS[d]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {HOURS.map((hour) => (
            <tr key={hour}>
              <td style={{ textAlign: 'right', color: 'var(--color-ink-subtle)', whiteSpace: 'nowrap' }}>{hour}:00</td>
              {DISPLAY_DAYS.map((day) => {
                const count = grid.get(`${day}-${hour}`) ?? 0;
                const opacity = count > 0 ? Math.max(0.12, count / maxCount) : 0;
                const title = count > 0 ? `${DAY_LABELS[day]} ${hour}:00 — ${count} wizyt` : undefined;
                return (
                  <td key={day} title={title} style={{ background: `rgba(37,99,235,${opacity})`, borderRadius: 5 }}>
                    {count > 0 ? <span style={{ color: 'var(--color-status-scheduled)', fontWeight: 500 }}>{count}</span> : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: 8, fontSize: 11, color: 'var(--color-ink-subtle)', textAlign: 'right' }}>Ciemniejszy odcień = więcej rezerwacji w tym przedziale</p>
    </div>
  );
}
