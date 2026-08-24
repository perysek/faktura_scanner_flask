import { useEffect, useState } from 'react';
import './KpiMatrixPage.css';
import { kpiMatrixApi } from '../../lib/api/kpiMatrix';
import { ApiError } from '../../lib/api/client';
import { KpiIndicatorRow } from './KpiIndicatorRow';
import { Icon } from '../../lib/icons/Icon';
import type { KpiMatrixResponse } from '../../types/kpiMatrix';

const MONTH_HEADERS = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];

/** Wskaźniki biznesowe — ISO 9001/IATF-style monthly KPI matrix (8 processes
 * × effectiveness/efficiency indicators, plus Obrót in P7). Ported from
 * templates/analytics/kpi_matrix.html + static/js/analytics/kpi_matrix.js.
 * Backend (/api/analytics/kpi-matrix) was already fully JSON — no server
 * changes for this page.
 *
 * Scope note: this is the smaller, self-contained half of the "Analityka /
 * KPI / Przychody" module-inventory.md entry. The main analytics dashboard
 * (/analiza-biznesowa — templates/analytics/dashboard.html, 449 lines +
 * static/js/analytics/dashboard.js, 1475 lines: 10 Chart.js graphs, a custom
 * peak-hours heatmap, a stateful period-navigation system with month/year/
 * custom-range granularity, and several data tables) and a previously
 * undocumented third page (/income — templates/income/dashboard.html) are
 * deliberately deferred — see implementation-log.md for the full audit
 * correction and reasoning. */
export function KpiMatrixPage() {
  const [data, setData] = useState<KpiMatrixResponse | null>(null);
  const [year, setYear] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [tip, setTip] = useState<{ text: string; top: number; left: number } | null>(null);

  function load(y: number | null) {
    setLoading(true);
    setError(null);
    kpiMatrixApi
      .get(y ?? undefined)
      .then((r) => {
        setData(r);
        setYear(r.year);
        setExpandedKey(null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Błąd danych'))
      .finally(() => setLoading(false));
  }

  useEffect(() => load(null), []);

  function showTip(text: string, target: HTMLElement) {
    const r = target.getBoundingClientRect();
    const tipW = 380;
    let left = r.left;
    if (left + tipW > window.innerWidth - 12) left = window.innerWidth - tipW - 12;
    setTip({ text, top: r.bottom + 6, left: Math.max(12, left) });
  }

  const totalIndicators = data?.processes.reduce((sum, p) => sum + p.indicators.length, 0) ?? 0;

  return (
    <div className="refined-page kpi-page animate-fade-up">
      <div className="page-header kpi-header">
        <div>
          <h1 className="page-title">Wskaźniki biznesowe</h1>
          <p className="page-subtitle">
            {loading ? 'Ładowanie…' : error ? 'Błąd ładowania danych' : `Rok ${data?.year} — ${data?.processes.length} procesów, ${totalIndicators} wskaźników (skuteczność + efektywność)`}
          </p>
        </div>
        <div className="kpi-controls">
          <div className="kpi-legend">
            <span>
              <span className="dot good" /> cel osiągnięty
            </span>
            <span>
              <span className="dot bad" /> cel niespełniony
            </span>
          </div>
          <div className="kpi-year-nav">
            <button type="button" className="refined-btn-secondary refined-btn-sm" disabled={!data || year === data.min_year} onClick={() => year && load(year - 1)} title="Poprzedni rok" aria-label="Poprzedni rok">
              <Icon name="chevron_left" />
            </button>
            <select className="form-select refined-btn-sm kpi-year-select" aria-label="Wybierz rok" value={year ?? ''} onChange={(e) => load(Number(e.target.value))} disabled={!data}>
              {data &&
                Array.from({ length: data.max_year - data.min_year + 1 }, (_, i) => data.max_year - i).map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
            </select>
            <button type="button" className="refined-btn-secondary refined-btn-sm" disabled={!data || year === data.max_year} onClick={() => data && load(data.max_year)}>
              Aktualny
            </button>
            <button type="button" className="refined-btn-secondary refined-btn-sm" disabled={!data || year === data.max_year} onClick={() => year && load(year + 1)} title="Następny rok" aria-label="Następny rok">
              <Icon name="chevron_right" />
            </button>
          </div>
        </div>
      </div>

      <div className="kpi-table-wrap">
        <table className="kpi-table">
          <colgroup>
            <col className="col-process" />
            <col className="col-indicator" />
            <col className="col-unit" />
            <col className="col-year" />
            {MONTH_HEADERS.map((m) => (
              <col key={m} className="col-month" />
            ))}
            <col className="col-year" />
            <col className="col-target" />
          </colgroup>
          <thead>
            <tr>
              <th>Proces</th>
              <th>Wskaźnik</th>
              <th>Jedn.</th>
              <th>Rok-1</th>
              {MONTH_HEADERS.map((m) => (
                <th key={m}>{m}</th>
              ))}
              <th>{year ? `Rok ${year}` : 'Rok'}</th>
              <th>Cel</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={18} style={{ textAlign: 'center', padding: '2rem' }}>
                  Ładowanie danych…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={18} style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-error)' }}>
                  Nie udało się wczytać wskaźników ({error})
                </td>
              </tr>
            ) : (
              data?.processes.map((proc) =>
                proc.indicators.map((ind, idx) => (
                  <KpiIndicatorRow
                    key={ind.key}
                    proc={proc}
                    indicator={ind}
                    isFirst={idx === 0}
                    expanded={expandedKey === ind.key}
                    onToggle={() => setExpandedKey((k) => (k === ind.key ? null : ind.key))}
                    onTip={showTip}
                    onTipHide={() => setTip(null)}
                  />
                )),
              )
            )}
          </tbody>
        </table>
      </div>

      {tip && (
        <div className="kpi-hover-tip" style={{ display: 'block', top: tip.top, left: tip.left }}>
          {tip.text}
        </div>
      )}
    </div>
  );
}
