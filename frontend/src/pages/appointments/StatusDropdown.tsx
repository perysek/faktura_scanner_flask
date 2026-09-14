import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useToast } from '../../components/feedback/ToastProvider';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { STATUS_LABELS, VALID_TRANSITIONS } from '../../types/appointment';
import type { AppointmentStatus } from '../../types/appointment';

export interface StatusDropdownProps {
  appointmentId: number;
  currentStatus: AppointmentStatus;
  /** Needed only for the no_show time-window gate below — same rule
   * WizytaDetailPage already applied to its own picker, now applied
   * everywhere this component replaces a status control. */
  appointmentDate: string;
  startTime: string;
  canWrite: boolean;
  onSuccess: () => void;
  /** Sizing/context class already on the old `.status-badge` trigger at each
   * call site (e.g. the mobile card's is smaller than the desktop row's) —
   * passed through unchanged. */
  className?: string;
  /** A target status this component must NOT apply itself — picking it closes
   * the menu and calls `onIntercept` instead. Used by WizytaDetailPage for
   * 'completed', which needs payment-method info this generic dropdown
   * doesn't collect (CompleteVisitModal handles it there instead). */
  interceptStatus?: AppointmentStatus;
  onIntercept?: () => void;
}

/**
 * Inline-tap status changer — DESIGN.md §17's "new settings-style popover"
 * idiom (trigger-button + role="menu", same click-outside/useEscapeClaim
 * shape as ThemeSwitcher), applied to appointment status instead of theme.
 * Replaces StatusChangeModal's centered-overlay picker everywhere it was
 * used (WizytyListPage's row badge, the mobile card's badge, and
 * WizytaDetailPage's hero badge + <select>) — one tap opens a small menu
 * anchored to the badge itself instead of a full modal.
 */
export function StatusDropdown({
  appointmentId,
  currentStatus,
  appointmentDate,
  startTime,
  canWrite,
  onSuccess,
  className,
  interceptStatus,
  onIntercept,
}: StatusDropdownProps) {
  const toast = useToast();
  const [isOpen, setIsOpen] = useState(false);
  const [view, setView] = useState<'menu' | 'reason'>('menu');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEscapeClaim(isOpen);

  const isNoShowAllowed = (() => {
    const start = new Date(`${appointmentDate}T${startTime}`);
    return start.getTime() - Date.now() <= 30 * 60 * 1000;
  })();
  const options = (VALID_TRANSITIONS[currentStatus] ?? []).filter((s) => s !== 'no_show' || isNoShowAllowed);

  function close(returnFocus: boolean) {
    setIsOpen(false);
    setView('menu');
    setReason('');
    if (returnFocus) btnRef.current?.focus();
  }

  useEffect(() => {
    if (!isOpen) return;
    function onDocClick(event: MouseEvent) {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || btnRef.current?.contains(target)) return;
      close(false);
    }
    document.addEventListener('click', onDocClick, true);
    return () => document.removeEventListener('click', onDocClick, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || view !== 'menu') return;
    itemRefs.current[0]?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, view]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.stopPropagation();
      close(true);
      return;
    }
    if (view !== 'menu') return;
    const idx = itemRefs.current.findIndex((el) => el === document.activeElement);
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      itemRefs.current[(idx + 1 + options.length) % options.length]?.focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      itemRefs.current[(idx - 1 + options.length) % options.length]?.focus();
    }
  }

  async function applyStatus(status: AppointmentStatus, cancellationReason?: string) {
    setSaving(true);
    try {
      const result = await appointmentsApi.updateStatus(appointmentId, status, cancellationReason);
      if (result.success) {
        toast.success(`Status zmieniony na: ${STATUS_LABELS[status]}`);
        close(false);
        onSuccess();
      } else {
        toast.error('Nie udało się zmienić statusu');
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zmiany statusu');
    } finally {
      setSaving(false);
    }
  }

  function selectStatus(status: AppointmentStatus) {
    if (interceptStatus && status === interceptStatus) {
      close(false);
      onIntercept?.();
      return;
    }
    if (status === 'cancelled') {
      setView('reason');
      return;
    }
    applyStatus(status);
  }

  if (!canWrite || options.length === 0) {
    return <span className={`status-badge ${currentStatus}${className ? ` ${className}` : ''}`}>{STATUS_LABELS[currentStatus]}</span>;
  }

  return (
    // flexShrink: 0 — every call site's old plain `.status-badge` button was
    // a flex child with `flex-shrink: 0` (mobile card row, desktop table
    // cell, detail-page hero); that CSS still targets the inner button
    // (class match, any depth) but no longer affects layout since THIS
    // wrapper is the actual flex item now — restated here so wrapping in a
    // positioning container doesn't let the badge shrink/wrap where it
    // didn't before.
    <div style={{ position: 'relative', display: 'inline-block', flexShrink: 0 }}>
      <button
        type="button"
        ref={btnRef}
        className={`status-badge clickable ${currentStatus}${className ? ` ${className}` : ''}`}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={`status-menu-${appointmentId}`}
        aria-label={`Zmień status wizyty: ${STATUS_LABELS[currentStatus]}`}
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen((o) => !o);
        }}
      >
        {STATUS_LABELS[currentStatus]}
      </button>
      {isOpen && (
        <div
          id={`status-menu-${appointmentId}`}
          ref={menuRef}
          className="status-dropdown-menu"
          role={view === 'menu' ? 'menu' : undefined}
          aria-label="Zmień status wizyty"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={handleKeyDown}
        >
          {view === 'menu' ? (
            options.map((status, i) => (
              <button
                key={status}
                type="button"
                ref={(el) => {
                  itemRefs.current[i] = el;
                }}
                className="status-dropdown-item"
                role="menuitem"
                disabled={saving}
                onClick={() => selectStatus(status)}
              >
                {STATUS_LABELS[status]}
              </button>
            ))
          ) : (
            <div className="status-dropdown-reason">
              <label htmlFor={`cancel-reason-${appointmentId}`}>Powód anulowania</label>
              <textarea
                id={`cancel-reason-${appointmentId}`}
                autoFocus
                placeholder="Opcjonalnie — wpisz powód anulowania..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <div className="status-dropdown-reason-actions">
                <button type="button" className="status-dropdown-item" disabled={saving} onClick={() => setView('menu')}>
                  Wstecz
                </button>
                <button type="button" className="status-dropdown-item status-dropdown-item--danger" disabled={saving} onClick={() => applyStatus('cancelled', reason.trim() || undefined)}>
                  {saving ? 'Zapisywanie…' : 'Anuluj wizytę'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
