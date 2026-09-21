import { useMemo, useState } from 'react';
import type { MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './RbacPages.css';
import { useApiData } from '../../lib/useApiData';
import { usersApi } from '../../lib/api/users';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Modal } from '../../components/ui/Modal';
import { ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { ResetPasswordDialog } from './ResetPasswordDialog';
import { Avatar, EmptyNotice, ErrorNotice, RoleBadge, StatusBadge } from './RbacBits';
import { canManageUser, canRemoveUser, canResetPassword, formatDateTime } from './rbacRules';
import type { UserListRow } from '../../types/rbac';

const stop = (e: MouseEvent) => e.stopPropagation();

/** Użytkownicy — lista kont systemowych. Desktop: table, click a row to open the
 * account. Phone (≤640px): a card list — tap opens the account, ⋯ opens a bottom
 * action sheet with the same actions the desktop row has, "Nowy użytkownik" sits
 * in a sticky bar at the bottom (thumb zone). Who may do what comes from
 * rbacRules.ts, which mirrors the backend's own refusals. */
export function UsersListPage() {
  const auth = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const usersState = useApiData(() => usersApi.list(), []);
  const [search, setSearch] = useState('');
  const [resetTarget, setResetTarget] = useState<UserListRow | null>(null);
  const [sheetTarget, setSheetTarget] = useState<UserListRow | null>(null);

  const actor = auth.user;
  const allUsers = useMemo(() => usersState.data ?? [], [usersState.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allUsers;
    return allUsers.filter((u) =>
      [u.full_name, u.email, u.role, u.role_display_name, u.employee_name ?? ''].some((field) => field.toLowerCase().includes(q)),
    );
  }, [allUsers, search]);

  async function handleDelete(u: UserListRow) {
    setSheetTarget(null);
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

  async function handleToggleActive(u: UserListRow) {
    setSheetTarget(null);
    if (u.is_active) {
      const ok = await confirm({
        title: 'Dezaktywować konto?',
        message: `${u.full_name} nie będzie mógł się zalogować, dopóki konto nie zostanie ponownie aktywowane.`,
        confirmText: 'Dezaktywuj',
      });
      if (!ok) return;
    }
    try {
      const res = await usersApi.toggleActive(u.id);
      toast.success(res.is_active ? 'Konto aktywowane.' : 'Konto dezaktywowane.');
      usersState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zmienić statusu konta');
    }
  }

  function openReset(u: UserListRow) {
    setSheetTarget(null);
    setResetTarget(u);
  }

  const sheet = sheetTarget;

  return (
    <div className="refined-page rbac-page rbac-list-page animate-fade-up">
      <header className="page-header rbac-page-header">
        <div>
          <h1 className="page-title">Użytkownicy</h1>
          <p className="page-subtitle">Zarządzanie kontami użytkowników systemu</p>
        </div>
        <div className="page-header-actions rbac-desktop-only">
          <ButtonLink to="/uzytkownicy/nowy" variant="primary" icon="add">
            Nowy użytkownik
          </ButtonLink>
        </div>
      </header>

      <div className="rbac-toolbar">
        <div className="rbac-search">
          <Icon name="search" />
          <input
            type="search"
            className="form-input"
            placeholder="Szukaj: imię, email, rola…"
            aria-label="Szukaj użytkownika"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {!usersState.loading && !usersState.error && (
          <span className="rbac-count" aria-live="polite">
            {filtered.length === allUsers.length ? `${allUsers.length} kont` : `${filtered.length} z ${allUsers.length}`}
          </span>
        )}
      </div>

      {usersState.loading ? (
        <EmptyNotice>Ładowanie…</EmptyNotice>
      ) : usersState.error ? (
        <ErrorNotice message="Nie udało się wczytać użytkowników." onRetry={usersState.reload} />
      ) : filtered.length === 0 ? (
        <EmptyNotice>{allUsers.length === 0 ? 'Brak użytkowników.' : 'Nikt nie pasuje do wyszukiwania.'}</EmptyNotice>
      ) : (
        <>
          <div className="form-card rbac-desktop-only">
            <div className="table-container">
              <table className="refined-table">
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
                    const manageable = canManageUser(actor, u);
                    return (
                      <tr key={u.id} className={manageable ? 'row-clickable' : undefined} onClick={manageable ? () => navigate(`/uzytkownicy/${u.id}`) : undefined}>
                        <td className="cell-name" style={{ fontWeight: 500 }}>
                          {manageable ? (
                            <Link to={`/uzytkownicy/${u.id}`} className="rbac-name-link" onClick={stop}>
                              {u.full_name}
                            </Link>
                          ) : (
                            u.full_name
                          )}
                        </td>
                        <td style={{ color: 'var(--color-ink-muted)' }}>{u.email}</td>
                        <td>
                          <RoleBadge role={u.role} label={u.role_display_name} />
                        </td>
                        <td>{u.employee_name || <span className="rbac-muted">—</span>}</td>
                        <td>
                          <StatusBadge active={u.is_active} />
                        </td>
                        <td style={{ color: 'var(--color-ink-muted)' }}>{formatDateTime(u.last_login)}</td>
                        <td className="cell-actions">
                          {manageable ? (
                            <div className="rbac-row-actions" onClick={stop}>
                              <ButtonLink to={`/uzytkownicy/${u.id}/edytuj`} variant="ghost">
                                Edytuj
                              </ButtonLink>
                              {canResetPassword(actor, u) && (
                                <button type="button" className="refined-btn-ghost btn-press btn-reset" onClick={() => openReset(u)}>
                                  Resetuj hasło
                                </button>
                              )}
                              {canRemoveUser(actor, u) && (
                                <button type="button" className="action-icon-btn danger" title="Usuń użytkownika" aria-label={`Usuń: ${u.full_name}`} onClick={() => handleDelete(u)}>
                                  <Icon name="delete" />
                                </button>
                              )}
                            </div>
                          ) : (
                            <span className="rbac-muted" title="Kontem właściciela zarządza tylko właściciel">
                              konto właściciela
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <ul className="user-cards rbac-mobile-only">
            {filtered.map((u) => {
              const manageable = canManageUser(actor, u);
              const body = (
                <>
                  <Avatar name={u.full_name} />
                  <span className="user-card-text">
                    <span className="user-card-name">{u.full_name}</span>
                    <span className="user-card-sub">{u.email}</span>
                    <span className="user-card-meta">
                      <RoleBadge role={u.role} label={u.role_display_name} />
                      <StatusBadge active={u.is_active} />
                    </span>
                    {u.employee_name && <span className="user-card-sub">Pracownik: {u.employee_name}</span>}
                    {!manageable && <span className="user-card-sub">Kontem właściciela zarządza tylko właściciel</span>}
                  </span>
                </>
              );
              return (
                <li key={u.id} className="user-card">
                  {manageable ? (
                    <Link to={`/uzytkownicy/${u.id}`} className="user-card-main">
                      {body}
                    </Link>
                  ) : (
                    <div className="user-card-main user-card-main--static">{body}</div>
                  )}
                  {manageable && (
                    <button type="button" className="user-card-more" aria-label={`Akcje: ${u.full_name}`} onClick={() => setSheetTarget(u)}>
                      <Icon name="more_horiz" />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}

      <div className="rbac-mobile-cta rbac-mobile-only">
        <ButtonLink to="/uzytkownicy/nowy" variant="primary" icon="add">
          Nowy użytkownik
        </ButtonLink>
      </div>

      <Modal isOpen={sheet !== null} onClose={() => setSheetTarget(null)} title={sheet?.full_name ?? ''} variant="sheet">
        {sheet && (
          <ul className="action-sheet">
            <li>
              <Link className="action-sheet-item" to={`/uzytkownicy/${sheet.id}`}>
                <Icon name="visibility" /> Zobacz szczegóły
              </Link>
            </li>
            <li>
              <Link className="action-sheet-item" to={`/uzytkownicy/${sheet.id}/edytuj`}>
                <Icon name="edit" /> Edytuj dane
              </Link>
            </li>
            {canResetPassword(actor, sheet) && (
              <li>
                <button type="button" className="action-sheet-item" onClick={() => openReset(sheet)}>
                  <Icon name="refresh" /> Resetuj hasło
                </button>
              </li>
            )}
            {canRemoveUser(actor, sheet) && (
              <li>
                <button type="button" className="action-sheet-item" onClick={() => handleToggleActive(sheet)}>
                  <Icon name={sheet.is_active ? 'person_off' : 'person'} /> {sheet.is_active ? 'Dezaktywuj konto' : 'Aktywuj konto'}
                </button>
              </li>
            )}
            {canRemoveUser(actor, sheet) && (
              <li className="action-sheet-danger">
                <button type="button" className="action-sheet-item" onClick={() => handleDelete(sheet)}>
                  <Icon name="delete" /> Usuń konto
                </button>
              </li>
            )}
          </ul>
        )}
      </Modal>

      <ResetPasswordDialog target={resetTarget} onClose={() => setResetTarget(null)} />
    </div>
  );
}
