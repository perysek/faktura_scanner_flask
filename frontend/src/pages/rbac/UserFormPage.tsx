import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import './RbacPages.css';
import { usersApi } from '../../lib/api/users';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { FormActions, FormCard, FormFieldset, SelectField, TextField } from '../../components/ui/form';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import { ModuleChips } from './ModuleChips';
import { Switch } from './Switch';
import { assignableRoles } from './rbacRules';
import type { AssignableRole, AvailableEmployee, LinkedEmployee } from '../../types/rbac';

interface Props {
  mode: 'create' | 'edit';
}

/** Nowy/Edytuj użytkownika. Built on the design-system form primitives (the
 * Jinja port used hand-rolled inputs). What's new versus that port: picking a
 * role shows what it grants, "-- Brak --" really unlinks the employee, and you
 * can't edit your own role or deactivate yourself (the API refuses both). The
 * password change stays a separate card with its own submit, like the original. */
export function UserFormPage({ mode }: Props) {
  const { id } = useParams<{ id: string }>();
  const userId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const auth = useAuth();
  const toast = useToast();
  const backTo = mode === 'edit' && userId ? `/uzytkownicy/${userId}` : '/uzytkownicy';
  useEscapeBack(backTo);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [availableEmployees, setAvailableEmployees] = useState<AvailableEmployee[]>([]);
  const [roles, setRoles] = useState<AssignableRole[]>([]);
  const [moduleNames, setModuleNames] = useState<Record<string, string>>({});
  const [linkedEmployee, setLinkedEmployee] = useState<LinkedEmployee | null>(null);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [role, setRole] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [isActive, setIsActive] = useState(true);

  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSaving, setPwSaving] = useState(false);

  const isSelf = mode === 'edit' && auth.user?.id === userId;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const opts = await usersApi.formOptions();
        if (cancelled) return;
        setAvailableEmployees(opts.available_employees);
        setRoles(opts.roles);
        setModuleNames(opts.module_display_names);

        if (mode === 'edit' && userId) {
          const detail = await usersApi.get(userId);
          if (cancelled) return;
          setFullName(detail.user.full_name);
          setEmail(detail.user.email);
          setRole(detail.user.role);
          setIsActive(detail.user.is_active);
          setLinkedEmployee(detail.linked_employee);
          if (detail.linked_employee) setEmployeeId(String(detail.linked_employee.id));
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
  }, [mode, userId]);

  const roleOptions = useMemo(() => {
    const offered = assignableRoles(auth.user, roles).map((r) => ({ value: r.name, label: r.display_name }));
    // A role that no longer exists still has to show up, or the select would
    // silently fall back to the placeholder and hide the problem.
    if (mode === 'edit' && role && !offered.some((o) => o.value === role) && !roles.some((r) => r.name === role)) {
      offered.unshift({ value: role, label: `${role} (rola usunięta — wybierz nową)` });
    }
    return offered;
  }, [auth.user, roles, mode, role]);

  const employeeOptions = useMemo(() => {
    const list = [...availableEmployees];
    if (mode === 'edit' && linkedEmployee && !list.some((e) => e.id === linkedEmployee.id)) list.unshift(linkedEmployee);
    return list.map((e) => ({
      value: String(e.id),
      label: `${e.first_name} ${e.last_name}${mode === 'edit' && linkedEmployee?.id === e.id ? ' (bieżący)' : ''}`,
    }));
  }, [availableEmployees, linkedEmployee, mode]);

  const selectedRole = roles.find((r) => r.name === role);
  const noFreeEmployees = mode === 'create' && !loading && availableEmployees.length === 0;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (mode === 'create' && password !== passwordConfirm) {
      setError('Hasła nie pasują do siebie.');
      return;
    }

    setSaving(true);
    try {
      let targetId = userId;
      if (mode === 'create') {
        const res = await usersApi.create({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
          role,
          employee_id: Number(employeeId),
          is_active: true,
        });
        targetId = res.user_id;
      } else if (userId) {
        await usersApi.update(userId, {
          full_name: fullName.trim(),
          email: email.trim(),
          role,
          is_active: isActive,
          employee_id: employeeId ? Number(employeeId) : null,
        });
      }
      toast.success(mode === 'create' ? 'Użytkownik utworzony' : 'Zmiany zostały zapisane.');
      navigate(targetId ? `/uzytkownicy/${targetId}` : '/uzytkownicy');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Błąd zapisu.');
    } finally {
      setSaving(false);
    }
  }

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setPwError('');
    if (!userId) return;
    if (newPassword.length < 8) {
      setPwError('Hasło musi mieć co najmniej 8 znaków.');
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setPwError('Hasła nie pasują do siebie.');
      return;
    }
    setPwSaving(true);
    try {
      await usersApi.changePassword(userId, newPassword);
      toast.success('Hasło zostało zmienione.');
      setNewPassword('');
      setNewPasswordConfirm('');
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : 'Błąd zmiany hasła.');
    } finally {
      setPwSaving(false);
    }
  }

  return (
    <div className="refined-page rbac-page rbac-form-page animate-fade-up">
      <header className="page-header rbac-page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowy użytkownik' : `Edytuj: ${fullName || '…'}`}</h1>
          <p className="page-subtitle">{mode === 'create' ? 'Konto logowania powiązane z pracownikiem' : 'Dane konta, rola i powiązany pracownik'}</p>
        </div>
      </header>

      <form onSubmit={handleSubmit}>
        <FormCard>
          {error && (
            <div className="rbac-error-msg" role="alert">
              {error}
            </div>
          )}

          <FormFieldset legend="Dane konta">
            <TextField label="Imię i nazwisko" required disabled={loading} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" autoFocus={mode === 'create'} />
            <TextField label="Email" type="email" required disabled={loading} value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </FormFieldset>

          {mode === 'create' && (
            <FormFieldset legend="Hasło">
              <TextField label="Hasło" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" helper="Minimum 8 znaków" />
              <TextField label="Potwierdź hasło" type="password" required value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} autoComplete="new-password" />
            </FormFieldset>
          )}

          <FormFieldset legend="Dostęp">
            <SelectField
              label="Rola"
              required
              disabled={loading || isSelf}
              placeholder="-- Wybierz rolę --"
              options={roleOptions}
              value={role}
              onChange={(e) => setRole(e.target.value)}
              helper={isSelf ? 'Nie możesz zmienić własnej roli.' : undefined}
            />
            <SelectField
              label="Powiązany pracownik"
              required={mode === 'create'}
              disabled={loading}
              placeholder={mode === 'create' ? '-- Wybierz pracownika --' : '-- Brak (odepnij od konta) --'}
              options={employeeOptions}
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              helper={mode === 'create' ? 'Tylko pracownicy bez przypisanego konta.' : 'Wybierz „Brak”, aby odpiąć pracownika od tego konta.'}
            />

            {selectedRole && (
              <div className="form-field-full">
                <span className="form-label">Ta rola daje dostęp do</span>
                <ModuleChips permissions={selectedRole.permissions} names={moduleNames} />
              </div>
            )}

            {noFreeEmployees && (
              <p className="rbac-note form-field-full">
                Każdy aktywny pracownik ma już konto.
                {auth.hasModuleWrite('employees') && (
                  <>
                    {' '}
                    <Link to="/pracownicy/nowy">Dodaj pracownika</Link>, a potem wróć tutaj.
                  </>
                )}
              </p>
            )}

            {mode === 'edit' && (
              <div className="form-field-full">
                <label className="perm-row perm-row--main perm-standalone">
                  <span className="perm-text">
                    <span className="perm-flag-label">Konto aktywne</span>
                    <span className="perm-hint">{isActive ? 'Może się logować' : 'Logowanie zablokowane'}</span>
                  </span>
                  <Switch checked={isActive} disabled={loading || isSelf} onChange={(e) => setIsActive(e.target.checked)} aria-label="Konto aktywne" />
                </label>
                {isSelf && <span className="form-helper-text">Nie możesz dezaktywować własnego konta.</span>}
              </div>
            )}
          </FormFieldset>

          <FormActions submitLabel={mode === 'create' ? 'Utwórz użytkownika' : 'Zapisz zmiany'} isLoading={saving || loading} cancelHref={backTo} />
        </FormCard>
      </form>

      {mode === 'edit' && !isSelf && (
        <form onSubmit={handlePasswordSubmit}>
          <FormCard>
            {pwError && (
              <div className="rbac-error-msg" role="alert">
                {pwError}
              </div>
            )}
            <FormFieldset legend="Zmiana hasła">
              <TextField label="Nowe hasło" type="password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" helper="Minimum 8 znaków" />
              <TextField label="Potwierdź nowe hasło" type="password" value={newPasswordConfirm} onChange={(e) => setNewPasswordConfirm(e.target.value)} autoComplete="new-password" />
            </FormFieldset>
            <FormActions submitLabel="Zmień hasło" isLoading={pwSaving} />
          </FormCard>
        </form>
      )}
      {isSelf && (
        <p className="rbac-note">
          Własne hasło zmienisz w <Link to="/profil">Profilu</Link>.
        </p>
      )}
    </div>
  );
}
