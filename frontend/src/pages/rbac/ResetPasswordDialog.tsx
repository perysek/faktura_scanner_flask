import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { usersApi } from '../../lib/api/users';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { TextField } from '../../components/ui/form';

interface Props {
  target: { id: number; full_name: string } | null;
  onClose: () => void;
}

/** Owner-only password reset for another account. Bottom sheet on a phone,
 * centered dialog above 640px. The server refuses anything under 8 characters;
 * the checks here just save a round trip. */
export function ResetPasswordDialog({ target, onClose }: Props) {
  const toast = useToast();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!target) return;
    setPassword('');
    setConfirm('');
    setError('');
  }, [target]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!target) return;
    setError('');
    if (password.length < 8) {
      setError('Hasło musi mieć co najmniej 8 znaków.');
      return;
    }
    if (password !== confirm) {
      setError('Hasła nie pasują do siebie.');
      return;
    }
    setSaving(true);
    try {
      await usersApi.changePassword(target.id, password);
      toast.success('Hasło zostało zmienione.');
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Błąd połączenia z serwerem.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen={target !== null} onClose={onClose} title="Resetuj hasło" variant="sheet">
      <form onSubmit={handleSubmit}>
        <p className="rbac-muted" style={{ marginBottom: '1rem' }}>
          {target?.full_name}
        </p>
        {error && (
          <div className="rbac-error-msg" role="alert">
            {error}
          </div>
        )}
        <div className="rbac-stack">
          <TextField label="Nowe hasło" type="password" autoComplete="new-password" placeholder="Minimum 8 znaków" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
          <TextField label="Potwierdź hasło" type="password" autoComplete="new-password" placeholder="Powtórz nowe hasło" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <div className="form-actions">
          <Button type="submit" variant="primary" isLoading={saving} loadingText="Zapisywanie…">
            Zapisz hasło
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Anuluj
          </Button>
        </div>
      </form>
    </Modal>
  );
}
