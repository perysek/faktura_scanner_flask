import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { ScreenCard } from '../components/ScreenCard';
import { PulseDot } from '../components/PulseDot';
import { colors, fonts, pillColors, radii } from '../theme';
import { fetchToday, TodayAppointment, TodayResult } from '../api/mobileApi';
import { useTicker } from '../hooks/useTicker';
import { formatCountdown } from '../utils/countdown';

interface Props {
  sessionToken: string;
  employeeName: string;
  onOpenAppointment: (appt: TodayAppointment) => void;
  onSwitchEmployee: () => void;
  onUnauthorized: () => void;
  /** Bumped by the parent after an action succeeds elsewhere, to force a refetch. */
  refreshKey: number;
}

function formatTodayLabel(isoDate: string | undefined): string {
  if (!isoDate) return '';
  const [y, m, d] = isoDate.split('-').map(Number);
  const date = new Date(y, m - 1, d); // local time -- never new Date(isoDate) directly (UTC parse bug)
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
}

function pillLabelFor(appt: TodayAppointment, now: number): string {
  if (appt.state === 'too_early' && appt.unlock_at) {
    return formatCountdown(new Date(appt.unlock_at).getTime() - now);
  }
  switch (appt.state) {
    case 'already_done':
      return 'Zakończona';
    case 'end_visit':
      return 'W trakcie';
    case 'start_visit':
      return 'Gotowość';
    case 'wrong_status':
      return 'Sprawdź';
    default:
      return '';
  }
}

export function TodayListScreen({
  sessionToken,
  employeeName,
  onOpenAppointment,
  onSwitchEmployee,
  onUnauthorized,
  refreshKey,
}: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [appointments, setAppointments] = useState<TodayAppointment[]>([]);
  const [todayLabel, setTodayLabel] = useState('');
  const now = useTicker(1000);
  const expiredRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result: TodayResult = await fetchToday(sessionToken);
    setLoading(false);
    if (!result.success) {
      if (result.error === 'unauthorized') {
        onUnauthorized();
        return;
      }
      setError(result.error === 'network_error' ? 'Brak połączenia z serwerem.' : 'Coś poszło nie tak.');
      return;
    }
    expiredRef.current = false;
    setAppointments(result.appointments);
    setTodayLabel(formatTodayLabel(result.today));
  }, [sessionToken, onUnauthorized]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, refreshKey]);

  // When any too_early countdown reaches zero, refetch once to pick up the
  // server-authoritative state (mirrors the design's "reload at zero").
  useEffect(() => {
    if (expiredRef.current) return;
    const anyExpired = appointments.some(
      (a) => a.state === 'too_early' && a.unlock_at && new Date(a.unlock_at).getTime() - now <= 0
    );
    if (anyExpired) {
      expiredRef.current = true;
      load();
    }
  }, [now, appointments, load]);

  return (
    <ScreenCard noPadding>
      <View style={styles.header}>
        <Image source={require('../../assets/logo.png')} style={styles.logo} resizeMode="contain" />
        <Text style={styles.subheading}>Dzisiejsze wizyty — {todayLabel}</Text>
      </View>

      {loading && (
        <View style={styles.centered}>
          <ActivityIndicator color={colors.ink} />
        </View>
      )}

      {!loading && error && (
        <View style={styles.centered}>
          <Text style={styles.errorMsg}>{error}</Text>
          <Pressable onPress={load}>
            <Text style={styles.retryLink}>Spróbuj ponownie</Text>
          </Pressable>
        </View>
      )}

      {!loading && !error && appointments.length === 0 && (
        <Text style={styles.emptyMsg}>Brak wizyt na dziś.</Text>
      )}

      {!loading &&
        !error &&
        appointments.map((appt) => {
          const pill = pillColors[appt.state] ?? pillColors.wrong_status;
          return (
            <Pressable
              key={appt.appointment_id}
              onPress={() => onOpenAppointment(appt)}
              style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            >
              <Text style={styles.time}>{appt.start_time}</Text>
              <View style={styles.rowMain}>
                <Text style={styles.client} numberOfLines={1}>
                  {appt.client_name}
                </Text>
                <Text style={styles.service} numberOfLines={1}>
                  {appt.service_name ?? ''}
                </Text>
              </View>
              <View style={[styles.pill, { backgroundColor: pill.bg }]}>
                {pill.dot && <PulseDot color={pill.fg} />}
                <Text style={[styles.pillText, { color: pill.fg }]}>{pillLabelFor(appt, now)}</Text>
              </View>
            </Pressable>
          );
        })}

      <Pressable onPress={onSwitchEmployee} style={styles.switchRow}>
        <Text style={styles.switchLink}>Zmień pracownika ({employeeName})</Text>
      </Pressable>
    </ScreenCard>
  );
}

const LOGO_ASPECT = 1645 / 478;

const styles = StyleSheet.create({
  header: {
    paddingTop: 32,
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  logo: {
    width: 200,
    height: 200 / LOGO_ASPECT,
    marginBottom: 12,
  },
  subheading: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.inkMuted,
  },
  centered: {
    paddingVertical: 32,
    paddingHorizontal: 24,
    alignItems: 'center',
  },
  errorMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.error,
    marginBottom: 8,
  },
  retryLink: {
    fontFamily: fonts.medium,
    fontSize: 14,
    color: colors.ink,
    textDecorationLine: 'underline',
  },
  emptyMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.inkMuted,
    paddingHorizontal: 24,
    paddingBottom: 32,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
  },
  rowPressed: {
    backgroundColor: colors.surface,
  },
  time: {
    minWidth: 48,
    fontFamily: fonts.semiBold,
    fontSize: 15,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
  },
  rowMain: {
    flex: 1,
    minWidth: 0,
  },
  client: {
    fontFamily: fonts.medium,
    fontSize: 14,
    color: colors.ink,
  },
  service: {
    fontFamily: fonts.regular,
    fontSize: 12,
    color: colors.inkSubtle,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexShrink: 0,
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: radii.badge,
  },
  pillText: {
    fontFamily: fonts.semiBold,
    fontSize: 12,
    fontVariant: ['tabular-nums'],
  },
  switchRow: {
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
  },
  switchLink: {
    fontFamily: fonts.regular,
    fontSize: 13,
    color: colors.inkMuted,
    textAlign: 'center',
  },
});
