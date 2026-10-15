import type { CSSProperties } from 'react';
import { Button } from '../../components/ui/Button';
import { RUN_STATUS, formatDateTime, formatDay, formatDuration, skippedTotal } from './dataImportShared';
import type { ImportHistoryRow } from '../../types/dataImport';

interface ImportHistoryCardProps {
  rows: ImportHistoryRow[];
  loading: boolean;
  /** Id of the run shown in the live panel — its row gets highlighted. */
  activeId: number | null;
  onReload: () => void;
  style?: CSSProperties;
}

function duration(row: ImportHistoryRow): string {
  if (!row.started_at || !row.finished_at) return '—';
  return formatDuration(new Date(row.finished_at).getTime() - new Date(row.started_at).getTime());
}

/** Historia importów — the last 20 runs (GET /api/import/history), newest first. */
export function ImportHistoryCard({ rows, loading, activeId, onReload, style }: ImportHistoryCardProps) {
  return (
    <section className="form-card di-card di-rise" style={style} aria-labelledby="di-history-title">
      <div className="di-card-head">
        <h2 id="di-history-title" className="di-card-title">
          Historia importów <span className="di-card-count">ostatnie 20</span>
        </h2>
        <Button variant="ghost" small icon="refresh" onClick={onReload} isLoading={loading} loadingText="Ładuję…" aria-label="Odśwież historię importów">
          Odśwież
        </Button>
      </div>

      <div className="table-container di-history-table">
        <table className="refined-table">
          <thead>
            <tr>
              <th scope="col">Rozpoczęto</th>
              <th scope="col">Zakres wizyt</th>
              <th scope="col">Uruchomił</th>
              <th scope="col">Status</th>
              <th scope="col" className="di-num">
                Wstawiono
              </th>
              <th scope="col" className="di-num">
                Pominięto
              </th>
              <th scope="col" className="di-num">
                Błędy
              </th>
              <th scope="col" className="di-num">
                Czas
              </th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              Array.from({ length: 4 }, (_, i) => (
                <tr key={`sk-${i}`} aria-hidden="true">
                  <td colSpan={8}>
                    <span className="skeleton di-row-skeleton" />
                  </td>
                </tr>
              ))
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-state cell-empty">
                  Nie uruchomiono jeszcze żadnego importu.
                </td>
              </tr>
            ) : (
              rows.map((row, i) => {
                const st = RUN_STATUS[row.status] ?? RUN_STATUS.unknown;
                const errors = row.stats.errors ?? 0;
                return (
                  <tr key={row.id} className="di-history-row" data-active={row.id === activeId ? 'true' : undefined} style={{ '--i': Math.min(i, 12) } as CSSProperties}>
                    <td>
                      <span className="di-cell-strong">{formatDateTime(row.started_at)}</span>
                      <span className="di-cell-sub">#{row.id}</span>
                    </td>
                    <td>
                      {row.date_range_start && row.date_range_end ? `${formatDay(row.date_range_start)} – ${formatDay(row.date_range_end)}` : '—'}
                      {row.dry_run && <span className="di-tag di-tag-inline">próba</span>}
                    </td>
                    <td>{row.triggered_by_name || '—'}</td>
                    <td>
                      <span className="di-pill" data-tone={st.tone} data-live={row.status === 'running' ? 'true' : undefined} title={row.error_message ?? undefined}>
                        <span className="di-pill-dot" aria-hidden="true" />
                        {st.label}
                      </span>
                    </td>
                    <td className="di-num">{row.stats.inserted ?? '—'}</td>
                    <td className="di-num">{skippedTotal(row.stats) || '—'}</td>
                    <td className="di-num" data-bad={errors > 0 ? 'true' : undefined}>
                      {row.stats.errors ?? '—'}
                    </td>
                    <td className="di-num">{duration(row)}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
