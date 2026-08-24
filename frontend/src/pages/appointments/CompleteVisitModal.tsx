import { useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { SelectField, TextField } from '../../components/ui/form';
import { useToast } from '../../components/feedback/ToastProvider';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { formatPLN } from '../../lib/format';

export interface CompleteVisitModalProps {
  isOpen: boolean;
  onClose: () => void;
  appointmentId: number;
  onSuccess: () => void;
}

const PAYMENT_METHODS = [
  { value: 'gotówka', label: 'Gotówka' },
  { value: 'karta', label: 'Karta' },
  { value: 'przelew', label: 'Przelew' },
];

/** "Zamknij wizytę" — ported from view.html's `completeAppointment()`, which
 * used two chained native `prompt()` calls (payment method, then nothing for
 * discount — discount wasn't actually collected there despite the endpoint
 * accepting it). Replaced with a real form; discount added here since the
 * field already exists server-side and a blank prompt() was the only reason
 * it wasn't exposed, not a deliberate omission. */
export function CompleteVisitModal({ isOpen, onClose, appointmentId, onSuccess }: CompleteVisitModalProps) {
  const toast = useToast();
  const [paymentMethod, setPaymentMethod] = useState('gotówka');
  const [discount, setDiscount] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSubmit() {
    setSaving(true);
    try {
      const discountAmount = discount.trim() ? parseFloat(discount) : undefined;
      const result = (await appointmentsApi.complete(appointmentId, paymentMethod, discountAmount)) as { success: true; net_amount?: number; commission_total?: number };
      toast.success(
        result.net_amount !== undefined
          ? `Wizyta zamknięta. Przychód: ${formatPLN(result.net_amount)}, prowizja: ${formatPLN(result.commission_total ?? 0)}`
          : 'Wizyta zamknięta',
      );
      onClose();
      onSuccess();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zamykania wizyty');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Zamknij wizytę"
      footer={
        <>
          <Button variant="secondary" disabled={saving} onClick={onClose}>
            Anuluj
          </Button>
          <Button variant="primary" icon="check_circle" isLoading={saving} loadingText="Zamykanie…" onClick={handleSubmit}>
            Zamknij wizytę
          </Button>
        </>
      }
    >
      <SelectField label="Metoda płatności" options={PAYMENT_METHODS} value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)} />
      <TextField label="Rabat" type="number" step="0.01" min="0" placeholder="0.00" helper="Opcjonalny, w złotych" value={discount} onChange={(e) => setDiscount(e.target.value)} />
    </Modal>
  );
}
