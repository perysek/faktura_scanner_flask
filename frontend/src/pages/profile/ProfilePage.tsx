import { useState } from 'react';
import type { FormEvent } from 'react';
import '../rbac/RbacPages.css';
import { useApiData } from '../../lib/useApiData';
import { profileApi } from '../../lib/api/profile';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { FormCard, TextField } from '../../components/ui/form';
import { ModuleChips } from '../rbac/ModuleChips';
import { Avatar, EmptyNotice, ErrorNotice, RoleBadge, StatusBadge } from '../rbac/RbacBits';
import { employmentStatusLabel, formatDate, formatDateTime } from '../rbac/rbacRules';

/** Profil — "who am I and what may I do", for every signed-in role. Read-only
 * facts plus the one thing a user changes about themselves: their password.
 * Nothing financial is shown, not even the linked employee's own pay — the
 * endpoint (routes/auth/routes.py `_profile_payload`) never sends it. */
export function ProfilePage() {
  const auth = useAuth();
  const toast = useToast();
  const state = useApiData(() => profileApi.get(), []);

  const [pwOpen, setPwOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSaving, setPwSaving] = useState(false);

  if (state.loading) {
    return (
      <div className="refined-page rbac-page">
        <EmptyNotice>Ładowanie…</EmptyNotice>
      </div>
    );
  }
  if (state.error || !state.data?.user) {
    return (
      <div className="refined-page rbac-page">
        <ErrorNotice message="Nie udało się wczytać profilu." onRetry={state.reload} />
      </div>
    );
  }

  const { user, employee, permissions, module_display_names: names } = state.data;

  function closePasswordForm() {
    setPwOpen(false);
    setPwError('');
    setOldPassword('');
    setNewPassword('');
    setConfirmPassword('');
  }

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setPwError('');
    if (!oldPassword || !newPassword || !confirmPassword) {
      setPwError('Wypełnij wszystkie pola.');
      return;
    }
    if (newPassword.length < 8) {
      setPwError('Nowe hasło musi mieć minimum 8 znaków.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwError('Nowe hasła nie pasują do siebie.');
      return;
    }
    setPwSaving(true);
    try {
      await profileApi.changePassword({ old_password: oldPassword, new_password: newPassword, confirm_password: confirmPassword });
      toast.success('Hasło zostało zmienione.');
      closePasswordForm();
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : 'Błąd połączenia z serwerem.');
    } finally {
      setPwSaving(false);
    }
  }

  return (
    <div className="refined-page rbac-page profile-page animate-fade-up">
      <header className="page-header rbac-page-header">
        <div className="rbac-detail-heading">
          <Avatar name={user.full_name} size="lg" />
          <div>
            <h1 className="page-title">{user.full_name}</h1>
            <p className="page-subtitle">{user.email}</p>
            <div className="rbac-badge-row">
              <RoleBadge role={user.role} label={user.role_display_name} />
              <StatusBadge active={user.is_active} />
            </div>
          </div>
        </div>
        <div className="page-header-actions rbac-desktop-only">
          <ButtonLink to="/dashboard" variant="secondary">
            Powrót do pulpitu
          </ButtonLink>
          <Button variant="danger" onClick={() => auth.logout()}>
            Wyloguj się
          </Button>
        </div>
      </header>

      <div className="rbac-detail-grid">
        <FormCard>
          <h2 className="rbac-card-title">Informacje o koncie</h2>
          <dl className="rbac-dl">
            <div>
              <dt>Imię i nazwisko</dt>
              <dd>{user.full_name}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd className="rbac-break">{user.email}</dd>
            </div>
            <div>
              <dt>Rola</dt>
              <dd>
                <RoleBadge role={user.role} label={user.role_display_name} />
              </dd>
            </div>
            <div>
              <dt>Ostatnie logowanie</dt>
              <dd>{formatDateTime(user.last_login)}</dd>
            </div>
            <div>
              <dt>Konto utworzone</dt>
              <dd>{formatDateTime(user.created_at)}</dd>
            </div>
          </dl>
        </FormCard>

        <FormCard>
          <h2 className="rbac-card-title">Twój profil pracownika</h2>
          {employee ? (
            <dl className="rbac-dl">
              <div>
                <dt>Imię i nazwisko</dt>
                <dd>
                  {employee.first_name} {employee.last_name}
                </dd>
              </div>
              <div>
                <dt>Stanowisko</dt>
                <dd>{employee.position || '—'}</dd>
              </div>
              <div>
                <dt>Zatrudnienie</dt>
                <dd>{employmentStatusLabel(employee.employment_status)}</dd>
              </div>
              <div>
                <dt>Zatrudniony od</dt>
                <dd>{formatDate(employee.hire_date)}</dd>
              </div>
            </dl>
          ) : (
            <p className="rbac-muted">Twoje konto nie jest powiązane z profilem pracownika.</p>
          )}
        </FormCard>

        <div className="rbac-detail-wide">
          <FormCard>
            <h2 className="rbac-card-title">Twoje uprawnienia</h2>
            <ModuleChips permissions={permissions} names={names} emptyText="Twoja rola nie ma dostępu do żadnego modułu." />
          </FormCard>
        </div>

        <div className="rbac-detail-wide">
          <FormCard>
            <h2 className="rbac-card-title">Bezpieczeństwo</h2>
            {!pwOpen ? (
              <div className="profile-security">
                <p className="rbac-muted">Zmień hasło do swojego konta.</p>
                <Button variant="secondary" onClick={() => setPwOpen(true)}>
                  Zmień hasło
                </Button>
              </div>
            ) : (
              <form onSubmit={handlePasswordSubmit} className="profile-pw-form">
                {pwError && (
                  <div className="rbac-error-msg" role="alert">
                    {pwError}
                  </div>
                )}
                <div className="rbac-stack">
                  <TextField label="Obecne hasło" type="password" autoComplete="current-password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} autoFocus />
                  <TextField label="Nowe hasło" type="password" autoComplete="new-password" helper="Minimum 8 znaków" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                  <TextField label="Powtórz nowe hasło" type="password" autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
                </div>
                <div className="form-actions">
                  <Button type="submit" variant="primary" icon="save" isLoading={pwSaving} loadingText="Zapisywanie…">
                    Zapisz nowe hasło
                  </Button>
                  <Button variant="secondary" onClick={closePasswordForm}>
                    Anuluj
                  </Button>
                </div>
              </form>
            )}
          </FormCard>
        </div>
      </div>

      <div className="rbac-mobile-only profile-mobile-actions">
        <ButtonLink to="/dashboard" variant="secondary">
          Powrót do pulpitu
        </ButtonLink>
        <Button variant="danger" onClick={() => auth.logout()}>
          Wyloguj się
        </Button>
      </div>
    </div>
  );
}
