import { useEffect, useRef } from 'react';
import { Chart, LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Filler } from 'chart.js';
import type { ServicePriceHistoryEntry } from '../../types/service';

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Filler);

function fmtDateShort(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('pl-PL', { year: '2-digit', month: '2-digit', day: '2-digit' });
}

/** Price-history sparkline — ported from services/view.html's `drawSparkline()`.
 * `history` is newest-first (API order); chart wants chronological order. */
export function PriceHistorySparkline({ history }: { history: ServicePriceHistoryEntry[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || history.length === 0) return;
    const chrono = [...history].reverse();

    chartRef.current?.destroy();
    chartRef.current = new Chart(canvas, {
      type: 'line',
      data: {
        labels: chrono.map((h) => fmtDateShort(h.effective_from)),
        datasets: [
          {
            data: chrono.map((h) => h.price),
            // Intentional literal, ported 1:1 — burnt-orange, visibly darker
            // than --color-chart-amber (#f59e0b); not an oversight.
            borderColor: '#b45309',
            backgroundColor: 'rgba(180, 83, 9, 0.08)',
            borderWidth: 2,
            fill: true,
            tension: 0.2,
            pointRadius: 3,
            pointBackgroundColor: '#b45309',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(ctx.parsed.y as number) + ' PLN',
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 } } },
          y: { beginAtZero: false, ticks: { font: { size: 10 } } },
        },
      },
    });

    return () => chartRef.current?.destroy();
  }, [history]);

  return <canvas ref={canvasRef} role="img" aria-label="Wykres historii cen usługi" />;
}
