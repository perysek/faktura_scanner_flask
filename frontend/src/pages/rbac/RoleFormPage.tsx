import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './RbacPages.css';
import { rolesApi } from '../../lib/api/roles';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { FormActions } from '../../components/ui/form';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import type { RolePermissionFlags } from '../../types/rbac';

interface Props {
  mode: 'create' | 'edit';
}

const DEFAULT_FLAGS: RolePermissionFlags = { has_access: false, read_only: false, own_data: false, can_edit_price_history: false, can_send_sms: false };

/** Nowa/Edytuj rolę — ported from templates/roles/{create,edit}.html. Create
 * is a simple has_access-only toggle per module (the extra flags default to
 * false server-side, same as the original create form); edit exposes the
 * full per-module flag set (read_only/own_data + the two module-specific
 * sub-flags for services/appointments). */
export function RoleFormPage({ mode }: Props) {
  const { id } = useParams<{ id: string }>();
  const roleId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const toast = useToast();
  useEscapeBack('/poziomy-dostepu');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [allModules, setAllModules] = useState<string[]>([]);
  const [moduleDisplayNames, setModuleDisplayNames] = useState<Record<string, string>>({});

  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [flags, setFlags] = useState<Record<string, RolePermissionFlags>>({});

  const roleTitle = useMemo(() => (mode === 'create' ? 'Nowa rola' : displayName || '…'), [mode, displayName]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        if (mode === 'create') {
          const opts = await rolesApi.formOptions();
          if (cancelled) return;
          setAllModules(opts.all_modules);
          setModuleDisplayNames(opts.module_display_names);
          setFlags(Object.fromEntries(opts.all_modules.map((m) => [m, { ...DEFAULT_FLAGS }])));
        } else if (roleId) {
          const detail = await rolesApi.get(roleId);
          if (cancelled) return;
          setAllModules(detail.all_modules);
          setModuleDisplayNames(detail.module_display_names);
          setDisplayName(detail.role.display_name);
          setName(detail.role.name);
          setFlags(detail.permissions);
        }
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : 'Błąd ładowania danych');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, roleId]);

  function updateFlag(mod: string, key: keyof RolePermissionFlags, value: boolean) {
    setFlags((prev) => ({ ...prev, [mod]: { ...(prev[mod] ?? DEFAULT_FLAGS), [key]: value } }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      if (mode === 'create') {
        const permissions = Object.fromEntries(allModules.map((m) => [m, flags[m]?.has_access ?? false]));
        await rolesApi.create({ name: name.trim().toLowerCase().replace(/\s+/g, '_'), display_name: displayName.trim(), permissions });
      } else if (roleId) {
        await rolesApi.update(roleId, { display_name: displayName.trim(), permissions: flags });
      }
      toast.success(mode === 'create' ? 'Rola utworzona' : 'Uprawnienia zostały zapisane.');
      navigate('/poziomy-dostepu');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : mode === 'create' ? 'Błąd tworzenia roli.' : 'Błąd zapisu.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="refined-page rbac-page rbac-form-page animate-fade-up">
      <h1 className="page-title">{roleTitle}</h1>
      {mode === 'edit' && <p style={{ color: 'var(--color-ink-muted)', fontSize: '0.875rem', marginBottom: '2rem', fontFamily: 'monospace' }}>{name}</p>}

      <div className="refined-card">
        {error && <div className="rbac-error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          {mode === 'create' && (
            <div className="field-group">
              <label className="field-label" htmlFor="role-name">
                Nazwa roli (klucz systemowy)
              </label>
              <input id="role-name" className="field-input" required pattern="[a-z_]+" title="Tylko małe litery i podkreślenia" placeholder="np. manager" value={name} onChange={(e) => setName(e.target.value)} />
              <p className="field-hint">Tylko małe litery i podkreślenia. Np. "manager", "head_stylist"</p>
            </div>
          )}
          <div className="field-group">
            <label className="field-label" htmlFor="display-name">
              Wyświetlana nazwa
            </label>
            <input id="display-name" className="field-input" required placeholder="np. Kierownik" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>

          <div className="rbac-section-title" style={{ marginTop: '1.5rem' }}>
            Dostęp do modułów
          </div>
          <div>
            {allModules.map((mod) => {
              const f = flags[mod] ?? DEFAULT_FLAGS;
              if (mode === 'create') {
                return (
                  <div key={mod} className="module-row module-row--simple">
                    <div>
                      <div className="module-name">{moduleDisplayNames[mod] ?? mod}</div>
                      <div className="module-key">{mod}</div>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={f.has_access} onChange={(e) => updateFlag(mod, 'has_access', e.target.checked)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>
                );
              }
              return (
                <div key={mod} className="module-row">
                  <div className="module-main">
                    <div>
                      <div className="module-name">{moduleDisplayNames[mod] ?? mod}</div>
                      <div className="module-key">{mod}</div>
                    </div>
                    <label className="toggle">
                      <input type="checkbox" checked={f.has_access} onChange={(e) => updateFlag(mod, 'has_access', e.target.checked)} />
                      <span className="toggle-slider" />
                    </label>
                  </div>
                  <div className={`module-flags${f.has_access ? '' : ' disabled'}`}>
                    <div className="flag-item">
                      <label className="toggle toggle-sm">
                        <input type="checkbox" checked={f.read_only} onChange={(e) => updateFlag(mod, 'read_only', e.target.checked)} />
                        <span className="toggle-slider" />
                      </label>
                      <span>Tylko do odczytu</span>
                    </div>
                    <div className="flag-item">
                      <label className="toggle toggle-sm">
                        <input type="checkbox" checked={f.own_data} onChange={(e) => updateFlag(mod, 'own_data', e.target.checked)} />
                        <span className="toggle-slider" />
                      </label>
                      <span>Tylko własne dane</span>
                    </div>
                    {mod === 'services' && (
                      <div className="flag-item">
                        <label className="toggle toggle-sm">
                          <input type="checkbox" checked={f.can_edit_price_history} onChange={(e) => updateFlag(mod, 'can_edit_price_history', e.target.checked)} />
                          <span className="toggle-slider" />
                        </label>
                        <span>Edycja historii zmian ceny</span>
                      </div>
                    )}
                    {mod === 'appointments' && (
                      <div className="flag-item">
                        <label className="toggle toggle-sm">
                          <input type="checkbox" checked={f.can_send_sms} onChange={(e) => updateFlag(mod, 'can_send_sms', e.target.checked)} />
                          <span className="toggle-slider" />
                        </label>
                        <span>Wysyłanie SMS</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <FormActions submitLabel={mode === 'create' ? 'Utwórz rolę' : 'Zapisz uprawnienia'} isLoading={saving || loading} cancelHref="/poziomy-dostepu" />
        </form>
      </div>
    </div>
  );
}
