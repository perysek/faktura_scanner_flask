import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@shared/contexts/AuthContext';
import { AuthLayout } from '@shared/pages/auth/AuthLayout';
import { Button } from '@shared/components/ui/Button';

/** The salon app's own login (same accounts, same Flask session), restyled 1:1 from
 * frontend/src/pages/auth/Login.tsx — only the copy says where you are. */
export function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const next = (location.state as { next?: string } | null)?.next;
  if (!auth.isLoading && auth.user) return <Navigate to={next && next !== '/login' ? next : '/'} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const result = await auth.login(email, password, remember);
    setBusy(false);
    if (!result.success) setError(result.error ?? 'Nieprawidłowy email lub hasło');
  }

  return (
    <AuthLayout>
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h1 className="refined-title">Zgłoszenia</h1>
        <p className="refined-subtitle">Panel obsługi · problemy i pomysły użytkowników</p>
      </div>

      {error && (
        <div className="flash-message flash-error" role="alert">
          {error}
        </div>
      )}

      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div>
          <label htmlFor="email" className="refined-label">
            Adres email
          </label>
          <input
            id="email"
            type="email"
            className="refined-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            autoComplete="email"
            placeholder="twoj@email.pl"
          />
        </div>
        <div>
          <label htmlFor="password" className="refined-label">
            Hasło
          </label>
          <input
            id="password"
            type="password"
            className="refined-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            placeholder="••••••••"
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input id="remember" type="checkbox" className="refined-checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          <label htmlFor="remember" className="checkbox-label">
            Zapamiętaj mnie
          </label>
        </div>
        <Button type="submit" variant="brand" isLoading={busy} loadingText="Logowanie…" style={{ width: '100%' }}>
          Zaloguj się
        </Button>
      </form>
    </AuthLayout>
  );
}
