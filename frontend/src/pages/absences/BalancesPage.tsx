import { useEffect, useMemo, useState } from 'react';
import './BalancesPage.css';
import { absenceBalancesApi } from '../../lib/api/absenceBalances';
import { BalanceRowView } from './BalanceRow';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import type { AbsenceBalanceRow, AbsenceCategory } from '../../types/absenceBalance';

function rowKey(r: Pick<AbsenceBalanceRow, 'employee_id' | 'category_id'>) {
  return `${r.employee_id}:${r.category_id}`;
}

/** Bilanse urlopowe — module-inventory.md "Wymaga audytu" list. Ported from
 * templates/absences/balances.html: per-employee limits/usage against
 * tracked absence categories, inline-editable per row (spinboxes for
 * used/limit, a period label, save+undo+reset-to-zero), filterable by
 * name/category/status. Backend (routes/absence_balance_routes.py) was
 * already fully JSON — no server changes for this module. */
export function BalancesPage() {
  // Original page: any Escape navigates back to /absences (the "wnioski"
  // list) unless a confirm modal is open — ConfirmProvider already claims
  // Escape for itself while its own modal is open (useEscapeClaim), so this
  // binding correctly no-ops during the reset-to-zero confirm dialog.
  useEscapeBack('/nieobecnosci');
  const [rows, setRows] = useState<AbsenceBalanceRow[]>([]);
  const [categories, setCategories] = useState<AbsenceCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [cats, employeeIds] = await Promise.all([absenceBalancesApi.trackedCategories(), absenceBalancesApi.summaryEmployeeIds()]);
        if (cancelled) return;
        setCategories(cats);

        const perEmployee = await Promise.all(
          employeeIds.map((employeeId) =>
            absenceBalancesApi
              .employeeBalances(employeeId)
              .then((r) => r.balances.map((b): AbsenceBalanceRow => ({ ...b, employee_id: employeeId, employee_name: r.employee_name })))
              .catch(() => [] as AbsenceBalanceRow[]),
          ),
        );
        if (!cancelled) setRows(perEmployee.flat());
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  function patchRow(employeeId: number, categoryId: number, patch: Partial<AbsenceBalanceRow>) {
    setRows((prev) => prev.map((r) => (r.employee_id === employeeId && r.category_id === categoryId ? { ...r, ...patch } : r)));
  }

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (s && !r.employee_name.toLowerCase().includes(s)) return false;
      if (catFilter && String(r.category_id) !== catFilter) return false;
      if (statusFilter && r.status !== statusFilter) return false;
      return true;
    });
  }, [rows, search, catFilter, statusFilter]);

  // Sort descending by employee name (Z → A), matching the original.
  const sorted = useMemo(() => [...filtered].sort((a, b) => b.employee_name.localeCompare(a.employee_name, 'pl', { sensitivity: 'base' })), [filtered]);

  const stats = useMemo(() => {
    const tracked = new Set(rows.map((r) => r.employee_id)).size;
    const warning = rows.filter((r) => r.status === 'warning').length;
    const exceeded = rows.filter((r) => r.status === 'exceeded').length;
    return { tracked, warning, exceeded };
  }, [rows]);

  return (
    <div className="refined-page balances-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Bilanse urlopowe</h1>
          <p className="page-subtitle">Zarządzanie limitami i korektami</p>
        </div>
      </header>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Pracownicy ze śledzeniem</div>
          <div className="stat-value">{loading ? '—' : stats.tracked}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Śledzone kategorie</div>
          <div className="stat-value">{loading ? '—' : categories.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Bliscy limitu</div>
          <div className="stat-value warning">{loading ? '—' : stats.warning}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Przekroczony limit</div>
          <div className="stat-value exceeded">{loading ? '—' : stats.exceeded}</div>
        </div>
      </div>

      <div className="filter-bar">
        <input type="text" className="filter-input" placeholder="Szukaj pracownika…" style={{ minWidth: 220 }} value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="filter-input" aria-label="Filtruj według kategorii" value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
          <option value="">Wszystkie kategorie</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select className="filter-input" aria-label="Filtruj według statusu" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Wszystkie statusy</option>
          <option value="ok">OK</option>
          <option value="warning">Blisko limitu</option>
          <option value="exceeded">Przekroczony</option>
        </select>
      </div>

      <div className="card">
        <div className="card-body">
          <table className="balance-table stack-cards">
            <thead>
              <tr>
                <th style={{ width: '9rem' }}>Pracownik</th>
                <th style={{ width: '9rem' }}>Kategoria</th>
                <th style={{ width: '6rem' }}>Okres</th>
                <th>Wykorzystano</th>
                <th style={{ width: '7rem', textAlign: 'right' }}>Limit</th>
                <th style={{ width: '13rem', textAlign: 'center' }}>% wykorzystania</th>
                <th style={{ width: '13rem', textAlign: 'center' }}>Status</th>
                <th style={{ width: '6rem', textAlign: 'right' }}>Akcje</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="cell-empty" style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-ink-subtle)' }}>
                    Ładowanie…
                  </td>
                </tr>
              ) : sorted.length === 0 ? (
                <tr>
                  <td colSpan={8} className="cell-empty" style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-ink-subtle)' }}>
                    Brak danych
                  </td>
                </tr>
              ) : (
                sorted.map((row, i) => {
                  const isFirst = i === 0 || sorted[i - 1].employee_id !== row.employee_id;
                  const isLast = i === sorted.length - 1 || sorted[i + 1].employee_id !== row.employee_id;
                  return (
                    <BalanceRowView key={rowKey(row)} row={row} isFirstInGroup={isFirst} isLastInGroup={isLast} onChanged={(patch) => patchRow(row.employee_id, row.category_id, patch)} />
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
