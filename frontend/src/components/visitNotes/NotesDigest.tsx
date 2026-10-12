import { Fragment } from 'react';
import './VisitNotes.css';
import { formatNoteStampShort } from '../../lib/visitNotes/noteFormat';
import type { RecentNote } from '../../types/visitNote';

/**
 * The "Aktualne uwagi i zalecenia" list-column cell: each note's text followed by
 * its `[dd.mm.yy@HH:MM]` stamp, separated by a comma. The caller decides how many
 * notes it was given (clients list: 2, visits list: 1) — this only renders them.
 * Text soft-wraps in the column; nothing is clipped (see VisitNotes.css).
 * `label` (visits list: "Zalecenie po wizycie:") is a bold lead-in before the first note.
 */
export function NotesDigest({ notes, label }: { notes: RecentNote[] | null | undefined; label?: string }) {
  if (!notes || notes.length === 0) return <span className="vn-digest-empty">—</span>;
  return (
    <span className="vn-digest">
      {label && <strong className="vn-digest-label">{label} </strong>}
      {notes.map((note, i) => (
        <Fragment key={i}>
          {i > 0 && ', '}
          {note.text} <span className="vn-digest-stamp">[{formatNoteStampShort(note.at)}]</span>
        </Fragment>
      ))}
    </span>
  );
}
