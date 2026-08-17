import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/ui/Button';
import { AuthLayout } from './AuthLayout';

interface FlashState {
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

interface LocationState {
  next?: string;
  flash?: FlashState;
}

/**
 * Login screen — DESIGN.md §15.2. The one place `variant="brand"` is used
 * (§15.5) — implementation-log.md Decision D12.
 */
export function Login() {
  const auth = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const state = location.state as LocationState | null;
  const next = state?.next;
  const flash = state?.flash;

  // Already authenticated → redirect away immediately (§15.2 point 4).
  if (!auth.isLoading && auth.user) {
    return <Navigate to={next || '/'} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const result = await auth.login(email, password, remember);
    setIsSubmitting(false);
    if (!result.success) {
      setError(result.error ?? 'Nieprawidłowy email lub hasło');
    }
    // On success, the redirect above fires on the next render once
    // auth.user is hydrated.
  }

  return (
    <AuthLayout>
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <h1 className="refined-title">Beauty Salon</h1>
        <p className="refined-subtitle">Management System</p>
      </div>

      {!error && flash && (
        <div className={`flash-message flash-${flash.type}`} role="status">
          {flash.message}
        </div>
      )}

      {error && (
        <div className="flash-message flash-error" role="alert">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div>
          <label htmlFor="email" className="refined-label">
            Adres email
          </label>
          <input
            type="email"
            id="email"
            name="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            autoComplete="email"
            className="refined-input"
            placeholder="twoj@email.pl"
          />
        </div>

        <div>
          <label htmlFor="password" className="refined-label">
            Hasło
          </label>
          <input
            type="password"
            id="password"
            name="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="refined-input"
            placeholder="••••••••"
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input
            type="checkbox"
            id="remember"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="refined-checkbox"
          />
          <label htmlFor="remember" className="checkbox-label">
            Zapamiętaj mnie
          </label>
        </div>

        <Button type="submit" variant="brand" isLoading={isSubmitting} loadingText="Logowanie…" style={{ width: '100%' }}>
          Zaloguj się
        </Button>
      </form>

      <div style={{ textAlign: 'center', marginTop: '0.75rem' }}>
        <Link to="/forgot-password" style={{ fontSize: '0.75rem', color: 'var(--color-ink-subtle)', textDecoration: 'none' }}>
          Zapomniałem hasła
        </Link>
      </div>
    </AuthLayout>
  );
}
