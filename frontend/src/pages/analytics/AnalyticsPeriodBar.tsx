import { useState } from 'react';
import { Icon } from '../../lib/icons/Icon';
import type { UseAnalyticsPeriod } from './useAnalyticsPeriod';
import type { AnalyticsPeriod } from '../../types/analyticsDashboard';

const PRESETS: { key: AnalyticsPeriod; label: string }[] = [
  { key: 'current_month', label: 'Ten miesiąc' },
  { key: 'last_month', label: 'Ostatni miesiąc' },
  { key: 'current_year', label: 'Rok do daty' },
];

/** Period selector + prev/next nav + custom-range modal trigger — ported from
 * dashboard.html's period-selector markup, driven by `useAnalyticsPeriod`. */
export function AnalyticsPeriodBar({ periodState }: { periodState: UseAnalyticsPeriod }) {
  const { period, description, select, navigate } = periodState;
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <div className="abiz-period-bar">
        <div className="abiz-period-nav">
          <button type="button" className="refined-btn-secondary refined-btn-sm" title="Poprzedni okres" aria-label="Poprzedni okres" onClick={() => navigate(-1)}>
            <Icon name="chevron_left" />
          </button>
          <button type="button" className="refined-btn-secondary refined-btn-sm" onClick={() => select('current_month')}>
            Dziś
          </button>
          <button type="button" className="refined-btn-secondary refined-btn-sm" title="Następny okres" aria-label="Następny okres" onClick={() => navigate(1)}>
            <Icon name="chevron_right" />
          </button>
        </div>

        <div className="abiz-period-selector">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              className={`refined-btn-secondary refined-btn-sm${period === p.key ? ' active' : ''}`}
              onClick={() => select(p.key)}
            >
              {p.label}
            </button>
          ))}
          <button
            type="button"
            className={`refined-btn-secondary refined-btn-sm${period === 'custom' ? ' active' : ''}`}
            onClick={() => setModalOpen(true)}
          >
            Własny zakres
          </button>
        </div>

        <p className="page-subtitle" style={{ margin: 0 }}>
          {description}
        </p>
      </div>

      {modalOpen && (
        <CustomRangeModal
          onCancel={() => setModalOpen(false)}
          onApply={(start, end) => {
            periodState.applyCustom(start, end);
            setModalOpen(false);
          }}
        />
      )}
    </>
  );
}

function CustomRangeModal({ onCancel, onApply }: { onCancel: () => void; onApply: (start: string, end: string) => void }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [error, setError] = useState<string | null>(null);

  function handleApply() {
    if (!start || !end) {
      setError('Wybierz obie daty.');
      return;
    }
    if (start > end) {
      setError('Data początkowa musi być wcześniejsza niż końcowa.');
      return;
    }
    onApply(start, end);
  }

  return (
    <div className="abiz-modal-backdrop fixed inset-0 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="refined-card max-w-md w-full" style={{ margin: '0 1rem' }} onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-medium mb-4">Wybierz zakres dat</h3>
        <div className="space-y-4">
          <div>
            <label className="form-label">Data początkowa</label>
            <input type="date" className="form-input" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <label className="form-label">Data końcowa</label>
            <input type="date" className="form-input" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          {error && <p className="analytics-error">{error}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" className="refined-btn-secondary refined-btn-sm" onClick={onCancel}>
              Anuluj
            </button>
            <button type="button" className="refined-btn-primary refined-btn-sm" onClick={handleApply}>
              Zastosuj
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
