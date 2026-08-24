import { KpiIndicatorChart } from './KpiIndicatorChart';
import { getKpiFormatter, kpiStatusClass } from './kpiFormat';
import type { KpiIndicator, KpiProcess } from '../../types/kpiMatrix';

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);
const TABLE_COLS = 18;

interface Props {
  proc: KpiProcess;
  indicator: KpiIndicator;
  isFirst: boolean;
  expanded: boolean;
  onToggle: () => void;
  onTip: (text: string, target: HTMLElement) => void;
  onTipHide: () => void;
}

/** One indicator row (+ its process-name cell, rowspan'd, on the first row of
 * each process group) — ported from static/js/analytics/kpi_matrix.js's
 * `buildRow()`. Click toggles the expanded chart row rendered by the parent
 * table (kept there, not here, so only one indicator's chart is ever mounted
 * at a time — matches the original's single shared `expandedChart` slot). */
export function KpiIndicatorRow({ proc, indicator: ind, isFirst, expanded, onToggle, onTip, onTipHide }: Props) {
  const formatter = getKpiFormatter(ind);

  if (ind.unavailable_note) {
    return (
      <tr className={isFirst ? 'proc-band-a' : 'proc-band-b'}>
        {isFirst && (
          <td className="cell-process" rowSpan={proc.indicators.length}>
            {proc.id} · {proc.name}
          </td>
        )}
        <td className="cell-indicator">
          <span className="kpi-tip" onMouseEnter={(e) => onTip(ind.description || ind.unavailable_note || '', e.currentTarget)} onMouseLeave={onTipHide}>
            {ind.name}
          </span>
        </td>
        <td className="cell-unit">{ind.unit}</td>
        <td className="cell-na" colSpan={15}>
          brak danych źródłowych
        </td>
      </tr>
    );
  }

  return (
    <>
      <tr className={`${isFirst ? 'proc-band-a' : 'proc-band-b'} kpi-row-clickable${expanded ? ' kpi-row-expanded' : ''}`} onClick={onToggle}>
        {isFirst && (
          <td className="cell-process" rowSpan={proc.indicators.length}>
            {proc.id} · {proc.name}
          </td>
        )}
        <td className="cell-indicator">
          <span className="kpi-tip" onMouseEnter={(e) => ind.description && onTip(ind.description, e.currentTarget)} onMouseLeave={onTipHide}>
            {ind.name}
          </span>
        </td>
        <td className="cell-unit">{formatter.unitLabel}</td>
        <td className="cell-yprior">{formatter.fmt(ind.y_prior)}</td>
        {MONTHS.map((m) => {
          const v = ind.months[String(m)] ?? null;
          return (
            <td key={m} className={kpiStatusClass(v, ind.direction, ind.target)}>
              {formatter.fmt(v)}
            </td>
          );
        })}
        <td className={`cell-year ${kpiStatusClass(ind.y_current, ind.direction, ind.target)}`}>{formatter.fmt(ind.y_current)}</td>
        <td className="cell-target">
          {ind.direction} {formatter.fmt(ind.target)}
        </td>
      </tr>
      {expanded && (
        <tr className="kpi-detail-row">
          <td colSpan={TABLE_COLS}>
            <div className="kpi-chart-box">
              <KpiIndicatorChart indicator={ind} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
