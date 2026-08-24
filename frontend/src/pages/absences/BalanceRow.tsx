import { useState } from 'react';
import { absenceBalancesApi } from '../../lib/api/absenceBalances';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Icon } from '../../lib/icons/Icon';
import type { AbsenceBalanceRow, BalanceStatus } from '../../types/absenceBalance';

function unitLabel(unit: string) {
  return unit === 'hours' ? 'h' : 'd';
}

function barClass(s: BalanceStatus) {
  return s === 'exceeded' ? 'bar-exceeded' : s === 'warning' ? 'bar-warning' : 'bar-ok';
}

function badgeClass(s: BalanceStatus) {
  return { exceeded: 'badge-exceeded', warning: 'badge-warning', unlimited: 'badge-unlimited', ok: 'badge-ok' }[s] ?? 'badge-ok';
}

function badgeLabel(s: BalanceStatus) {
  return { exceeded: 'Przekroczony', warning: 'Blisko limitu', unlimited: 'Bez limitu', ok: 'OK' }[s] ?? s;
}

/** Live-computed status from the CURRENT (possibly edited, unsaved) used/limit
 * values — mirrors updateRowDisplay()'s client-side status mirror of the
 * server's net_used >= limit * warning_pct rule, so the bar/badge update as
 * the user types, before Save is even pressed. */
function computeLiveStatus(used: number, limit: number, warningThresholdPct: number): { status: BalanceStatus; pct: number } {
  if (!limit || limit <= 0) return { status: 'unlimited', pct: 0 };
  const pct = (used / limit) * 100;
  const status: BalanceStatus = used > limit ? 'exceeded' : used >= limit * warningThresholdPct ? 'warning' : 'ok';
  return { status, pct };
}

interface Props {
  row: AbsenceBalanceRow;
  isFirstInGroup: boolean;
  isLastInGroup: boolean;
  onChanged: (patch: Partial<AbsenceBalanceRow>) => void;
}

/** One (employee, category) row — inline-editable used/limit/period with a
 * reason field that appears only when "used" changes (server mandates a
 * reason for any balance adjustment), Save + one-level Undo + a destructive
 * "reset to zero" delete. Ported from balances.html's per-row spinbox/save/
 * undo/delete script — state that lived in `tr.dataset.*` there now lives as
 * local React state. */
export function BalanceRowView({ row, isFirstInGroup, isLastInGroup, onChanged }: Props) {
  const toast = useToast();
  const confirm = useConfirm();
  const step = row.unit === 'hours' ? 0.5 : 1;

  const [used, setUsed] = useState(row.net_used);
  const [limit, setLimit] = useState(row.status === 'unlimited' ? 0 : row.limit);
  const [period, setPeriod] = useState(row.period_label ?? '');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [undoState, setUndoState] = useState<{ used: number; limit: number; period: string } | null>(null);

  const usedDirty = Math.abs(used - row.net_used) >= 0.001;
  const limitDirty = Math.abs(limit - (row.status === 'unlimited' ? 0 : row.limit)) >= 0.001;
  const periodDirty = period !== (row.period_label ?? '');
  const dirty = usedDirty || limitDirty || periodDirty;
  const reasonOk = !usedDirty || reason.trim().length > 0;
  const canSave = dirty && reasonOk && !saving;

  const live = computeLiveStatus(used, limit, row.warning_threshold_pct ? row.warning_threshold_pct / 100 : 0.8);
  const displayStatus = limit > 0 ? live.status : 'unlimited';
  const displayPct = limit > 0 ? Math.min(live.pct, 100) : 0;
  const statusLabel = displayStatus === 'ok' ? `Zostało: ${(limit - used).toFixed(step === 1 ? 0 : 1)} ${unitLabel(row.unit)}` : badgeLabel(displayStatus);

  function step_(dir: 1 | -1, field: 'used' | 'limit') {
    const setter = field === 'used' ? setUsed : setLimit;
    const current = field === 'used' ? used : limit;
    setter(Math.max(0, Number((current + dir * step).toFixed(step === 1 ? 0 : 1))));
  }

  async function handleSave() {
    const delta = Number((used - row.net_used).toFixed(1));
    setSaving(true);
    try {
      const calls: Promise<unknown>[] = [];
      if (Math.abs(delta) >= 0.001) {
        calls.push(absenceBalancesApi.createAdjustment(row.employee_id, row.category_id, delta, reason.trim(), period || null));
      }
      if (limitDirty) {
        calls.push(absenceBalancesApi.setLimit(row.employee_id, row.category_id, limit));
      }
      await Promise.all(calls);
      setUndoState({ used: row.net_used, limit: row.status === 'unlimited' ? 0 : row.limit, period: row.period_label ?? '' });
      setReason('');
      toast.success('Zapisano zmianę bilansu');
      onChanged({ net_used: used, limit, period_label: period, status: displayStatus, pct: live.pct });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zapisać zmian');
    } finally {
      setSaving(false);
    }
  }

  async function handleUndo() {
    if (!undoState) return;
    const undoDelta = Number((undoState.used - used).toFixed(1));
    setSaving(true);
    try {
      const calls: Promise<unknown>[] = [];
      if (Math.abs(undoDelta) >= 0.001) {
        calls.push(absenceBalancesApi.createAdjustment(row.employee_id, row.category_id, undoDelta, 'Cofnięcie ostatniego zapisu', undoState.period || null));
      }
      if (Math.abs(undoState.limit - limit) >= 0.001) {
        calls.push(absenceBalancesApi.setLimit(row.employee_id, row.category_id, undoState.limit));
      }
      await Promise.all(calls);
      setUsed(undoState.used);
      setLimit(undoState.limit);
      setPeriod(undoState.period);
      setUndoState(null);
      toast.success('Cofnięto ostatni zapis');
      onChanged({ net_used: undoState.used, limit: undoState.limit, period_label: undoState.period });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się cofnąć zapisu');
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (used <= 0) {
      toast.info('Bilans jest już zerowy');
      return;
    }
    const ok = await confirm({
      title: 'Resetuj bilans',
      message: `Wyzerować bilans tej kategorii? Wpadnie korekta −${used.toFixed(1)} do historii — wstecz się tego nie wyklika.`,
      confirmText: 'Resetuj',
    });
    if (!ok) return;
    setSaving(true);
    try {
      await absenceBalancesApi.createAdjustment(row.employee_id, row.category_id, -used, 'Resetowanie bilansu', null);
      toast.success('Bilans wyzerowany');
      setUsed(0);
      onChanged({ net_used: 0 });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zresetować bilansu');
    } finally {
      setSaving(false);
    }
  }

  const groupCls = [isFirstInGroup ? 'group-first' : '', isLastInGroup ? 'group-last' : ''].filter(Boolean).join(' ');
  const rowCtx = `${row.employee_name}, ${row.category_name}`;

  return (
    <tr className={`${displayStatus === 'exceeded' ? 'exceeded-row' : ''} ${groupCls}`}>
      <td className="cell-name" style={isFirstInGroup ? { fontWeight: 500, whiteSpace: 'nowrap' } : undefined}>
        {isFirstInGroup ? row.employee_name : <span className="emp-grouped-hidden">{row.employee_name}</span>}
      </td>
      <td data-label="Kategoria" style={{ whiteSpace: 'nowrap' }}>
        {row.category_name}
      </td>
      <td data-label="Okres">
        <input type="text" className="row-period-input" aria-label={`Okres — ${rowCtx}`} placeholder="np. 2026" value={period} onChange={(e) => setPeriod(e.target.value)} />
      </td>
      <td data-label="Wykorzystano">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', whiteSpace: 'nowrap' }}>
          <div className="row-spinbox-wrap">
            <input
              type="number"
              className="row-spinbox"
              aria-label={`Wykorzystano — ${rowCtx}`}
              step={step}
              min={0}
              value={used}
              onChange={(e) => setUsed(Math.max(0, Number(e.target.value) || 0))}
            />
            <div className="row-spinbox-arrows">
              <button type="button" className="row-arrow" tabIndex={-1} onClick={() => step_(1, 'used')}>
                <Icon name="expand_more" className="rot-180" />
              </button>
              <button type="button" className="row-arrow" tabIndex={-1} onClick={() => step_(-1, 'used')}>
                <Icon name="expand_more" />
              </button>
            </div>
          </div>
          <span className="row-unit-label">{unitLabel(row.unit)}</span>
          {usedDirty && (
            <input
              type="text"
              className="row-reason"
              style={{ display: 'block' }}
              aria-label={`Powód zmiany — ${rowCtx}`}
              placeholder="Powód zmiany…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
        </div>
      </td>
      <td data-label="Limit" style={{ textAlign: 'right' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
          <div className="row-spinbox-wrap">
            <input
              type="number"
              className="row-spinbox"
              aria-label={`Limit — ${rowCtx}`}
              step={step}
              min={0}
              value={limit}
              onChange={(e) => setLimit(Math.max(0, Number(e.target.value) || 0))}
            />
            <div className="row-spinbox-arrows">
              <button type="button" className="row-arrow" tabIndex={-1} onClick={() => step_(1, 'limit')}>
                <Icon name="expand_more" className="rot-180" />
              </button>
              <button type="button" className="row-arrow" tabIndex={-1} onClick={() => step_(-1, 'limit')}>
                <Icon name="expand_more" />
              </button>
            </div>
          </div>
          <span className="row-unit-label">{limit <= 0 ? '∞' : unitLabel(row.unit)}</span>
        </div>
      </td>
      <td data-label="% wykorzystania">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div className="progress-wrap" style={{ flex: 1 }}>
            <div className={`progress-bar ${barClass(displayStatus)}`} style={{ width: `${displayPct}%` }} />
          </div>
          <span className="row-pct-label">{displayStatus === 'unlimited' ? '—' : `${live.pct.toFixed(0)}%`}</span>
        </div>
      </td>
      <td data-label="Status">
        <span className={`status-badge ${badgeClass(displayStatus)}`}>{statusLabel}</span>
      </td>
      <td className="cell-actions" style={{ whiteSpace: 'nowrap' }}>
        <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'flex-end' }}>
          <button type="button" className="icon-btn delete-btn" title="Resetuj bilans do zera" disabled={saving} onClick={handleReset}>
            <Icon name="delete" />
          </button>
          <button type="button" className="icon-btn save-btn" title="Zapisz zmiany" disabled={!canSave} onClick={handleSave}>
            <Icon name="save" />
          </button>
          <button type="button" className="icon-btn undo-btn" title="Cofnij ostatni zapis" disabled={!undoState || saving} onClick={handleUndo}>
            <Icon name="undo" />
          </button>
        </div>
      </td>
    </tr>
  );
}
