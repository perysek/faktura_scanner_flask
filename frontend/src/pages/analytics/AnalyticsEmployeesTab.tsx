import { Link } from 'react-router-dom';
import { useApiData } from '../../lib/useApiData';
import { analyticsDashboardApi } from '../../lib/api/analyticsDashboard';
import { CHART_BASE_OPTIONS, CHART_COLORS, useChartCanvas } from '../../lib/useChartCanvas';
import { formatPLN } from '../../lib/format';
import type { PeriodParams } from '../../types/analyticsDashboard';

const PL_MONTHS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
function monthLabel(monthStart: string) {
  const [y, mo] = monthStart.split('-').map(Number);
  return `${PL_MONTHS[mo - 1]} ${y}`;
}
const LINE_PALETTE = [CHART_COLORS.blue, CHART_COLORS.green, CHART_COLORS.purple, CHART_COLORS.amber, CHART_COLORS.teal, CHART_COLORS.red, CHART_COLORS.orange, CHART_COLORS.emerald];

function satisfactionColor(score: number | null) {
  if (score === null) return 'var(--color-ink-subtle)';
  if (score >= 4.5) return 'var(--color-success)';
  if (score >= 3.5) return 'var(--color-warning)';
  return 'var(--color-error)';
}

/** "Pracownicy" tab — the performance table now links each row to
 * `/pracownicy/:id` (its own full "Analizy i wyniki" section already exists —
 * BeCreative pick over building a duplicate drill-down here), plus two rolling
 * charts (`employee-utilisation`, `satisfaction-rating`) that existed in the
 * backend but were never wired into the legacy Jinja dashboard at all. */
export function AnalyticsEmployeesTab({ period }: { period: PeriodParams }) {
  const deps = [period.period, period.startDate, period.endDate];
  const employeesState = useApiData(() => analyticsDashboardApi.employees(period), deps);
  const utilisationState = useApiData(() => analyticsDashboardApi.rollingEmployeeUtilisation(), []);
  const satisfactionState = useApiData(() => analyticsDashboardApi.rollingSatisfactionRating(), []);

  const employees = employeesState.data?.employees ?? [];
  const utilisationRows = utilisationState.data?.rows ?? [];
  const satisfactionOverall = satisfactionState.data?.overall ?? [];

  const utilisationChartRef = useChartCanvas(() => {
    if (utilisationRows.length === 0) return null;
    const months = Array.from(new Set(utilisationRows.map((r) => r.month_start))).sort();
    const names = Array.from(new Set(utilisationRows.map((r) => r.employee_name)));
    const byKey = new Map(utilisationRows.map((r) => [`${r.month_start}|${r.employee_name}`, r.utilisation_pct]));
    return {
      type: 'line',
      data: {
        labels: months.map(monthLabel),
        datasets: names.map((name, i) => ({
          label: name,
          data: months.map((m) => byKey.get(`${m}|${name}`) ?? null),
          borderColor: LINE_PALETTE[i % LINE_PALETTE.length],
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 3,
          spanGaps: true,
          tension: 0.3,
        })),
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: { legend: { display: true, position: 'bottom' as const, labels: { boxWidth: 12, font: { size: 11 } } }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y ?? '—'}%` } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => `${v}%` } } },
      },
    };
  }, [utilisationRows]);

  const satisfactionChartRef = useChartCanvas(() => {
    if (satisfactionOverall.length === 0) return null;
    return {
      type: 'line',
      data: {
        labels: satisfactionOverall.map((m) => monthLabel(m.month_start)),
        datasets: [
          {
            label: 'Śr. ocena klientów',
            data: satisfactionOverall.map((m) => (m.avg_score != null ? Number(m.avg_score) : null)),
            borderColor: CHART_COLORS.orange,
            backgroundColor: CHART_COLORS.blueFill,
            borderWidth: 2,
            pointRadius: 4,
            fill: true,
            spanGaps: true,
            tension: 0.3,
          },
        ],
      },
      options: {
        ...CHART_BASE_OPTIONS,
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const point = satisfactionOverall[ctx.dataIndex];
                return ctx.parsed.y != null ? `Śr. ocena: ${(ctx.parsed.y as number).toFixed(2)} / 5 (${point?.scored_count ?? 0} ocen)` : 'Brak ocen w tym miesiącu';
              },
            },
          },
        },
        scales: { y: { min: 1, max: 5, ticks: { stepSize: 1 } } },
      },
    };
  }, [satisfactionOverall]);

  if (employeesState.loading) return <p className="analytics-loading">Ładowanie…</p>;

  return (
    <div>
      <div className="refined-card mb-6">
        <h3 className="section-title">Wyniki pracowników</h3>
        {employees.length === 0 ? (
          <p className="analytics-empty">Brak danych</p>
        ) : (
          <div className="table-container stack-cards-wrap">
            <table className="refined-table stack-cards">
              <thead>
                <tr>
                  <th>Pracownik</th>
                  <th className="text-right">Wizyty</th>
                  <th className="text-right">Przychód</th>
                  <th className="text-right">Prowizja</th>
                  <th className="text-right">Wynagrodzenie brutto</th>
                  <th className="text-right">Koszt pracodawcy</th>
                  <th className="text-right">Zysk netto</th>
                  <th className="text-right">Satysfakcja</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((e) => (
                  <tr key={e.id}>
                    <td data-label="Pracownik" className="font-medium">
                      <Link to={`/pracownicy/${e.id}`} className="abiz-employee-link">
                        {e.employee_name}
                      </Link>
                    </td>
                    <td data-label="Wizyty" className="text-right">{e.appointments_count}</td>
                    <td data-label="Przychód" className="text-right">{formatPLN(e.revenue_generated)}</td>
                    <td data-label="Prowizja" className="text-right">{formatPLN(e.commission_earned)}</td>
                    <td data-label="Wynagrodzenie brutto" className="text-right">{formatPLN(e.gross_salary)}</td>
                    <td data-label="Koszt pracodawcy" className="text-right" title={`Stawka pracodawcy: ${(e.cost_rate * 100).toFixed(1)}%`}>
                      {formatPLN(e.total_employer_cost)}
                    </td>
                    <td data-label="Zysk netto" className="text-right font-medium" style={{ color: e.net_profit >= 0 ? 'var(--color-success)' : 'var(--color-error)' }}>
                      {formatPLN(e.net_profit)}
                    </td>
                    <td data-label="Satysfakcja" className="text-right text-sm" style={{ color: satisfactionColor(e.avg_satisfaction) }}>
                      {e.avg_satisfaction ? `${e.avg_satisfaction.toFixed(1)} ★` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="analytics-chart-grid analytics-chart-grid-2">
        <div>
          <div className="analytics-chart-label">Wykorzystanie pracowników (12 mies.)</div>
          {utilisationRows.length === 0 ? (
            <p className="analytics-empty">Brak danych</p>
          ) : (
            <div className="analytics-chart-box">
              <canvas ref={utilisationChartRef} role="img" aria-label="Wykres wykorzystania pracowników" />
            </div>
          )}
        </div>
        <div>
          <div className="analytics-chart-label">Śr. ocena satysfakcji klientów (12 mies.)</div>
          {satisfactionOverall.length === 0 ? (
            <p className="analytics-empty">Brak danych</p>
          ) : (
            <div className="analytics-chart-box">
              <canvas ref={satisfactionChartRef} role="img" aria-label="Wykres średniej oceny satysfakcji klientów" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
