import { useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { useToast } from '../../components/feedback/ToastProvider';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { STATUS_LABELS, VALID_TRANSITIONS } from '../../types/appointment';
import type { AppointmentStatus } from '../../types/appointment';

export interface StatusChangeModalProps {
  isOpen: boolean;
  onClose: () => void;
  appointmentId: number;
  currentStatus: AppointmentStatus;
  /** Skip the status picker and go straight to the (optional) cancellation
   * reason step for this one status — used by WizytaDetailPage's per-status
   * action buttons, where the target status is already known from which
   * button was clicked. Omit to show the full picker (WizytyListPage's
   * clickable status badge). */
  fixedStatus?: AppointmentStatus;
  onSuccess: () => void;
}

/**
 * Status picker + optional cancellation-reason step, ported from
 * list.html's `#statusModal` (native `<input type=radio>` pills + reason
 * textarea, shown for `cancelled` only) and reused for view.html's
 * per-button `changeStatus()` (which used a native `prompt()` for the
 * reason — replaced here with this same modal instead, `prompt()` being
 * exactly the pattern DESIGN.md §16 forbids for `useConfirm`).
 */
export function StatusChangeModal({ isOpen, onClose, appointmentId, currentStatus, fixedStatus, onSuccess }: StatusChangeModalProps) {
  const toast = useToast();
  const options = fixedStatus ? [fixedStatus] : VALID_TRANSITIONS[currentStatus] ?? [];
  const [selected, setSelected] = useState<AppointmentStatus | null>(fixedStatus ?? (options.length === 1 ? options[0] : null));
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  function handleClose() {
    setReason('');
    setSelected(fixedStatus ?? null);
    onClose();
  }

  async function handleSubmit() {
    if (!selected) return;
    setSaving(true);
    try {
      const result = await appointmentsApi.updateStatus(appointmentId, selected, selected === 'cancelled' ? reason.trim() || undefined : undefined);
      if (result.success) {
        toast.success(`Status zmieniony na: ${STATUS_LABELS[selected]}`);
        handleClose();
        onSuccess();
      } else {
        toast.error('Nie udało się zmienić statusu');
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zmiany statusu');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Zmień status wizyty"
      footer={
        <>
          <Button variant="secondary" disabled={saving} onClick={handleClose}>
            Zamknij
          </Button>
          <Button variant="primary" disabled={!selected} isLoading={saving} loadingText="Zapisywanie…" onClick={handleSubmit}>
            Zapisz
          </Button>
        </>
      }
    >
      <p className="form-label">Aktualny status</p>
      <p style={{ marginBottom: '1rem' }}>
        <span className={`status-badge ${currentStatus}`}>{STATUS_LABELS[currentStatus]}</span>
      </p>

      {!fixedStatus && (
        <>
          <p className="form-label">Nowy status</p>
          <div className="modal-status-options">
            {options.length === 0 ? (
              <span className="empty-text">Brak dostępnych zmian statusu.</span>
            ) : (
              options.map((status) => (
                <button key={status} type="button" className={`status-option-btn${selected === status ? ' active' : ''}`} onClick={() => setSelected(status)}>
                  {STATUS_LABELS[status]}
                </button>
              ))
            )}
          </div>
        </>
      )}

      {selected === 'cancelled' && (
        <div className="modal-reason-wrap">
          <label htmlFor="cancellation-reason">Powód anulowania</label>
          <textarea id="cancellation-reason" placeholder="Opcjonalnie — wpisz powód anulowania..." value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
      )}
    </Modal>
  );
}
