import { useEffect, useRef } from 'react';
import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js';
import type { MonthlyTotals } from '../../types/dashboard';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

/**
 * Bar chart for "Kwoty faktur — ostatnie 12 miesięcy" — ported from
 * templates/dashboard/index.html's `loadMonthlyChart()` (Chart.js via CDN
 * `<script>` tag there). Here `chart.js` is an npm dependency instead
 * (self-contained SPA bundle, no global-script race, versioned like every
 * other dependency) — same library, same chart config, different loading
 * mechanism. Colors use `--color-ink`/`--color-accent` tokens instead of the
 * original's hardcoded `rgba(26,26,26,…)`/gold literals (DESIGN.md §16 "never
 * hardcode when a token exists" — same rule Decyzja D18 applied in Faza 1).
 */
export function MonthlyChart({ labels, data }: MonthlyTotals) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const style = getComputedStyle(document.documentElement);
    const ink = style.getPropertyValue('--color-ink').trim() || '#1a1a1a';
    const accent = style.getPropertyValue('--color-accent').trim() || '#c9a227';
    const border = style.getPropertyValue('--color-border').trim() || '#e8e6e1';
    const inkMuted = style.getPropertyValue('--color-ink-muted').trim() || '#6b6b6b';

    chartRef.current?.destroy();
    chartRef.current = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Kwota brutto (zł)',
            data,
            backgroundColor: ink,
            borderColor: ink,
            borderWidth: 1,
            borderRadius: 2,
            hoverBackgroundColor: accent,
            hoverBorderColor: accent,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: ink,
            padding: 12,
            titleFont: { size: 13, weight: 600, family: 'Inter' },
            bodyFont: { size: 14, weight: 500, family: 'Inter' },
            callbacks: {
              label: (context) => {
                const value = context.parsed.y as number;
                return 'Kwota: ' + value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' zł';
              },
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: border },
            ticks: {
              font: { size: 11, family: 'Inter' },
              color: inkMuted,
              callback: (value) => {
                const n = Number(value);
                if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + ' M';
                if (n >= 1_000) return (n / 1_000).toFixed(0) + ' K';
                return n;
              },
            },
          },
          x: {
            grid: { display: false },
            ticks: { font: { size: 11, family: 'Inter' }, color: inkMuted },
          },
        },
      },
    });

    return () => chartRef.current?.destroy();
  }, [labels, data]);

  return <canvas ref={canvasRef} role="img" aria-label="Wykres kwot faktur z ostatnich 12 miesięcy" />;
}
