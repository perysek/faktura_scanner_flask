export type TrendDirection = 'up' | 'down' | 'flat';

// Direction is the single source of truth; color derives from it so the
// glyph/label/stroke can never disagree — ported 1:1 from
// templates/clients/list.html's inline sparklineSvg()/trendDirection().
function trendDirection(weeks: number[]): TrendDirection {
  if (!weeks || weeks.length < 4) return 'flat';
  const half = Math.floor(weeks.length / 2);
  const firstAvg = weeks.slice(0, half).reduce((a, b) => a + b, 0) / half;
  const lastAvg = weeks.slice(weeks.length - half).reduce((a, b) => a + b, 0) / half;
  const delta = lastAvg - firstAvg;
  return delta > 0.15 ? 'up' : delta < -0.15 ? 'down' : 'flat';
}

// `down`/`flat` have no exact --color-chart-*/-status-* token match except
// `down` (#ef4444 === --color-chart-red) — kept as the literal for `flat`
// since substituting the nearest token would be a subtle, unrequested shade
// change from the original widget (pixel-parity is the Faza 1 acceptance bar).
const TREND_COLOR: Record<TrendDirection, string> = { up: 'var(--color-success)', down: 'var(--color-chart-red)', flat: '#9ca3af' };
const TREND_LABEL: Record<TrendDirection, string> = { up: 'rosnący', down: 'spadkowy', flat: 'stabilny' };
const TREND_GLYPH: Record<TrendDirection, string> = { up: '▲', down: '▼', flat: '→' };

function smooth2(data: number[]): number[] {
  return data.map((v, i) => (i === 0 ? v : (v + data[i - 1]) / 2));
}

export function isVipClient(client: { is_active: boolean; visits_last_8w?: number }): boolean {
  // VIP = ≥3 visits in the last 8 weeks (the app-wide VIP rule) — drives the
  // gold avatar ring, the ★ VIP tag, and the VIP filter chip identically.
  return client.is_active && (client.visits_last_8w ?? 0) >= 3;
}

/** Weekly-completed-visit trend sparkline — one column-filling fluid SVG
 * polyline, ported 1:1 from list.html's sparklineSvg(). */
export function TrendSparkline({ months }: { months: number[] | undefined }) {
  if (!months || !months.length) {
    return <span style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>—</span>;
  }
  const dir = trendDirection(months);
  const color = TREND_COLOR[dir];
  const data = smooth2(months);
  const width = 96;
  const height = 22;
  const pad = 1.5;
  const max = Math.max(...data, 1);
  const step = (width - 2 * pad) / Math.max(data.length - 1, 1);
  const points = data
    .map((v, i) => {
      const x = pad + i * step;
      const y = pad + (height - 2 * pad) * (1 - v / max);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', width: '100%' }} role="img" aria-label={`Trend: ${TREND_LABEL[dir]}`}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{ display: 'block', flex: 1, minWidth: 0, overflow: 'visible' }}
        aria-hidden="true"
      >
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth={1.75}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <span aria-hidden="true" style={{ fontSize: '0.5625rem', color, flexShrink: 0 }}>
        {TREND_GLYPH[dir]}
      </span>
    </span>
  );
}
