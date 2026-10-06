import { useEffect, useState } from 'react';
import './VisitNotes.css';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { SearchableSelectField, TextareaField } from '../ui/form';
import { useToast } from '../feedback/ToastProvider';
import { visitNotesApi } from '../../lib/api/visitNotes';
import { ApiError } from '../../lib/api/client';
import { formatDate } from '../../lib/format';
import { MAX_NOTE_LENGTH } from '../../lib/visitNotes/noteFormat';
import type { NoteableVisit, VisitNote } from '../../types/visitNote';

export interface VisitNoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Set to EDIT this note; leave unset to ADD one. */
  note?: VisitNote | null;
  /** ADD: the visit the note belongs to, when it is already known (a list row, the visit page). */
  appointmentId?: number | null;
  /** ADD with no `appointmentId` (the client page): the client whose completed visits to pick from. */
  clientId?: number;
  /** One line of context above the textarea for a known visit, e.g. "30.09.2026 · Anna Nowak · Koloryzacja". */
  visitLabel?: string;
  /** Called after a successful save, just before the modal closes — reload whatever shows notes. */
  onSaved: () => void;
}

const TEXT_FIELD_ID = 'visit-note-text';

function visitOptionLabel(v: NoteableVisit): string {
  return [formatDate(v.appointment_date), v.service_name, v.employee_name].filter(Boolean).join(' · ');
}

/**
 * Small add/edit dialog for one visit note: a textarea with Anuluj / Zapisz.
 * Adding to a known visit just needs the text; adding from the client page also
 * shows a picker of that client's completed visits (a note always belongs to
 * exactly one completed visit). The server re-checks every rule — this only
 * keeps the obvious mistakes from ever being sent.
 */
export function VisitNoteModal({ isOpen, onClose, note, appointmentId, clientId, visitLabel, onSaved }: VisitNoteModalProps) {
  const toast = useToast();
  const isEdit = !!note;
  const needsPicker = !isEdit && appointmentId == null;

  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [visits, setVisits] = useState<NoteableVisit[] | null>(null);
  const [visitsError, setVisitsError] = useState<string | null>(null);
  const [pickedVisit, setPickedVisit] = useState('');

  // Fresh form on every open (and when a different note is opened for editing).
  useEffect(() => {
    if (!isOpen) return;
    setText(note?.note_text ?? '');
    setSaving(false);
    // The shared focus trap puts focus on the first control (the "×"). A text-entry dialog
    // should start in the text, caret at the end. This effect runs after the trap's: the
    // Modal is our child, and child effects fire before the parent's.
    const field = document.getElementById(TEXT_FIELD_ID);
    if (field instanceof HTMLTextAreaElement) {
      field.focus();
      field.setSelectionRange(field.value.length, field.value.length);
    }
  }, [isOpen, note]);

  // Client page: load the completed visits to pick from, newest preselected.
  useEffect(() => {
    if (!isOpen || !needsPicker || clientId == null) return;
    let cancelled = false;
    setVisits(null);
    setVisitsError(null);
    visitNotesApi
      .visits(clientId)
      .then((list) => {
        if (cancelled) return;
        setVisits(list);
        setPickedVisit(list[0] ? String(list[0].appointment_id) : '');
      })
      .catch((err: unknown) => {
        if (!cancelled) setVisitsError(err instanceof ApiError ? err.message : 'Nie udało się wczytać wizyt');
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, needsPicker, clientId]);

  const trimmed = text.trim();
  const targetVisitId = isEdit ? null : appointmentId ?? (pickedVisit ? Number(pickedVisit) : null);
  const unchanged = isEdit && trimmed === note.note_text;
  const canSave = trimmed.length > 0 && !unchanged && (isEdit || targetVisitId !== null) && !saving;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    try {
      if (isEdit) {
        await visitNotesApi.update(note.id, trimmed);
        toast.success('Uwaga zapisana');
      } else {
        await visitNotesApi.create(targetVisitId as number, trimmed);
        toast.success('Uwaga dodana');
      }
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zapisać uwagi');
      setSaving(false);
    }
  }

  const context = isEdit
    ? [formatDate(note.appointment_date), note.client_name, note.service_name].filter(Boolean).join(' · ')
    : visitLabel;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Edytuj uwagę' : 'Dodaj uwagę z wizyty'}
      size="medium"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Anuluj
          </Button>
          <Button variant="primary" icon="save" isLoading={saving} loadingText="Zapisywanie…" disabled={!canSave} onClick={handleSave}>
            Zapisz
          </Button>
        </>
      }
    >
      {needsPicker ? (
        visitsError ? (
          <p className="vn-modal-error">{visitsError}</p>
        ) : visits === null ? (
          <p className="vn-modal-context">Ładowanie wizyt…</p>
        ) : visits.length === 0 ? (
          <p className="vn-modal-error">Brak zakończonych wizyt, do których można dodać uwagę.</p>
        ) : (
          <SearchableSelectField
            label="Wizyta"
            searchPlaceholder="Szukaj wizyty…"
            options={visits.map((v) => ({ value: String(v.appointment_id), label: visitOptionLabel(v) }))}
            value={pickedVisit}
            onChange={setPickedVisit}
            fullWidth
          />
        )
      ) : (
        context && <p className="vn-modal-context">{context}</p>
      )}
      <TextareaField
        id={TEXT_FIELD_ID}
        label="Treść uwagi"
        rows={5}
        maxLength={MAX_NOTE_LENGTH}
        value={text}
        onChange={(e) => setText(e.target.value)}
        helper={`${text.length} / ${MAX_NOTE_LENGTH}`}
        fullWidth
      />
    </Modal>
  );
}
