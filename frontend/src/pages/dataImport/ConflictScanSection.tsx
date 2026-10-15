import { useState } from 'react';
import type { CSSProperties } from 'react';
import { dataImportApi } from '../../lib/api/dataImport';
import { ApiError } from '../../lib/api/client';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button } from '../../components/ui/Button';
import { DatePickerField } from '../../components/ui/form';
import { formatDay, todayISO } from './dataImportShared';
import type { ConflictGroup, ConflictReason } from '../../types/dataImport';

const REASON_LABELS: Record<ConflictReason, string> = {
  time_overlap: 'Nakładający się termin',
  same_day_different_stylist: 'Ten sam dzień, inny fryzjer',
};

type Msg = { text: string; level: 'info' | 'error' | 'success' };

/** Visit conflict scan — finds appointments duplicated by a reschedule (in
 * caldis.pl or manually): (1) same client/employee/service with overlapping
 * times, (2) same service with a different stylist on the same day. Read-only
 * scan + a destructive (but individually-reversible) apply step. */
export function ConflictScanSection({ style }: { style?: CSSProperties }) {
  const confirm = useConfirm();

  const [dateStart, setDateStart] = useState(todayISO(-90));
  const [dateEnd, setDateEnd] = useState(todayISO(90));
  const [scanning, setScanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [statusMsg, setStatusMsg] = useState<Msg | null>(null);
  const [summary, setSummary] = useState<{ candidateCount: number; groupCount: number; supersededCount: number } | null>(null);
  const [groups, setGroups] = useState<ConflictGroup[] | null>(null);
  const [scannedRange, setScannedRange] = useState<{ date_start: string; date_end: string } | null>(null);

  async function runScan() {
    if (!dateStart || !dateEnd) return setStatusMsg({ text: 'Wybierz zakres dat.', level: 'error' });
    if (dateStart > dateEnd) return setStatusMsg({ text: 'Data „od” musi być wcześniejsza niż data „do”.', level: 'error' });

    setScanning(true);
    setStatusMsg(null);
    setGroups(null);
    try {
      const data = await dataImportApi.conflictScan(dateStart, dateEnd);
      setScannedRange({ date_start: dateStart, date_end: dateEnd });
      setSummary({ candidateCount: data.candidate_count, groupCount: data.group_count, supersededCount: data.superseded_count });
      setGroups(data.groups);
      setStatusMsg(data.group_count > 0 ? { text: 'Skan zakończony — sprawdź grupy poniżej.', level: 'info' } : { text: 'Skan zakończony — brak konfliktów.', level: 'success' });
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
    setStatusMsg(null);
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
    <section className="form-card di-card di-rise" style={style} aria-labelledby="di-scan-title">
      <div className="di-card-head">
        <h2 id="di-scan-title" className="di-card-title">
          Skan konfliktów wizyt
        </h2>
      </div>
      <p className="di-muted-copy di-scan-description">
        Szuka wizyt zdublowanych przez przełożenie terminu (w caldis.pl lub ręcznie): ten sam klient, pracownik i usługa w nakładających się godzinach albo ta sama usługa u innego fryzjera tego
        samego dnia. W każdej grupie ostateczna jest wizyta o najwyższym numerze — pozostałe zostają usunięte odwracalnie: nadchodzące anulowane, odbyte ukryte.
      </p>

      <div className="form-grid di-dates">
        <DatePickerField label="Data od" id="di-scan-start" value={dateStart} onChange={setDateStart} />
        <DatePickerField label="Data do" id="di-scan-end" value={dateEnd} onChange={setDateEnd} />
      </div>

      <div className="di-form-actions">
        <Button variant="secondary" icon="search" isLoading={scanning} loadingText="Skanuję…" onClick={runScan}>
          Skanuj
        </Button>
        {groups && groups.length > 0 && (
          <Button variant="danger" icon="delete_sweep" isLoading={applying} loadingText="Usuwam…" onClick={applyScan}>
            Usuń duplikaty
          </Button>
        )}
        {statusMsg && (
          <p key={statusMsg.text} className="di-status-msg di-pop" data-level={statusMsg.level} role={statusMsg.level === 'error' ? 'alert' : 'status'}>
            {statusMsg.text}
          </p>
        )}
      </div>

      {groups && summary && (
        <div className="di-scan-results animate-fade-in">
          <p className="di-muted-copy">
            Sprawdzono <strong>{summary.candidateCount}</strong> wizyt · <strong>{summary.groupCount}</strong> grup konfliktów · <strong>{summary.supersededCount}</strong> wizyt do usunięcia
          </p>
          {groups.map((g, gi) => (
            <article key={gi} className="di-scan-group" style={{ '--i': Math.min(gi, 10) } as CSSProperties}>
              <header className="di-scan-group-head">
                <h3 className="di-scan-group-title">
                  {g.client_name} <span className="di-cell-sub">· {g.service_name}</span>
                </h3>
                <div className="di-scan-badges">
                  {g.reasons.map((r) => (
                    <span key={r} className="di-tag">
                      {REASON_LABELS[r] ?? r}
                    </span>
                  ))}
                </div>
              </header>
              <div className="table-container">
                <table className="refined-table">
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Data</th>
                      <th scope="col">Godz.</th>
                      <th scope="col">Pracownik</th>
                      <th scope="col">Status</th>
                      <th scope="col" className="di-num">
                        Cena
                      </th>
                      <th scope="col" className="di-num">
                        Wynik
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.appointments.map((a) => (
                      <tr key={a.id} className={a.is_keeper ? undefined : 'di-superseded'}>
                        <td>#{a.id}</td>
                        <td>{formatDay(a.appointment_date)}</td>
                        <td>
                          {a.start_time}–{a.end_time}
                        </td>
                        <td>{a.employee_name}</td>
                        <td>{a.status}</td>
                        <td className="di-num">{a.total_price} zł</td>
                        <td className="di-num">
                          {a.is_keeper ? (
                            <span className="di-pill" data-tone="ok">
                              Zostaje
                            </span>
                          ) : (
                            <span className="di-pill" data-tone="bad">
                              {a.planned_action === 'cancel' ? 'Do anulowania' : 'Do ukrycia'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
