import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './RbacPages.css';
import { usersApi } from '../../lib/api/users';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { FormActions } from '../../components/ui/form';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import type { AssignableRole, AvailableEmployee, LinkedEmployee } from '../../types/rbac';

interface Props {
  mode: 'create' | 'edit';
}

/** Nowy/Edytuj użytkownika — ported from templates/users/{create,edit}.html.
 * Edit mode additionally has a separate "change password" card, kept
 * separate from the main save action exactly like the original (two
 * independent forms/submit buttons, not merged into one). */
export function UserFormPage({ mode }: Props) {
  const { id } = useParams<{ id: string }>();
  const userId = id ? Number(id) : undefined;
  const navigate = useNavigate();
  const toast = useToast();
  useEscapeBack('/uzytkownicy');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [availableEmployees, setAvailableEmployees] = useState<AvailableEmployee[]>([]);
  const [roles, setRoles] = useState<AssignableRole[]>([]);
  const [linkedEmployee, setLinkedEmployee] = useState<LinkedEmployee | null>(null);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [role, setRole] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [isActive, setIsActive] = useState(true);

  // Change-password card (edit mode only) — independent submit.
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const opts = await usersApi.formOptions();
        if (cancelled) return;
        setAvailableEmployees(opts.available_employees);
        setRoles(opts.roles);

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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (mode === 'create' && password !== passwordConfirm) {
      setError('Hasła nie pasują do siebie.');
      return;
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        await usersApi.create({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
          role,
          employee_id: Number(employeeId),
          is_active: true,
        });
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
      navigate('/uzytkownicy');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Błąd zapisu.');
    } finally {
      setSaving(false);
    }
  }

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPwError('');
    setPwSuccess('');
    if (!newPassword || !userId) return;
    if (newPassword !== newPasswordConfirm) {
      setPwError('Hasła nie pasują do siebie.');
      return;
    }
    setPwSaving(true);
    try {
      await usersApi.changePassword(userId, newPassword);
      setPwSuccess('Hasło zostało zmienione.');
      setNewPassword('');
      setNewPasswordConfirm('');
    } catch (err) {
      setPwError(err instanceof ApiError ? err.message : 'Błąd zmiany hasła.');
    } finally {
      setPwSaving(false);
    }
  }

  const employeeOptions =
    mode === 'edit' && linkedEmployee && !availableEmployees.some((e) => e.id === linkedEmployee.id)
      ? [{ id: linkedEmployee.id, first_name: linkedEmployee.first_name, last_name: linkedEmployee.last_name }, ...availableEmployees]
      : availableEmployees;

  return (
    <div className="refined-page rbac-page rbac-form-page animate-fade-up">
      <h1 className="page-title">{mode === 'create' ? 'Nowy użytkownik' : `Edytuj: ${fullName}`}</h1>

      <div className="refined-card">
        {mode === 'edit' && <div className="rbac-section-title">Dane konta</div>}
        {error && <div className="rbac-error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field-group">
            <label className="field-label" htmlFor="full_name">
              Imię i nazwisko {mode === 'create' && <span className="required-mark">*</span>}
            </label>
            <input id="full_name" className="field-input" required disabled={loading} value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor="email">
              Email {mode === 'create' && <span className="required-mark">*</span>}
            </label>
            <input id="email" type="email" className="field-input" required disabled={loading} value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>

          {mode === 'create' && (
            <>
              <div className="field-group">
                <label className="field-label" htmlFor="password">
                  Hasło <span className="required-mark">*</span>
                </label>
                <input id="password" type="password" className="field-input" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
                <p className="field-hint">Minimum 8 znaków</p>
              </div>
              <div className="field-group">
                <label className="field-label" htmlFor="password_confirm">
                  Potwierdź hasło <span className="required-mark">*</span>
                </label>
                <input id="password_confirm" type="password" className="field-input" required value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} />
              </div>
            </>
          )}

          <div className="field-group">
            <label className="field-label" htmlFor="role">
              Rola {mode === 'create' && <span className="required-mark">*</span>}
            </label>
            <select id="role" className="field-select" required disabled={loading} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="">-- Wybierz rolę --</option>
              {roles.map((r) => (
                <option key={r.name} value={r.name}>
                  {r.display_name} ({r.name})
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="employee_id">
              {mode === 'create' ? (
                <>
                  Pracownik <span className="required-mark">*</span>
                </>
              ) : (
                'Powiązany pracownik'
              )}
            </label>
            <select id="employee_id" className="field-select" required={mode === 'create'} disabled={loading} value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
              <option value="">{mode === 'create' ? '-- Wybierz pracownika --' : '-- Brak --'}</option>
              {employeeOptions.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.first_name} {emp.last_name}
                  {mode === 'edit' && linkedEmployee?.id === emp.id ? ' (bieżący)' : ''}
                </option>
              ))}
            </select>
            {mode === 'create' && <p className="field-hint">Tylko pracownicy bez przypisanego konta użytkownika</p>}
          </div>

          {mode === 'edit' && (
            <div className="field-group">
              <label className="field-label">Aktywne konto</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <label className="toggle">
                  <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
                  <span className="toggle-slider" />
                </label>
                <span style={{ fontSize: '0.875rem', color: 'var(--color-ink-muted)' }}>{isActive ? 'Aktywne' : 'Nieaktywne'}</span>
              </div>
            </div>
          )}

          <FormActions submitLabel={mode === 'create' ? 'Utwórz użytkownika' : 'Zapisz zmiany'} isLoading={saving} cancelHref="/uzytkownicy" />
        </form>
      </div>

      {mode === 'edit' && (
        <div className="refined-card">
          <div className="rbac-section-title">Zmiana hasła</div>
          {pwError && <div className="rbac-error-msg">{pwError}</div>}
          {pwSuccess && <div className="rbac-success-msg">{pwSuccess}</div>}
          <form onSubmit={handlePasswordSubmit}>
            <div className="field-group">
              <label className="field-label" htmlFor="new_password">
                Nowe hasło
              </label>
              <input id="new_password" type="password" className="field-input" minLength={8} placeholder="Pozostaw puste, aby nie zmieniać" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
              <p className="field-hint">Minimum 8 znaków. Pozostaw puste, aby zachować obecne hasło.</p>
            </div>
            <div className="field-group">
              <label className="field-label" htmlFor="new_password_confirm">
                Potwierdź nowe hasło
              </label>
              <input id="new_password_confirm" type="password" className="field-input" value={newPasswordConfirm} onChange={(e) => setNewPasswordConfirm(e.target.value)} />
            </div>
            <FormActions submitLabel="Zmień hasło" isLoading={pwSaving} />
          </form>
        </div>
      )}
    </div>
  );
}
