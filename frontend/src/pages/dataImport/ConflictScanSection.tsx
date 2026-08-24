import { useState } from 'react';
import { dataImportApi } from '../../lib/api/dataImport';
import { ApiError } from '../../lib/api/client';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button } from '../../components/ui/Button';
import type { ConflictGroup, ConflictReason } from '../../types/dataImport';

function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const REASON_LABELS: Record<ConflictReason, string> = {
  time_overlap: 'Nakładający się termin',
  same_day_different_stylist: 'Ten sam dzień, inny fryzjer',
};

/** Visit conflict scan — finds appointments duplicated by a reschedule (in
 * caldis.pl or manually): (1) same client/employee/service with overlapping
 * times, (2) same service with a different stylist on the same day. Ported
 * from data_import/index.html's inline scan/apply script. Read-only scan +
 * a destructive (but individually-reversible) apply step. */
export function ConflictScanSection() {
  const confirm = useConfirm();

  const [dateStart, setDateStart] = useState(todayISO(-90));
  const [dateEnd, setDateEnd] = useState(todayISO(90));
  const [scanning, setScanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; level: 'info' | 'error' | 'success' } | null>(null);
  const [summary, setSummary] = useState<{ candidateCount: number; groupCount: number; supersededCount: number } | null>(null);
  const [groups, setGroups] = useState<ConflictGroup[] | null>(null);
  const [scannedRange, setScannedRange] = useState<{ date_start: string; date_end: string } | null>(null);

  async function runScan() {
    if (!dateStart || !dateEnd) {
      setStatusMsg({ text: 'Wybierz zakres dat.', level: 'error' });
      return;
    }
    if (dateStart > dateEnd) {
      setStatusMsg({ text: 'Data od musi być wcześniejsza niż data do.', level: 'error' });
      return;
    }

    setScanning(true);
    setStatusMsg({ text: 'Skanuję...', level: 'info' });
    setGroups(null);

    try {
      const data = await dataImportApi.conflictScan(dateStart, dateEnd);
      setScannedRange({ date_start: dateStart, date_end: dateEnd });
      setSummary({ candidateCount: data.candidate_count, groupCount: data.group_count, supersededCount: data.superseded_count });
      setGroups(data.groups);
      setStatusMsg(data.group_count > 0 ? { text: 'Skan zakończony — sprawdź wyniki poniżej.', level: 'success' } : { text: 'Skan zakończony — brak konfliktów.', level: 'success' });
    } catch (err) {
      setStatusMsg({ text: err instanceof ApiError ? err.message : 'Błąd skanowania.', level: 'error' });
    } finally {
      setScanning(false);
    }
  }

  async function applyScan() {
    if (!scannedRange) return;
    const ok = await confirm({
      title: 'Zastosuj skan konfliktów',
      message:
        'Wybrane nadpisane wizyty zostaną usunięte: nadchodzące zostaną anulowane, a te, które już się odbyły, zostaną ukryte (i ich przychód przestanie się liczyć w raportach). Można to cofnąć ręcznie ze szczegółów wizyty. Kontynuować?',
      confirmText: 'Zastosuj',
    });
    if (!ok) return;

    setApplying(true);
    setStatusMsg({ text: 'Usuwam duplikaty...', level: 'info' });
    try {
      const data = await dataImportApi.conflictScanApply(scannedRange.date_start, scannedRange.date_end);
      setStatusMsg({
        text: `Usunięto ${data.removed_count} nadpisanych wizyt w ${data.group_count} grupach (${data.cancelled_count} anulowanych, ${data.soft_deleted_count} ukrytych).`,
        level: 'success',
      });
      await runScan();
    } catch (err) {
      setStatusMsg({ text: err instanceof ApiError ? err.message : 'Błąd usuwania duplikatów.', level: 'error' });
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="di-card">
      <h2 className="di-card-title" style={{ marginBottom: '0.25rem' }}>
        Skan konfliktów wizyt
      </h2>
      <p className="di-scan-description">
        Znajduje wizyty zdublowane przez przekładanie terminu (w caldis.pl lub ręcznie): (1) ten sam klient/pracownik/usługa z nakładającymi się terminami, (2) ta sama usługa u innego fryzjera
        tego samego dnia. W każdej grupie wizyta o najwyższym numerze jest uznawana za ostateczną — reszta zostaje usunięta (odwracalnie): nadchodzące wizyty są anulowane, a wizyty, które już się
        odbyły, są ukrywane.
      </p>

      <div className="di-form-grid">
        <div>
          <label className="field-label" htmlFor="scan-date-start">
            Data od
          </label>
          <input id="scan-date-start" type="date" className="field-input" value={dateStart} onChange={(e) => setDateStart(e.target.value)} />
        </div>
        <div>
          <label className="field-label" htmlFor="scan-date-end">
            Data do
          </label>
          <input id="scan-date-end" type="date" className="field-input" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} />
        </div>
      </div>

      <div className="di-import-actions">
        <Button variant="secondary" icon="search" isLoading={scanning} loadingText="Skanuję…" onClick={runScan}>
          Skanuj
        </Button>
        {groups && groups.length > 0 && (
          <Button variant="danger" icon="delete" isLoading={applying} loadingText="Usuwam…" onClick={applyScan}>
            Zastosuj (usuń duplikaty)
          </Button>
        )}
        {statusMsg && <span className={`di-status-msg di-status-${statusMsg.level}`}>{statusMsg.text}</span>}
      </div>

      {groups && summary && (
        <div className="di-scan-results">
          <p className="di-scan-summary">
            Sprawdzono {summary.candidateCount} wizyt. Znaleziono {summary.groupCount} grup konfliktów ({summary.supersededCount} wizyt zostałoby usuniętych jako nadpisane).
          </p>
          {groups.map((g, gi) => (
            <div key={gi} className="di-scan-group">
              <div className="di-scan-group-header">
                <div className="di-scan-group-title">
                  {g.client_name} — {g.service_name}
                </div>
                <div className="di-scan-badges">
                  {g.reasons.map((r) => (
                    <span key={r} className="di-reason-badge">
                      {REASON_LABELS[r] ?? r}
                    </span>
                  ))}
                </div>
              </div>
              <div className="table-container">
                <table className="refined-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Data</th>
                      <th>Godz.</th>
                      <th>Pracownik</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Cena</th>
                      <th style={{ textAlign: 'right' }}>Wynik</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.appointments.map((a) => (
                      <tr key={a.id} style={a.is_keeper ? undefined : { opacity: 0.6, textDecoration: 'line-through' }}>
                        <td>#{a.id}</td>
                        <td>{a.appointment_date}</td>
                        <td>
                          {a.start_time}–{a.end_time}
                        </td>
                        <td>{a.employee_name}</td>
                        <td>{a.status}</td>
                        <td style={{ textAlign: 'right' }}>{a.total_price} zł</td>
                        <td style={{ textAlign: 'right' }}>
                          {a.is_keeper ? (
                            <span className="di-tag-keeper">Zachowana (ostatnia)</span>
                          ) : (
                            <span className="di-tag-superseded">{a.planned_action === 'cancel' ? 'Nadpisana — zostanie anulowana' : 'Nadpisana — zostanie ukryta'}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
