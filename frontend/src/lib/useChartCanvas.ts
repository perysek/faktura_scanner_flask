import { useEffect, useRef } from 'react';
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  type ChartConfiguration,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  RadarController,
  RadialLinearScale,
  Tooltip,
} from 'chart.js';

Chart.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  RadarController,
  RadialLinearScale,
  Tooltip,
);

/**
 * Canvas-ref + create/destroy boilerplate shared by every employee-analytics
 * chart (8 call sites across the 5 tabs) — same shared-hook idea as
 * `useApiData` for data fetching. `configFactory` returning `null` skips
 * rendering (e.g. a series with no data yet); the previous chart instance is
 * always destroyed first so re-renders never leak canvases.
 */
export function useChartCanvas(configFactory: () => ChartConfiguration | null, deps: unknown[]) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    chartRef.current?.destroy();
    chartRef.current = null;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const config = configFactory();
    if (!config) return;
    chartRef.current = new Chart(canvas, config);
    return () => chartRef.current?.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return canvasRef;
}

/** Chart accent colors — hardcoded from `--color-chart-*` / `--color-status-*`
 * tokens (frontend/src/styles/tokens.css). Those tokens are defined only in
 * `:root`, never overridden by the app's `[data-theme]` salon-color variants,
 * so a static copy here can't drift from the CSS the way a themed color
 * would. */
export const CHART_COLORS = {
  blue: '#2563eb',
  blueFill: 'rgba(37,99,235,0.15)',
  green: '#2d6a4f',
  greenFill: 'rgba(45,106,79,0.15)',
  purple: '#7c3aed',
  purpleFill: 'rgba(124,58,237,0.15)',
  amber: '#f59e0b',
  amberFill: 'rgba(245,158,11,0.15)',
  red: '#ef4444',
  redFill: 'rgba(239,68,68,0.12)',
  teal: '#14b8a6',
  tealFill: 'rgba(20,184,166,0.15)',
  orange: '#fb923c',
  emerald: '#34d399',
} as const;

export const CHART_BASE_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
} as const;
