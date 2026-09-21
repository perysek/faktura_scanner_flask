import { useState } from 'react';
import { Link } from 'react-router-dom';
import './RbacPages.css';
import { useApiData } from '../../lib/useApiData';
import { rolesApi } from '../../lib/api/roles';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Modal } from '../../components/ui/Modal';
import { ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { ModuleChips } from './ModuleChips';
import { EmptyNotice, ErrorNotice } from './RbacBits';
import { usersLabel } from './rbacRules';
import type { RoleListRow } from '../../types/rbac';

/** Why a role can't be deleted right now, or null when it can. The API refuses
 * both cases too — this just explains it instead of failing after the click. */
function deleteBlocker(role: RoleListRow): string | null {
  if (role.is_protected) return 'Rola systemowa — nie można jej usunąć.';
  if (role.user_count > 0) return `Ma przypisanych użytkowników (${role.user_count}) — najpierw zmień im rolę.`;
  return null;
}

/** Poziomy dostępu — lista ról. Desktop: table with a dot matrix of module
 * access and how many accounts hold each role. Phone (≤640px): a card per role
 * with the granted modules spelled out as chips, ⋯ for delete (with the reason
 * when it's blocked), "Nowa rola" in a sticky bar at the bottom. */
export function RolesListPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const rolesState = useApiData(() => rolesApi.list(), []);
  const [sheetRole, setSheetRole] = useState<RoleListRow | null>(null);
  const roles = rolesState.data?.roles ?? [];
  const names = rolesState.data?.module_display_names ?? {};

  async function handleDelete(role: RoleListRow) {
    setSheetRole(null);
    const blocker = deleteBlocker(role);
    if (blocker) {
      toast.error(blocker);
      return;
    }
    const ok = await confirm({
      title: 'Usuń rolę',
      message: `Usunąć rolę "${role.display_name}"? Tej operacji nie da się cofnąć.`,
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      await rolesApi.delete(role.id);
      toast.success('Rola usunięta');
      rolesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania roli');
    }
  }

  const sheetBlocker = sheetRole ? deleteBlocker(sheetRole) : null;

  return (
    <div className="refined-page rbac-page rbac-list-page animate-fade-up">
      <header className="page-header rbac-page-header">
        <div>
          <h1 className="page-title">Poziomy dostępu</h1>
          <p className="page-subtitle">Role i uprawnienia do modułów — kto co widzi i może zmieniać</p>
        </div>
        <div className="page-header-actions rbac-desktop-only">
          <ButtonLink to="/poziomy-dostepu/nowa" variant="primary" icon="add">
            Nowa rola
          </ButtonLink>
        </div>
      </header>

      {rolesState.loading ? (
        <EmptyNotice>Ładowanie…</EmptyNotice>
      ) : rolesState.error ? (
        <ErrorNotice message="Nie udało się wczytać ról." onRetry={rolesState.reload} />
      ) : roles.length === 0 ? (
        <EmptyNotice>Brak ról.</EmptyNotice>
      ) : (
        <>
          <div className="form-card rbac-desktop-only">
            <div className="dot-legend">
              <span className="dot-legend-item">
                <span className="module-dot module-dot-on" /> dozwolone
              </span>
              <span className="dot-legend-item">
                <span className="module-dot module-dot-off" /> brak dostępu
              </span>
            </div>
            <div className="table-container">
              <table className="refined-table">
                <thead>
                  <tr>
                    <th>Nazwa</th>
                    <th>Wyświetlana nazwa</th>
                    <th>Użytkownicy</th>
                    <th>Uprawnienia modułów</th>
                    <th>Typ</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {roles.map((r) => {
                    const blocker = deleteBlocker(r);
                    return (
                      <tr key={r.id}>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}>{r.name}</td>
                        <td className="cell-name" style={{ fontWeight: 500 }}>
                          {r.display_name}
                        </td>
                        <td>{r.user_count}</td>
                        <td>
                          {Object.entries(r.permissions).map(([mod, on]) => (
                            <span key={mod} title={`${names[mod] ?? mod}: ${on ? 'dozwolone' : 'brak dostępu'}`} className={`module-dot ${on ? 'module-dot-on' : 'module-dot-off'}`} />
                          ))}
                        </td>
                        <td>{r.is_protected && <span className="rbac-badge rbac-badge--protected">Systemowa</span>}</td>
                        <td className="cell-actions">
                          <div className="rbac-row-actions">
                            <ButtonLink to={`/poziomy-dostepu/${r.id}/edytuj`} variant="ghost">
                              Edytuj uprawnienia
                            </ButtonLink>
                            {!r.is_protected && (
                              <button type="button" className="refined-btn-danger btn-press" disabled={!!blocker} title={blocker ?? undefined} onClick={() => handleDelete(r)}>
                                Usuń
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <ul className="role-cards rbac-mobile-only">
            {roles.map((r) => (
              <li key={r.id} className="role-card">
                <Link to={`/poziomy-dostepu/${r.id}/edytuj`} className="role-card-main">
                  <span className="role-card-head">
                    <span className="role-card-name">{r.display_name}</span>
                    {r.is_protected && <span className="rbac-badge rbac-badge--protected">Systemowa</span>}
                  </span>
                  <span className="role-card-key">
                    {r.name} · {usersLabel(r.user_count)}
                  </span>
                  <ModuleChips permissions={r.permissions_detail} names={names} />
                </Link>
                <button type="button" className="user-card-more" aria-label={`Akcje: ${r.display_name}`} onClick={() => setSheetRole(r)}>
                  <Icon name="more_horiz" />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="rbac-mobile-cta rbac-mobile-only">
        <ButtonLink to="/poziomy-dostepu/nowa" variant="primary" icon="add">
          Nowa rola
        </ButtonLink>
      </div>

      <Modal isOpen={sheetRole !== null} onClose={() => setSheetRole(null)} title={sheetRole?.display_name ?? ''} variant="sheet">
        {sheetRole && (
          <ul className="action-sheet">
            <li>
              <Link className="action-sheet-item" to={`/poziomy-dostepu/${sheetRole.id}/edytuj`}>
                <Icon name="edit" /> Edytuj uprawnienia
              </Link>
            </li>
            {!sheetRole.is_protected && (
              <li className="action-sheet-danger">
                <button type="button" className="action-sheet-item" disabled={!!sheetBlocker} onClick={() => handleDelete(sheetRole)}>
                  <Icon name="delete" /> Usuń rolę
                </button>
                {sheetBlocker && <p className="action-sheet-reason">{sheetBlocker}</p>}
              </li>
            )}
          </ul>
        )}
      </Modal>
    </div>
  );
}
