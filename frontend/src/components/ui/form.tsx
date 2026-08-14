import { useId } from 'react';
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './Button';

/**
 * Typed form primitives — DESIGN.md §7. Never hand-roll a raw
 * <input>/<select>/<textarea> on a page; always go through these.
 *
 * Field wrapper contract, identical across every field type:
 * - Label always above the input (`.form-label`)
 * - Required fields get a red `*` marker (`aria-hidden` — the `required`
 *   attribute is the real accessible signal)
 * - Error text takes priority and suppresses helper text
 * - Helper text only shows when there's no error
 * - `fullWidth` spans the field across the whole grid (`.form-field-full`)
 */

interface FieldWrapperProps {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  helper?: string;
  fullWidth?: boolean;
  children: ReactNode;
}

function FieldWrapper({ id, label, required, error, helper, fullWidth, children }: FieldWrapperProps) {
  return (
    <div className={fullWidth ? 'form-field-full' : undefined}>
      <label htmlFor={id} className="form-label">
        {label} {required && <span className="required-mark" aria-hidden="true">*</span>}
      </label>
      {children}
      {error ? (
        <span className="form-error-text" role="alert">
          {error}
        </span>
      ) : helper ? (
        <span className="form-helper-text">{helper}</span>
      ) : null}
    </div>
  );
}

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'className'> {
  label: string;
  error?: string;
  helper?: string;
  fullWidth?: boolean;
  id?: string;
}

export function TextField({ label, error, helper, fullWidth, id, required, ...rest }: TextFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  return (
    <FieldWrapper id={fieldId} label={label} required={required} error={error} helper={helper} fullWidth={fullWidth}>
      <input
        id={fieldId}
        required={required}
        className={`form-input${error ? ' error' : ''}`}
        {...rest}
      />
    </FieldWrapper>
  );
}

export interface SelectFieldOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'className'> {
  label: string;
  options: SelectFieldOption[];
  placeholder?: string;
  error?: string;
  helper?: string;
  fullWidth?: boolean;
  id?: string;
}

export function SelectField({
  label,
  options,
  placeholder,
  error,
  helper,
  fullWidth,
  id,
  required,
  ...rest
}: SelectFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  return (
    <FieldWrapper id={fieldId} label={label} required={required} error={error} helper={helper} fullWidth={fullWidth}>
      <select id={fieldId} required={required} className={`form-select${error ? ' error' : ''}`} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
    </FieldWrapper>
  );
}

export interface TextareaFieldProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id' | 'className'> {
  label: string;
  error?: string;
  helper?: string;
  fullWidth?: boolean;
  id?: string;
}

export function TextareaField({ label, error, helper, fullWidth, id, required, ...rest }: TextareaFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  return (
    <FieldWrapper id={fieldId} label={label} required={required} error={error} helper={helper} fullWidth={fullWidth}>
      <textarea id={fieldId} required={required} className={`form-textarea${error ? ' error' : ''}`} {...rest} />
    </FieldWrapper>
  );
}

export interface CheckboxFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'className' | 'type'> {
  label: string;
  description?: string;
  id?: string;
}

export function CheckboxField({ label, description, id, ...rest }: CheckboxFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  return (
    <div>
      <div className="checkbox-wrapper">
        <input id={fieldId} type="checkbox" className="refined-checkbox" {...rest} />
        <label htmlFor={fieldId} className="checkbox-label">
          {label}
        </label>
      </div>
      {description && <p className="checkbox-description">{description}</p>}
    </div>
  );
}

export function FormCard({ children }: { children: ReactNode }) {
  return <div className="form-card">{children}</div>;
}

export interface FormFieldsetProps {
  legend: string;
  children: ReactNode;
}

/** Real <fieldset>/<legend>, not a styled <div> — screen readers announce the
 * group name before each field. Always the auto-fit `.form-grid` (§5) — a
 * field that needs to force its own full-width row (e.g. a long textarea
 * next to short fields) opts in via `fullWidth` on the field itself, rather
 * than this component offering a separate "1-column" mode. */
export function FormFieldset({ legend, children }: FormFieldsetProps) {
  return (
    <fieldset className="form-fieldset">
      <legend>{legend}</legend>
      <div className="form-grid">{children}</div>
    </fieldset>
  );
}

/** Convenience: one FormCard wrapping one FormFieldset, for single-topic
 * forms. Multi-topic forms compose FormCard + multiple FormFieldsets
 * directly instead (§7). */
export function FormSection({ legend, children }: FormFieldsetProps) {
  return (
    <FormCard>
      <FormFieldset legend={legend}>{children}</FormFieldset>
    </FormCard>
  );
}

export interface FormActionsProps {
  submitLabel?: string;
  savingLabel?: string;
  isLoading?: boolean;
  cancelHref?: string;
  onCancel?: () => void;
  cancelLabel?: string;
}

/** Submit + optional cancel button row. Submit shows a "Zapisywanie…"-style
 * busy label when isLoading (§7). */
export function FormActions({
  submitLabel = 'Zapisz',
  savingLabel = 'Zapisywanie…',
  isLoading,
  cancelHref,
  onCancel,
  cancelLabel = 'Anuluj',
}: FormActionsProps) {
  const navigate = useNavigate();
  return (
    <div className="form-actions">
      <Button type="submit" variant="primary" icon="save" isLoading={isLoading} loadingText={savingLabel}>
        {submitLabel}
      </Button>
      {cancelHref ? (
        <Button type="button" variant="secondary" onClick={() => navigate(cancelHref)}>
          {cancelLabel}
        </Button>
      ) : onCancel ? (
        <Button type="button" variant="secondary" onClick={onCancel}>
          {cancelLabel}
        </Button>
      ) : null}
    </div>
  );
}
