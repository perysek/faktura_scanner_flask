import { useApiData } from '../../lib/useApiData';
import { analyticsDashboardApi } from '../../lib/api/analyticsDashboard';
import { CHART_BASE_OPTIONS, useChartCanvas } from '../../lib/useChartCanvas';
import { formatPLN, formatDate } from '../../lib/format';
import type { PeriodParams } from '../../types/analyticsDashboard';

// Fixed order (dataviz skill's CVD-adjacency check) — same 5-color categorical
// set as the legacy dashboard.js, ported 1:1 rather than re-picked.
const CATEGORY_PALETTE = ['#2d6a4f', '#ec4899', '#f59e0b', '#2563eb', '#14b8a6'];
const OTHER_COLOR = '#94a3b8';

function discountColor(pct: number) {
  if (pct > 10) return 'var(--color-error)';
  if (pct > 0) return 'var(--color-warning)';
  return 'var(--color-success)';
}

/** "Ceny usług" tab — service price discipline table (unchanged from the
 * legacy version) plus the category-mix rolling chart, moved here from the
 * legacy's disconnected "Trendy roczne" tail since it's a pricing/services
 * question, not a period-scoped KPI. */
export function AnalyticsServicesTab({ period }: { period: PeriodParams }) {
  const analysisState = useApiData(() => analyticsDashboardApi.serviceAnalysis(period), [period.period, period.startDate, period.endDate]);
  const categoryMixState = useApiData(() => analyticsDashboardApi.rollingCategoryMix(), []);

  const services = (analysisState.data?.services ?? []).filter((s) => s.total_revenue > 0);
  const rows = categoryMixState.data?.rows ?? [];

  const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];

  const categoryMixChartRef = useChartCanvas(() => {
    if (rows.length === 0) return null;
    const today = new Date();
    const months: string[] = [];
    for (let i = 12; i >= 1; i--) {
      const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
      months.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`);
    }
    const labels = months.map((key) => {
      const [y, mo] = key.split('-').map(Number);
      return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    const totals = new Map<string, number>();
    rows.forEach((r) => totals.set(r.category, (totals.get(r.category) ?? 0) + Number(r.revenue)));
    const ranked = [...totals.keys()].sort((a, b) => (totals.get(b) ?? 0) - (totals.get(a) ?? 0));
    const TOP_N = 5;
    const topCategories = ranked.slice(0, TOP_N);
    const hasOther = ranked.length > TOP_N;

    const byMonthCategory = new Map<string, Map<string, number>>();
    rows.forEach((r) => {
      if (!byMonthCategory.has(r.month_start)) byMonthCategory.set(r.month_start, new Map());
      byMonthCategory.get(r.month_start)!.set(r.category, Number(r.revenue));
    });

    const datasets = topCategories.map((cat, i) => ({
      label: cat,
      data: months.map((m) => byMonthCategory.get(m)?.get(cat) ?? 0),
      backgroundColor: CATEGORY_PALETTE[i % CATEGORY_PALETTE.length],
      borderRadius: 2,
    }));

    if (hasOther) {
      datasets.push({
        label: 'Inne',
        data: months.map((m) => {
          const monthData = byMonthCategory.get(m);
          if (!monthData) return 0;
          let sum = 0;
          for (const [cat, rev] of monthData) if (!topCategories.includes(cat)) sum += rev;
          return sum;
        }),
        backgroundColor: OTHER_COLOR,
        borderRadius: 2,
      });
    }

    return {
      type: 'bar',
      data: { labels, datasets },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: { legend: { display: true, position: 'bottom' as const }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatPLN(ctx.parsed.y as number)}` } } },
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { callback: (v) => `${Number(v).toLocaleString('pl-PL')} zł` } } },
      },
    };
  }, [rows]);

  if (analysisState.loading) return <p className="analytics-loading">Ładowanie…</p>;

  return (
    <div>
      <div className="refined-card mb-6">
        <h3 className="section-title">Analiza cen usług</h3>
        <p className="analytics-chart-label" style={{ marginBottom: '0.75rem' }}>Porównanie cen katalogowych z faktycznie pobranymi</p>
        {services.length === 0 ? (
          <p className="analytics-empty">Brak danych</p>
        ) : (
          <div className="table-container stack-cards-wrap">
            <table className="refined-table stack-cards">
              <thead>
                <tr>
                  <th>Usługa</th>
                  <th>Kategoria</th>
                  <th className="text-right">Cena katalogowa</th>
                  <th className="text-right">Ost. zmiana ceny</th>
                  <th className="text-right">Trend w okresie</th>
                  <th className="text-right">Śr. pobrana</th>
                  <th className="text-right">Rabat śr.</th>
                  <th className="text-right">Wizyty</th>
                  <th className="text-right">Przychód</th>
                </tr>
              </thead>
              <tbody>
                {services.map((s, i) => {
                  const hasBookings = s.bookings > 0;
                  const discount = s.avg_discount_pct || 0;
                  const startPrice = s.price_at_period_start;
                  let trendIcon = '—';
                  let trendColor = 'var(--color-ink-subtle)';
                  if (startPrice != null) {
                    if (s.catalogue_price > startPrice) { trendIcon = '↑'; trendColor = 'var(--color-error)'; }
                    else if (s.catalogue_price < startPrice) { trendIcon = '↓'; trendColor = 'var(--color-success)'; }
                    else { trendIcon = '='; trendColor = 'var(--color-ink-subtle)'; }
                  }
                  return (
                    <tr key={i} style={!hasBookings ? { color: 'var(--color-ink-subtle)' } : undefined}>
                      <td data-label="Usługa" className={hasBookings ? 'font-medium' : 'italic'}>{s.service_name}</td>
                      <td data-label="Kategoria"><span className="text-xs">{s.category ?? ''}</span></td>
                      <td data-label="Cena katalogowa" className="text-right">{formatPLN(s.catalogue_price)}</td>
                      <td data-label="Ost. zmiana ceny" className="text-right text-xs">{s.last_price_change ? formatDate(s.last_price_change) : '—'}</td>
                      <td data-label="Trend w okresie" className="text-right font-medium" style={{ color: trendColor }}>{trendIcon}</td>
                      <td data-label="Śr. pobrana" className="text-right">{hasBookings ? formatPLN(s.avg_charged) : '—'}</td>
                      <td data-label="Rabat śr." className="text-right font-medium" style={{ color: hasBookings ? discountColor(discount) : undefined }}>
                        {hasBookings ? `${discount.toFixed(1)}%` : '—'}
                      </td>
                      <td data-label="Wizyty" className="text-right">{s.bookings}</td>
                      <td data-label="Przychód" className="text-right">{hasBookings ? formatPLN(s.total_revenue) : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="refined-card">
        <div className="analytics-chart-label">Struktura przychodu wg kategorii usług (12 mies.)</div>
        {rows.length === 0 ? (
          <p className="analytics-empty">Brak danych</p>
        ) : (
          <div className="analytics-chart-box">
            <canvas ref={categoryMixChartRef} role="img" aria-label="Wykres struktury przychodu wg kategorii usług" />
          </div>
        )}
      </div>
    </div>
  );
}
