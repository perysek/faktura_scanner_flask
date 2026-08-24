import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import './RbacPages.css';
import { useApiData } from '../../lib/useApiData';
import { usersApi } from '../../lib/api/users';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import type { UserListRow } from '../../types/rbac';

function formatLastLogin(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** Użytkownicy — lista kont systemowych. Ported from templates/users/list.html.
 * Superuser-only "Resetuj hasło" quick-action kept as a Modal (matches the
 * original's dedicated reset panel); role/delete rules mirror the backend's
 * own guards 1:1 (non-superuser can't touch superuser accounts, nobody can
 * delete themselves). */
export function UsersListPage() {
  const auth = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const usersState = useApiData(() => usersApi.list(), []);
  const [search, setSearch] = useState('');

  const [resetTarget, setResetTarget] = useState<UserListRow | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetting, setResetting] = useState(false);

  const isSuperuser = auth.user?.role === 'superuser';
  const currentUserId = auth.user?.id;

  const filtered = useMemo(() => {
    const users = usersState.data ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter((u) => u.full_name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q) || u.role.toLowerCase().includes(q));
  }, [usersState.data, search]);

  function openReset(u: UserListRow) {
    setResetTarget(u);
    setNewPassword('');
    setConfirmPassword('');
    setResetError('');
  }

  async function handleResetSubmit() {
    if (!resetTarget) return;
    setResetError('');
    if (!newPassword) {
      setResetError('Podaj nowe hasło.');
      return;
    }
    if (newPassword.length < 8) {
      setResetError('Hasło musi mieć co najmniej 8 znaków.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setResetError('Hasła nie pasują do siebie.');
      return;
    }
    setResetting(true);
    try {
      await usersApi.changePassword(resetTarget.id, newPassword);
      toast.success('Hasło zostało zmienione.');
      setResetTarget(null);
    } catch (err) {
      setResetError(err instanceof ApiError ? err.message : 'Błąd połączenia z serwerem.');
    } finally {
      setResetting(false);
    }
  }

  async function handleDelete(u: UserListRow) {
    const ok = await confirm({
      title: 'Kasujemy człowieka?',
      message: `Skasować konto ${u.full_name}? Zniknie bez śladu, jak kawa o 15:00.`,
      confirmText: 'Kasuj',
    });
    if (!ok) return;
    try {
      await usersApi.delete(u.id);
      toast.success('Użytkownik wykasowany. Konto poszło w niebyt.');
      usersState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania użytkownika');
    }
  }

  return (
    <div className="refined-page rbac-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Użytkownicy</h1>
          <p className="page-subtitle">Zarządzanie kontami użytkowników systemu</p>
        </div>
        <div className="rbac-header-actions">
          <input type="text" className="search-input" placeholder="Szukaj użytkownika…" value={search} onChange={(e) => setSearch(e.target.value)} />
          <Link to="/uzytkownicy/nowy" className="refined-btn-primary btn-press">
            <Icon name="add" /> Nowy użytkownik
          </Link>
        </div>
      </header>

      <div className="refined-card">
        {usersState.loading ? (
          <div className="rbac-empty-state">Ładowanie…</div>
        ) : filtered.length === 0 ? (
          <div className="rbac-empty-state">Brak użytkowników.</div>
        ) : (
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                <th>Imię i nazwisko</th>
                <th>Email</th>
                <th>Rola</th>
                <th>Pracownik</th>
                <th>Status</th>
                <th>Ostatnie logowanie</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => {
                const isSelf = u.id === currentUserId;
                const canDelete = !isSelf && (isSuperuser || u.role !== 'superuser');
                return (
                  <tr key={u.id}>
                    <td className="cell-name" style={{ fontWeight: 500 }}>
                      {u.full_name}
                    </td>
                    <td data-label="Email" style={{ color: 'var(--color-ink-muted)' }}>
                      {u.email}
                    </td>
                    <td data-label="Rola">
                      <span className={`badge ${u.role === 'superuser' ? 'badge-superuser' : 'badge-role'}`}>{u.role}</span>
                    </td>
                    <td data-label="Pracownik">{u.employee_name || <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>}</td>
                    <td data-label="Status">
                      <span className={`badge ${u.is_active ? 'badge-active' : 'badge-inactive'}`}>{u.is_active ? 'Aktywny' : 'Nieaktywny'}</span>
                    </td>
                    <td data-label="Ostatnie logowanie" style={{ color: 'var(--color-ink-muted)' }}>
                      {formatLastLogin(u.last_login)}
                    </td>
                    <td className="cell-actions" style={{ whiteSpace: 'nowrap' }}>
                      <div className="rbac-row-actions">
                        <Link to={`/uzytkownicy/${u.id}/edytuj`} className="refined-btn-ghost btn-press">
                          Edytuj
                        </Link>
                        {isSuperuser && (
                          <button type="button" className="refined-btn-ghost btn-reset btn-press" onClick={() => openReset(u)}>
                            Resetuj hasło
                          </button>
                        )}
                        {canDelete && (
                          <button type="button" className="action-icon-btn" title="Usuń użytkownika" aria-label="Usuń" onClick={() => handleDelete(u)}>
                            <Icon name="delete" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <Modal isOpen={resetTarget !== null} onClose={() => setResetTarget(null)} title="Resetuj hasło">
        <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-muted)', marginBottom: '0.75rem' }}>{resetTarget?.full_name}</p>
        {resetError && <div className="rbac-error-msg">{resetError}</div>}
        <div className="field-group">
          <label className="field-label" htmlFor="reset-pw-new">
            Nowe hasło
          </label>
          <input id="reset-pw-new" type="password" className="field-input" placeholder="Minimum 8 znaków" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoFocus />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="reset-pw-confirm">
            Potwierdź hasło
          </label>
          <input id="reset-pw-confirm" type="password" className="field-input" placeholder="Powtórz nowe hasło" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
        </div>
        <div className="form-actions">
          <Button variant="primary" isLoading={resetting} loadingText="Zapisywanie…" onClick={handleResetSubmit}>
            Zapisz hasło
          </Button>
          <Button variant="secondary" onClick={() => setResetTarget(null)}>
            Anuluj
          </Button>
        </div>
      </Modal>
    </div>
  );
}
