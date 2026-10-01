/** Mirrors MAX_NOTE_LENGTH in services/visit_note_service.py (the DB also enforces it). */
export const MAX_NOTE_LENGTH = 2000;

const STAMP = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/;

/**
 * "2026-10-01T08:15:00" -> "01.10.2026@08:15".
 *
 * Formats by slicing the string, never through `new Date()`: the backend already
 * converted to Warsaw time (utils.timezone.to_local) and sends no UTC offset, so
 * a Date round trip would re-interpret it in the browser's time zone.
 */
export function formatNoteStamp(iso: string | null | undefined): string {
  const m = iso ? STAMP.exec(iso) : null;
  return m ? `${m[3]}.${m[2]}.${m[1]}@${m[4]}:${m[5]}` : '—';
}

/** "2026-10-01T08:15:00" -> "01.10.26@08:15" — the compact form the list columns use. */
export function formatNoteStampShort(iso: string | null | undefined): string {
  const m = iso ? STAMP.exec(iso) : null;
  return m ? `${m[3]}.${m[2]}.${m[1].slice(2)}@${m[4]}:${m[5]}` : '—';
}
