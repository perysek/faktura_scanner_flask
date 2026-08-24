import { useEffect, useRef } from 'react';
import { Chart, BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
import { getKpiFormatter, kpiMetTarget } from './kpiFormat';
import type { KpiIndicator } from '../../types/kpiMatrix';

Chart.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip);

const MONTH_LABELS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];

/** Expanded-row detail chart — bar per month (colored by target-met status)
 * + a dashed target reference line. Ported 1:1 from
 * static/js/analytics/kpi_matrix.js's `renderIndicatorChart()`. */
export function KpiIndicatorChart({ indicator }: { indicator: KpiIndicator }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const values = Array.from({ length: 12 }, (_, i) => indicator.months[String(i + 1)] ?? null);
    const barColors = values.map((v) => {
      const met = kpiMetTarget(v, indicator.direction, indicator.target);
      if (met === null) return 'rgba(137,135,129,0.35)';
      return met ? 'rgba(45,106,79,0.75)' : 'rgba(155,44,44,0.7)';
    });
    const formatter = getKpiFormatter(indicator);

    chartRef.current?.destroy();
    chartRef.current = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: MONTH_LABELS,
        datasets: [
          { label: indicator.name, data: values, backgroundColor: barColors, borderRadius: 2, order: 2 },
          {
            label: 'Cel',
            type: 'line',
            data: new Array(12).fill(indicator.target),
            borderColor: '#c0392b',
            borderWidth: 2,
            borderDash: [6, 4],
            pointRadius: 0,
            pointHitRadius: 0,
            fill: false,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 200 },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (ctx.dataset.label === 'Cel') return `Cel: ${indicator.direction} ${formatter.fmt(indicator.target)} ${formatter.unitLabel}`;
                return `${formatter.fmt(ctx.parsed.y as number)} ${formatter.unitLabel}`;
              },
            },
          },
        },
        scales: {
          y: { beginAtZero: false, ticks: { font: { size: 11 } } },
          x: { ticks: { font: { size: 11 } } },
        },
      },
    });

    return () => chartRef.current?.destroy();
  }, [indicator]);

  return <canvas ref={canvasRef} role="img" aria-label={`Wykres miesięczny — ${indicator.name}`} />;
}
