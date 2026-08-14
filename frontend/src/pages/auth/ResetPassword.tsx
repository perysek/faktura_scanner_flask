import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import { Button } from '../../components/ui/Button';
import { AuthLayout } from './AuthLayout';

// Backend minimum (auth_service.py / routes/auth/routes.py) — kept in sync
// here per DESIGN.md §16 "Must" (implementation-log.md Decision D4).
const MIN_PASSWORD_LENGTH = 8;

/** Reset-password screen — DESIGN.md §15.3. Client-side validation is
 * defense-in-depth; the backend re-validates identically. On success the
 * user is redirected to /login and must log in fresh (a reset never
 * auto-logs-in). */
export function ResetPassword() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`Nowe hasło musi mieć minimum ${MIN_PASSWORD_LENGTH} znaków`);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Hasła nie są identyczne');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post(`/auth/reset-password/${token}`, {
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      navigate('/login', { state: { flash: { type: 'success', message: 'Hasło zostało zmienione. Zaloguj się nowym hasłem.' } } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <div style={{ marginBottom: '2rem' }}>
        <h1 className="refined-title refined-title-sm">Ustaw nowe hasło</h1>
        <p className="refined-subtitle">Wpisz nowe hasło do swojego konta</p>
      </div>

      {error && (
        <div className="flash-message flash-error" role="alert">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div>
          <label htmlFor="new_password" className="refined-label">
            Nowe hasło
          </label>
          <input
            type="password"
            id="new_password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
            autoComplete="new-password"
            className="refined-input"
            placeholder="••••••••"
          />
        </div>

        <div>
          <label htmlFor="confirm_password" className="refined-label">
            Potwierdź hasło
          </label>
          <input
            type="password"
            id="confirm_password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            autoComplete="new-password"
            className="refined-input"
            placeholder="••••••••"
          />
        </div>

        <Button type="submit" variant="primary" isLoading={isSubmitting} loadingText="Zapisywanie…" style={{ width: '100%' }}>
          Ustaw nowe hasło
        </Button>
      </form>

      <Link to="/forgot-password" className="back-link">
        ← Wróć do odzyskiwania hasła
      </Link>
    </AuthLayout>
  );
}
