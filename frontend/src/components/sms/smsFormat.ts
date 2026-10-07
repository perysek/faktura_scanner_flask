import type { SmsDeliveryStatus } from '../../types/sms';

/** "2026-10-07T04:20:53" -> "07.10.2026 04:20". The server already sends Warsaw wall-clock, so this is
 * plain string slicing — a Date round-trip would re-interpret it in the BROWSER's zone. */
export function fmtWhen(iso: string | null | undefined): string {
  if (!iso || iso.length < 16) return '—';
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)} ${iso.slice(11, 16)}`;
}

/** Same minute-precision time with the seconds, for a tooltip ("04:20:53"). */
export function fmtWhenExact(iso: string | null | undefined): string {
  if (!iso || iso.length < 19) return fmtWhen(iso);
  return `${fmtWhen(iso)}:${iso.slice(17, 19)}`;
}

/** "2026-10-10" + "08:00:00" -> "10.10.2026 08:00". */
export function fmtVisit(date: string | null | undefined, time: string | null | undefined): string {
  if (!date) return '—';
  const [y, m, d] = date.slice(0, 10).split('-');
  return `${d}.${m}.${y}${time ? ` ${time.slice(0, 5)}` : ''}`;
}

export const SMS_STATUS: Record<SmsDeliveryStatus, { label: string; className: string }> = {
  pending: { label: 'Oczekuje', className: 'sms-pill--pending' },
  sent: { label: 'Wysłany', className: 'sms-pill--sent' },
  delivered: { label: 'Dostarczony', className: 'sms-pill--delivered' },
  failed: { label: 'Błąd', className: 'sms-pill--failed' },
};

export function smsStatus(status: string | null | undefined): { label: string; className: string } {
  return SMS_STATUS[(status ?? 'pending') as SmsDeliveryStatus] ?? SMS_STATUS.pending;
}
