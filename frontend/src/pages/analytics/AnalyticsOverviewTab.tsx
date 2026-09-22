import { useApiData } from '../../lib/useApiData';
import { analyticsDashboardApi } from '../../lib/api/analyticsDashboard';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import { formatPLN, formatNextVisitLine1 } from '../../lib/format';
import { Icon } from '../../lib/icons/Icon';
import type { PeriodParams } from '../../types/analyticsDashboard';

const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
function monthLabel(monthStart: string) {
  const [y, mo] = monthStart.split('-').map(Number);
  return `${PL_MONTHS[mo - 1]} ${y}`;
}

function ChangeBadge({ pct }: { pct: number | null | undefined }) {
  if (pct === null || pct === undefined) return null;
  const positive = pct >= 0;
  return (
    <div className="text-sm font-medium" style={{ color: positive ? 'var(--color-success)' : 'var(--color-error)' }}>
      {positive ? '+' : ''}
      {pct.toFixed(1)}% {positive ? '↑' : '↓'} vs poprzedni okres
    </div>
  );
}

const INSIGHT_STYLE: Record<string, { icon: string; color: string; bg: string; border: string }> = {
  alert: { icon: 'error', color: 'var(--color-error)', bg: 'rgba(155,44,44,0.08)', border: 'rgba(155,44,44,0.2)' },
  warning: { icon: 'warning', color: 'var(--color-warning)', bg: 'rgba(154,103,0,0.08)', border: 'rgba(154,103,0,0.2)' },
  success: { icon: 'check_circle', color: 'var(--color-success)', bg: 'rgba(45,106,79,0.08)', border: 'rgba(45,106,79,0.2)' },
  info: { icon: 'info', color: 'var(--color-info-text)', bg: 'var(--color-info-bg)', border: 'var(--color-info-border)' },
};

export function AnalyticsOverviewTab({ period }: { period: PeriodParams }) {
  const deps = [period.period, period.startDate, period.endDate];
  const summaryState = useApiData(() => analyticsDashboardApi.summary(period), deps);
  const profitState = useApiData(() => analyticsDashboardApi.profit(period), deps);
  const revenueTrendState = useApiData(() => analyticsDashboardApi.revenueTrend(period), deps);
  const servicesState = useApiData(() => analyticsDashboardApi.services(period), deps);
  const insightsState = useApiData(() => analyticsDashboardApi.insights(period), deps);
  const monthlyTrendState = useApiData(() => analyticsDashboardApi.monthlyTrend(), []);
  const avgTicketState = useApiData(() => analyticsDashboardApi.rollingAvgTicket(), []);
  const costRatioState = useApiData(() => analyticsDashboardApi.rollingCostRatio(), []);

  const summary = summaryState.data;
  const profit = profitState.data;
  const revenueTrend = revenueTrendState.data?.data ?? [];
  const services = (servicesState.data?.services ?? []).slice(0, 5);
  const insights = insightsState.data?.insights ?? [];
  const monthlyTrend = monthlyTrendState.data?.months ?? [];
  const avgTicketRolling = avgTicketState.data?.months ?? [];
  const costRatioRolling = costRatioState.data?.months ?? [];

  const revenueTrendChartRef = useChartCanvas(() => {
    if (revenueTrend.length === 0) return null;
    return {
      type: 'line',
      data: {
        labels: revenueTrend.map((d) => formatNextVisitLine1(d.date)),
        datasets: [{ label: 'Przychód', data: revenueTrend.map((d) => d.revenue), borderColor: CHART_COLORS.blue, backgroundColor: CHART_COLORS.blueFill, fill: true, tension: 0.3 }],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => formatPLN(ctx.parsed.y as number) } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${Number(v).toLocaleString('pl-PL')} zł` } } },
      },
    };
  }, [revenueTrend]);

  const servicesChartRef = useChartCanvas(() => {
    if (services.length === 0) return null;
    return {
      type: 'bar',
      data: { labels: services.map((s) => s.service_name), datasets: [{ data: services.map((s) => s.revenue_generated), backgroundColor: CHART_COLORS.blueFill, borderColor: CHART_COLORS.blue, borderWidth: 1, borderRadius: 2 }] },
      options: {
        ...CHART_BASE_OPTIONS,
        indexAxis: 'y' as const,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => formatPLN(ctx.parsed.x as number) } } },
        scales: { x: { beginAtZero: true, ticks: { callback: (v) => `${Number(v).toLocaleString('pl-PL')} zł` } } },
      },
    };
  }, [services]);

  const profitBreakdownChartRef = useChartCanvas(() => {
    if (!profit) return null;
    const netColor = profit.net_profit >= 0 ? CHART_COLORS.green : CHART_COLORS.red;
    return {
      type: 'bar',
      data: {
        labels: [''],
        datasets: [
          { label: 'Koszty pracownicze', data: [profit.employee_costs], backgroundColor: CHART_COLORS.amberFill, borderColor: CHART_COLORS.amber, borderWidth: 1 },
          { label: 'Koszty faktur', data: [profit.invoice_costs], backgroundColor: CHART_COLORS.redFill, borderColor: CHART_COLORS.red, borderWidth: 1 },
          { label: profit.net_profit >= 0 ? 'Zysk netto' : 'Strata netto', data: [Math.abs(profit.net_profit)], backgroundColor: netColor, borderColor: netColor, borderWidth: 1 },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        indexAxis: 'y' as const,
        plugins: { legend: { display: true, position: 'bottom' as const }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatPLN(ctx.parsed.x as number)}` } } },
        scales: { x: { stacked: true, beginAtZero: true, ticks: { callback: (v) => `${Number(v).toLocaleString('pl-PL')} zł` } }, y: { stacked: true } },
      },
    };
  }, [profit]);

  const monthlyTrendChartRef = useChartCanvas(() => {
    if (monthlyTrend.length === 0) return null;
    return {
      type: 'bar' as const,
      data: {
        labels: monthlyTrend.map((m) => monthLabel(m.month_start)),
        datasets: [
          { type: 'bar' as const, label: 'Przychód', data: monthlyTrend.map((m) => m.revenue), backgroundColor: CHART_COLORS.blueFill, borderColor: CHART_COLORS.blue, borderWidth: 1, order: 2 },
          { type: 'bar' as const, label: 'Koszty pracownicze', data: monthlyTrend.map((m) => m.employee_costs), backgroundColor: CHART_COLORS.amberFill, borderColor: CHART_COLORS.amber, borderWidth: 1, order: 2 },
          { type: 'bar' as const, label: 'Koszty faktur', data: monthlyTrend.map((m) => m.invoice_costs), backgroundColor: CHART_COLORS.redFill, borderColor: CHART_COLORS.red, borderWidth: 1, order: 2 },
          {
            type: 'line' as const,
            label: 'Zysk netto',
            data: monthlyTrend.map((m) => m.profit),
            borderColor: CHART_COLORS.green,
            backgroundColor: CHART_COLORS.greenFill,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: monthlyTrend.map((m) => (m.profit >= 0 ? CHART_COLORS.green : CHART_COLORS.red)),
            fill: false,
            tension: 0.3,
            order: 1,
          },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        interaction: { mode: 'index' as const, intersect: false },
        plugins: { legend: { display: true, position: 'bottom' as const }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatPLN(ctx.parsed.y as number)}` } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${Number(v).toLocaleString('pl-PL')} zł` } } },
      },
    };
  }, [monthlyTrend]);

  const avgTicketChartRef = useChartCanvas(() => {
    if (avgTicketRolling.length === 0) return null;
    return {
      type: 'line',
      data: { labels: avgTicketRolling.map((m) => monthLabel(m.month_start)), datasets: [{ label: 'Średni rachunek', data: avgTicketRolling.map((m) => m.avg_ticket), borderColor: CHART_COLORS.blue, backgroundColor: CHART_COLORS.blueFill, borderWidth: 2, pointRadius: 4, fill: false, tension: 0.3 }] },
      options: { ...CHART_BASE_OPTIONS, plugins: { tooltip: { callbacks: { label: (ctx) => `Średni rachunek: ${formatPLN(ctx.parsed.y as number)}` } } }, scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${Number(v).toLocaleString('pl-PL')} zł` } } } },
    };
  }, [avgTicketRolling]);

  const costRatioChartRef = useChartCanvas(() => {
    if (costRatioRolling.length === 0) return null;
    return {
      type: 'line',
      data: { labels: costRatioRolling.map((m) => monthLabel(m.month_start)), datasets: [{ label: 'Udział kosztów faktur w przychodzie', data: costRatioRolling.map((m) => m.ratio_pct), borderColor: CHART_COLORS.amber, backgroundColor: CHART_COLORS.amberFill, borderWidth: 2, pointRadius: 4, fill: true, tension: 0.3 }] },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => `Udział faktur: ${ctx.parsed.y ?? 0}%`,
              afterLabel: (ctx) => {
                const m = costRatioRolling[ctx.dataIndex];
                return m ? `${formatPLN(m.invoice_costs)} z ${formatPLN(m.revenue)} przychodu` : '';
              },
            },
          },
        },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${v}%` } } },
      },
    };
  }, [costRatioRolling]);

  const loading = summaryState.loading || profitState.loading;
  if (loading) return <p className="analytics-loading">Ładowanie…</p>;

  return (
    <div>
      <div className="analytics-kpi-grid mb-6">
        <div className="analytics-kpi-card" style={{ background: 'rgba(37,99,235,0.05)', borderColor: 'rgba(37,99,235,0.15)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-status-scheduled)' }}>Przychód</div>
          <div className="analytics-kpi-value">{summary ? formatPLN(summary.current.total_revenue) : '—'}</div>
          <ChangeBadge pct={summary?.change?.revenue_pct} />
        </div>
        <div className="analytics-kpi-card" style={{ background: 'rgba(45,106,79,0.05)', borderColor: 'rgba(45,106,79,0.15)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-success)' }}>Wizyty</div>
          <div className="analytics-kpi-value">{summary ? summary.current.total_appointments.toLocaleString('pl-PL') : '—'}</div>
          <ChangeBadge pct={summary?.change?.appointments_pct} />
        </div>
        <div className="analytics-kpi-card" style={{ background: 'rgba(126,34,206,0.05)', borderColor: 'rgba(126,34,206,0.15)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-purple)' }}>Klienci</div>
          <div className="analytics-kpi-value">{summary ? summary.current.unique_clients.toLocaleString('pl-PL') : '—'}</div>
          <ChangeBadge pct={summary?.change?.clients_pct} />
        </div>
        <div className="analytics-kpi-card" style={{ background: 'rgba(245,158,11,0.05)', borderColor: 'rgba(245,158,11,0.15)' }}>
          <div className="analytics-kpi-label" style={{ color: 'var(--color-orange)' }}>Średni rachunek</div>
          <div className="analytics-kpi-value">{summary ? formatPLN(summary.current.avg_ticket) : '—'}</div>
          <ChangeBadge pct={summary?.change?.avg_ticket_pct} />
        </div>
      </div>

      {profit && (
        <div className="analytics-kpi-grid analytics-kpi-grid-3 mb-6">
          <div className="analytics-kpi-card" style={{ borderLeft: '4px solid var(--color-warning)', borderColor: 'var(--color-border-subtle)' }}>
            <div className="analytics-kpi-label">Koszty pracownicze</div>
            <div className="analytics-kpi-value">{formatPLN(profit.employee_costs)}</div>
            <div className="analytics-kpi-sub">ZUS + wynagrodzenia</div>
          </div>
          <div className="analytics-kpi-card" style={{ borderLeft: '4px solid var(--color-error)', borderColor: 'var(--color-border-subtle)' }}>
            <div className="analytics-kpi-label">Koszty faktur</div>
            <div className="analytics-kpi-value">{formatPLN(profit.invoice_costs)}</div>
            <div className="analytics-kpi-sub" style={{ color: profit.invoice_details.unpaid_count > 0 ? 'var(--color-error)' : 'var(--color-success)' }}>
              {profit.invoice_details.unpaid_count > 0 ? `${profit.invoice_details.unpaid_count} niezapłaconych: ${formatPLN(profit.invoice_details.unpaid_amount)}` : 'Wszystkie faktury opłacone'}
            </div>
          </div>
          <div className="analytics-kpi-card" style={{ borderLeft: `4px solid ${profit.net_profit >= 0 ? 'var(--color-success)' : 'var(--color-error)'}`, borderColor: 'var(--color-border-subtle)' }}>
            <div className="analytics-kpi-label">Zysk netto</div>
            <div className="analytics-kpi-value" style={{ color: profit.net_profit >= 0 ? 'var(--color-success)' : 'var(--color-error)' }}>{formatPLN(profit.net_profit)}</div>
            {profit.change ? <ChangeBadge pct={profit.change.net_profit_pct} /> : null}
            <div className="analytics-kpi-sub">marża {profit.profit_margin_pct}%</div>
          </div>
        </div>
      )}

      <div className="analytics-chart-grid analytics-chart-grid-2 mb-6">
        <div>
          <div className="analytics-chart-label">Trend przychodów</div>
          <div className="analytics-chart-box">
            <canvas ref={revenueTrendChartRef} role="img" aria-label="Wykres trendu przychodów" />
          </div>
        </div>
        <div>
          <div className="analytics-chart-label">Usługi (top 5 wg przychodu)</div>
          <div className="analytics-chart-box">
            <canvas ref={servicesChartRef} role="img" aria-label="Wykres top 5 usług" />
          </div>
        </div>
      </div>

      <div className="refined-card mb-6">
        <h3 className="section-title">Struktura zysku</h3>
        <div className="analytics-chart-box" style={{ height: 200 }}>
          <canvas ref={profitBreakdownChartRef} role="img" aria-label="Wykres struktury zysku" />
        </div>
      </div>

      <div className="refined-card mb-6">
        <h3 className="section-title">Trend 12 miesięcy — przychody / koszty / zysk</h3>
        <p className="analytics-chart-label" style={{ marginBottom: '0.75rem' }}>Ruchome okno 12 miesięcy, niezależne od wybranego okresu</p>
        <div className="analytics-chart-box" style={{ height: 320 }}>
          <canvas ref={monthlyTrendChartRef} role="img" aria-label="Wykres 12-miesięcznego trendu przychodów, kosztów i zysku" />
        </div>
      </div>

      <div className="analytics-chart-grid analytics-chart-grid-2 mb-6">
        <div>
          <div className="analytics-chart-label">Średni rachunek / miesiąc (12 mies.)</div>
          <div className="analytics-chart-box">
            <canvas ref={avgTicketChartRef} role="img" aria-label="Wykres średniego rachunku na miesiąc" />
          </div>
        </div>
        <div>
          <div className="analytics-chart-label">Udział kosztów faktur w przychodzie (12 mies.)</div>
          <div className="analytics-chart-box">
            <canvas ref={costRatioChartRef} role="img" aria-label="Wykres udziału kosztów faktur w przychodzie" />
          </div>
        </div>
      </div>

      <div className="refined-card">
        <h3 className="section-title">Wskazówki biznesowe</h3>
        {insights.length === 0 ? (
          <p className="analytics-empty">Brak danych do analizy</p>
        ) : (
          insights.map((insight, i) => {
            const style = INSIGHT_STYLE[insight.type] ?? INSIGHT_STYLE.info;
            return (
              <div key={i} className="abiz-insight-row" style={{ background: style.bg, borderColor: style.border }}>
                <span className="abiz-insight-icon" style={{ color: style.color }}>
                  <Icon name={style.icon} />
                </span>
                <div>
                  <div className="abiz-insight-title" style={{ color: style.color }}>{insight.title}</div>
                  <div className="abiz-insight-message">{insight.message}</div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
