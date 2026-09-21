import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import './RbacPages.css';
import { useApiData } from '../../lib/useApiData';
import { usersApi } from '../../lib/api/users';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import { Button, ButtonLink } from '../../components/ui/Button';
import { FormCard } from '../../components/ui/form';
import { ModuleChips } from './ModuleChips';
import { ResetPasswordDialog } from './ResetPasswordDialog';
import { Avatar, EmptyNotice, ErrorNotice, RoleBadge, StatusBadge } from './RbacBits';
import { canRemoveUser, canResetPassword, formatDateTime } from './rbacRules';

/** Użytkownik — read-only account view (new in the SPA; the Jinja app only had
 * list + edit). Shows who the account is, which employee it belongs to and what
 * its role can reach. Actions are gated by rbacRules.ts; the API independently
 * refuses everything the UI doesn't offer (incl. an admin opening an owner account). */
export function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const auth = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const state = useApiData(() => usersApi.get(userId), [userId]);
  const [resetOpen, setResetOpen] = useState(false);
  useEscapeBack('/uzytkownicy');

  if (state.loading) {
    return (
      <div className="refined-page rbac-page">
        <EmptyNotice>Ładowanie…</EmptyNotice>
      </div>
    );
  }
  if (state.error || !state.data?.user) {
    const forbidden = state.error instanceof ApiError && state.error.status === 403;
    return (
      <div className="refined-page rbac-page">
        <ErrorNotice message={forbidden ? 'Brak uprawnień do tego konta.' : 'Nie udało się wczytać użytkownika.'} onRetry={forbidden ? undefined : state.reload} />
        <p style={{ textAlign: 'center' }}>
          <Link to="/uzytkownicy">← Wróć do listy użytkowników</Link>
        </p>
      </div>
    );
  }

  const { user, linked_employee: employee, permissions, module_display_names: names } = state.data;
  const actor = auth.user;
  const isSelf = actor?.id === user.id;
  const canRemove = canRemoveUser(actor, user);
  const canReset = canResetPassword(actor, user);

  async function handleDelete() {
    const ok = await confirm({
      title: 'Kasujemy człowieka?',
      message: `Skasować konto ${user.full_name}? Zniknie bez śladu, jak kawa o 15:00.`,
      confirmText: 'Kasuj',
    });
    if (!ok) return;
    try {
      await usersApi.delete(user.id);
      toast.success('Użytkownik wykasowany. Konto poszło w niebyt.');
      navigate('/uzytkownicy');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania użytkownika');
    }
  }

  async function handleToggleActive() {
    if (user.is_active) {
      const ok = await confirm({
        title: 'Dezaktywować konto?',
        message: `${user.full_name} nie będzie mógł się zalogować, dopóki konto nie zostanie ponownie aktywowane.`,
        confirmText: 'Dezaktywuj',
      });
      if (!ok) return;
    }
    try {
      const res = await usersApi.toggleActive(user.id);
      toast.success(res.is_active ? 'Konto aktywowane.' : 'Konto dezaktywowane.');
      state.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zmienić statusu konta');
    }
  }

  const toggleLabel = user.is_active ? 'Dezaktywuj konto' : 'Aktywuj konto';

  return (
    <div className="refined-page rbac-page rbac-detail-page animate-fade-up">
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
          <ButtonLink to={`/uzytkownicy/${user.id}/edytuj`} variant="primary" icon="edit">
            Edytuj
          </ButtonLink>
          {canReset && (
            <Button variant="secondary" onClick={() => setResetOpen(true)}>
              Resetuj hasło
            </Button>
          )}
          {canRemove && (
            <Button variant="secondary" onClick={handleToggleActive}>
              {toggleLabel}
            </Button>
          )}
          {canRemove && (
            <Button variant="danger" icon="delete" onClick={handleDelete}>
              Usuń
            </Button>
          )}
        </div>
      </header>

      {isSelf && (
        <p className="rbac-note">
          To Twoje konto. Nie możesz zmienić własnej roli ani go dezaktywować — hasło zmienisz w <Link to="/profil">Profilu</Link>.
        </p>
      )}

      <div className="rbac-detail-grid">
        <FormCard>
          <h2 className="rbac-card-title">Konto</h2>
          <dl className="rbac-dl">
            <div>
              <dt>Rola</dt>
              <dd>
                <RoleBadge role={user.role} label={user.role_display_name} />
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <StatusBadge active={user.is_active} />
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
          <h2 className="rbac-card-title">Powiązany pracownik</h2>
          {employee ? (
            <>
              <p className="rbac-strong">
                {employee.first_name} {employee.last_name}
              </p>
              {auth.hasModuleAccess('employees') && (
                <p style={{ marginTop: '0.5rem' }}>
                  <Link to={`/pracownicy/${employee.id}`}>Otwórz kartę pracownika →</Link>
                </p>
              )}
            </>
          ) : (
            <p className="rbac-muted">
              To konto nie jest powiązane z żadnym pracownikiem. <Link to={`/uzytkownicy/${user.id}/edytuj`}>Powiąż w edycji</Link>.
            </p>
          )}
        </FormCard>

        <div className="rbac-detail-wide">
          <FormCard>
            <h2 className="rbac-card-title">Co może ta rola</h2>
            <ModuleChips permissions={permissions} names={names} />
            {auth.user?.role === 'superuser' && (
              <p className="rbac-muted" style={{ marginTop: '1rem' }}>
                Uprawnienia zmienisz w <Link to="/poziomy-dostepu">Poziomach dostępu</Link> — dotyczą wszystkich kont z tą rolą.
              </p>
            )}
          </FormCard>
        </div>
      </div>

      <div className="rbac-mobile-only">
        {(canReset || canRemove) && (
          <FormCard>
            <h2 className="rbac-card-title">Więcej działań</h2>
            <div className="rbac-stack">
              {canReset && (
                <Button variant="secondary" onClick={() => setResetOpen(true)}>
                  Resetuj hasło
                </Button>
              )}
              {canRemove && (
                <Button variant="secondary" onClick={handleToggleActive}>
                  {toggleLabel}
                </Button>
              )}
            </div>
          </FormCard>
        )}
        {canRemove && (
          <FormCard>
            <h2 className="rbac-card-title rbac-card-title--danger">Strefa ryzyka</h2>
            <p className="rbac-muted" style={{ marginBottom: '0.75rem' }}>
              Usunięcie konta jest nieodwracalne.
            </p>
            <Button variant="danger" icon="delete" onClick={handleDelete}>
              Usuń konto
            </Button>
          </FormCard>
        )}
        <div className="rbac-mobile-cta">
          <ButtonLink to={`/uzytkownicy/${user.id}/edytuj`} variant="primary" icon="edit">
            Edytuj
          </ButtonLink>
        </div>
      </div>

      <ResetPasswordDialog target={resetOpen ? { id: user.id, full_name: user.full_name } : null} onClose={() => setResetOpen(false)} />
    </div>
  );
}
