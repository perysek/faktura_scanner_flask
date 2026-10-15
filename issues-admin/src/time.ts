/** Time helpers — every API timestamp is ISO UTC ('…Z'); the browser shows Warsaw time. */

export function ago(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const min = Math.floor(diff / 60000);
  if (min < 1) return 'przed chwilą';
  if (min < 60) return `${min} min temu`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} godz. temu`;
  const d = Math.floor(h / 24);
  if (d < 30) return d === 1 ? 'wczoraj' : `${d} dni temu`;
  return dateTime(iso);
}

/** "12 min" / "3 godz." / "2 dni" — age badges in the list. */
export function ageShort(iso: string | null | undefined): string {
  if (!iso) return '';
  const min = Math.floor(Math.max(0, Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 60) return `${Math.max(min, 1)} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} godz.`;
  return `${Math.floor(h / 24)} d`;
}

/** Hours since `iso` — the list's age badge turns amber > 24 h, red > 72 h (plan §7). */
export function hoursSince(iso: string | null | undefined): number {
  return iso ? (Date.now() - new Date(iso).getTime()) / 3_600_000 : 0;
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  const sameDay = d.toDateString() === new Date().toDateString();
  return sameDay
    ? d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleString('pl-PL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  const min = Math.round(seconds / 60);
  if (min < 60) return `${min} min`;
  const h = min / 60;
  if (h < 48) return `${h.toFixed(h < 10 ? 1 : 0)} godz.`;
  return `${(h / 24).toFixed(1)} dni`;
}

export function between(from: string | null | undefined, to: string | null | undefined): string {
  if (!from || !to) return '—';
  return duration((new Date(to).getTime() - new Date(from).getTime()) / 1000);
}
