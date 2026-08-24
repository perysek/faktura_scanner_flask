import { Link } from 'react-router-dom';
import './RbacPages.css';
import { useApiData } from '../../lib/useApiData';
import { rolesApi } from '../../lib/api/roles';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Icon } from '../../lib/icons/Icon';
import { MODULE_LABELS } from '../../types/rbac';
import type { RoleListRow } from '../../types/rbac';

/** Role — lista ról z macierzą uprawnień jako kropki (dozwolone/brak
 * dostępu). Ported from templates/roles/list.html. */
export function RolesListPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const rolesState = useApiData(() => rolesApi.list(), []);
  const roles = rolesState.data ?? [];

  async function handleDelete(role: RoleListRow) {
    const ok = await confirm({
      title: 'Usuń rolę',
      message: `Usunąć rolę "${role.display_name}"? Użytkownicy z tą rolą stracą dostęp.`,
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

  return (
    <div className="refined-page rbac-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Role</h1>
          <p className="page-subtitle">Zarządzanie rolami i uprawnieniami modułów</p>
        </div>
        <Link to="/poziomy-dostepu/nowa" className="refined-btn-primary btn-press">
          <Icon name="add" /> Nowa rola
        </Link>
      </header>

      <div className="refined-card">
        <div className="dot-legend">
          <span className="dot-legend-item">
            <span className="module-dot module-dot-on" /> dozwolone
          </span>
          <span className="dot-legend-item">
            <span className="module-dot module-dot-off" /> brak dostępu
          </span>
        </div>
        {rolesState.loading ? (
          <div className="rbac-empty-state">Ładowanie…</div>
        ) : (
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                <th>Nazwa</th>
                <th>Wyświetlana nazwa</th>
                <th>Uprawnienia modułów</th>
                <th>Typ</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.id}>
                  <td data-label="Nazwa" style={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}>
                    {r.name}
                  </td>
                  <td className="cell-name" style={{ fontWeight: 500 }}>
                    {r.display_name}
                  </td>
                  <td data-label="Uprawnienia modułów">
                    {Object.entries(r.permissions).map(([mod, on]) => (
                      <span key={mod} title={MODULE_LABELS[mod] || mod} className={`module-dot ${on ? 'module-dot-on' : 'module-dot-off'}`} />
                    ))}
                  </td>
                  <td data-label="Typ">{r.is_protected && <span className="badge badge-protected">Systemowa</span>}</td>
                  <td className="cell-actions" style={{ gap: '0.5rem', justifyContent: 'flex-end' }}>
                    <div className="rbac-row-actions">
                      <Link to={`/poziomy-dostepu/${r.id}/edytuj`} className="refined-btn-ghost btn-press">
                        Edytuj uprawnienia
                      </Link>
                      {!r.is_protected && (
                        <button type="button" className="refined-btn-danger btn-press" onClick={() => handleDelete(r)}>
                          Usuń
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
