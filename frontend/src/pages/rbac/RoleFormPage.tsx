import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './RbacPages.css';
import { rolesApi } from '../../lib/api/roles';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { FormActions, FormCard, FormFieldset, TextField } from '../../components/ui/form';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import { EMPTY_FLAGS, PermissionGrid } from './PermissionGrid';
import type { RolePermissionFlags } from '../../types/rbac';

interface Props {
  mode: 'create' | 'edit';
}

/** Nowa/Edytuj rolę. One permission editor for both modes (the Jinja create form
 * only had "access" switches, so a read-only role took a create-then-edit
 * two-step). The key is fixed once created — it is what accounts point at. */
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
  const [moduleNames, setModuleNames] = useState<Record<string, string>>({});
  const [isProtected, setIsProtected] = useState(false);

  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [flags, setFlags] = useState<Record<string, RolePermissionFlags>>({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        if (mode === 'create') {
          const opts = await rolesApi.formOptions();
          if (cancelled) return;
          setAllModules(opts.all_modules);
          setModuleNames(opts.module_display_names);
          setFlags(Object.fromEntries(opts.all_modules.map((m) => [m, { ...EMPTY_FLAGS }])));
        } else if (roleId) {
          const detail = await rolesApi.get(roleId);
          if (cancelled) return;
          setAllModules(detail.all_modules);
          setModuleNames(detail.module_display_names);
          setDisplayName(detail.role.display_name);
          setName(detail.role.name);
          setIsProtected(detail.role.is_protected);
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
    setFlags((prev) => ({ ...prev, [mod]: { ...(prev[mod] ?? EMPTY_FLAGS), [key]: value } }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const permissions = Object.fromEntries(allModules.map((m) => [m, flags[m] ?? EMPTY_FLAGS]));
      if (mode === 'create') {
        await rolesApi.create({ name: name.trim().toLowerCase().replace(/\s+/g, '_'), display_name: displayName.trim(), permissions });
      } else if (roleId) {
        await rolesApi.update(roleId, { display_name: displayName.trim(), permissions });
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
      <header className="page-header rbac-page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowa rola' : displayName || '…'}</h1>
          <p className="page-subtitle">{mode === 'create' ? 'Zdefiniuj, do czego ma dostęp ta rola' : <span style={{ fontFamily: 'monospace' }}>{name}</span>}</p>
        </div>
      </header>

      <form onSubmit={handleSubmit}>
        <FormCard>
          {error && (
            <div className="rbac-error-msg" role="alert">
              {error}
            </div>
          )}
          {isProtected && <p className="rbac-note">To rola systemowa. Zmiana jej uprawnień dotyczy wszystkich kont, które ją mają — i nie da się jej usunąć.</p>}

          <FormFieldset legend="Rola">
            {mode === 'create' && (
              <TextField
                label="Klucz roli"
                required
                pattern="[a-z][a-z_]{1,49}"
                title="Małe litery i podkreślenia, 2–50 znaków, zaczyna się od litery"
                placeholder="np. manager"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoCapitalize="none"
                helper='Nie zmienia się po utworzeniu. Np. "manager", "head_stylist"'
              />
            )}
            <TextField label="Wyświetlana nazwa" required placeholder="np. Kierownik" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </FormFieldset>

          <FormFieldset legend="Dostęp do modułów">
            <div className="form-field-full">
              <PermissionGrid modules={allModules} names={moduleNames} flags={flags} onChange={updateFlag} />
            </div>
          </FormFieldset>

          <FormActions submitLabel={mode === 'create' ? 'Utwórz rolę' : 'Zapisz uprawnienia'} isLoading={saving || loading} cancelHref="/poziomy-dostepu" />
        </FormCard>
      </form>
    </div>
  );
}
