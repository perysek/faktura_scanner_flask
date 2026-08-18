import { empColor } from '../../lib/appointments/employeeColor';
import type { EmployeeOption } from '../../types/appointment';

export interface EmployeeFilterProps {
  employees: EmployeeOption[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  /** Prepend a "Wszyscy" (all) option — the week/month/list views allow it,
   * the day view (single-employee-per-column layout) doesn't. */
  allowAll?: boolean;
  emptyLabel?: string;
}

/** Ported 1:1 from `static/js/employee-filter.js`'s `EmployeeFilter.render()` —
 * pills for ≤5 employees, a `<select>` dropdown above that. Used by all 4
 * Wizyty views (list/day/week/month) so "which employee am I looking at" is
 * one component instead of four near-identical copies, same rationale as the
 * original's own shared JS file. */
export function EmployeeFilter({ employees, selectedId, onSelect, allowAll = false, emptyLabel = 'Brak wizyt w tym okresie' }: EmployeeFilterProps) {
  if (employees.length === 0 && !allowAll) {
    return <span className="empf-label">{emptyLabel}</span>;
  }

  const options: Array<{ id: number | null; full_name: string }> = allowAll ? [{ id: null, full_name: 'Wszyscy' }, ...employees] : employees;
  const isSelected = (id: number | null) => (id === null ? selectedId === null : id === selectedId);

  if (employees.length <= 5) {
    return (
      <div className="empf-pills">
        {options.map((e) => {
          const active = isSelected(e.id);
          const c = e.id === null ? '#6b7280' : empColor(e.id);
          const dot = active ? 'rgba(255,255,255,0.9)' : c;
          return (
            <button
              key={e.id ?? 'all'}
              type="button"
              className={`empf-pill${active ? ' active' : ''}`}
              style={active ? { background: c, borderColor: c, color: '#fff' } : undefined}
              onClick={() => onSelect(e.id)}
            >
              <span className="empf-pill-dot" style={{ background: dot }} />
              {e.full_name}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className="empf-dropdown">
      <span className="empf-dd-dot" style={{ background: selectedId ? empColor(selectedId) : '#6b7280' }} />
      <select value={selectedId ?? ''} onChange={(e) => onSelect(e.target.value === '' ? null : Number(e.target.value))}>
        {options.map((e) => (
          <option key={e.id ?? 'all'} value={e.id ?? ''}>
            {e.full_name}
          </option>
        ))}
      </select>
    </div>
  );
}
