import React, { useEffect, useRef, useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { ScreenCard } from '../components/ScreenCard';
import { ConfirmButton } from '../components/ConfirmButton';
import { DetailRow } from '../components/DetailRow';
import { colors, fonts, radii } from '../theme';
import {
  TodayAppointment,
  VisitState,
  fetchAppointmentState,
  submitAppointmentAction,
} from '../api/mobileApi';
import { useTicker } from '../hooks/useTicker';
import { formatCountdown } from '../utils/countdown';

interface Props {
  sessionToken: string;
  appointment: TodayAppointment;
  onBack: () => void;
  onDone: () => void;
  onUnauthorized: () => void;
}

function formatToday(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

function successMessageFor(newStatus: string): string {
  switch (newStatus) {
    case 'in_progress':
      return 'Wizyta oznaczona jako W trakcie.';
    case 'completed':
      return 'Wizyta oznaczona jako Zakończona.';
    case 'no_show':
      return 'Wizyta oznaczona jako: klient się nie stawił.';
    default:
      return 'Status zaktualizowany.';
  }
}

const LOGO_ASPECT = 1645 / 478;

export function VisitDetailScreen({ sessionToken, appointment, onBack, onDone, onUnauthorized }: Props) {
  const [appt, setAppt] = useState<TodayAppointment>(appointment);
  const [submitting, setSubmitting] = useState<'start' | 'end' | 'no_show' | null>(null);
  const [successNewStatus, setSuccessNewStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const now = useTicker(1000);
  const expiredRef = useRef(false);
  const autoReturnRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (autoReturnRef.current) clearTimeout(autoReturnRef.current);
    };
  }, []);

  // Live countdown hits zero -> refetch this one appointment's authoritative
  // state instead of a stale "too early" screen sitting there forever.
  useEffect(() => {
    if (successNewStatus || expiredRef.current) return;
    if (appt.state === 'too_early' && appt.unlock_at && new Date(appt.unlock_at).getTime() - now <= 0) {
      expiredRef.current = true;
      (async () => {
        const result = await fetchAppointmentState(sessionToken, appt.appointment_id);
        if (!result.success) {
          if (result.error === 'unauthorized') onUnauthorized();
          return;
        }
        setAppt((prev) => ({ ...prev, ...result } as TodayAppointment));
      })();
    }
  }, [now, appt, successNewStatus, sessionToken, onUnauthorized]);

  const runAction = async (action: 'start' | 'end' | 'no_show') => {
    setSubmitting(action);
    setError(null);
    const result = await submitAppointmentAction(sessionToken, appt.appointment_id, action);
    setSubmitting(null);

    if (!result.success) {
      if (result.error === 'unauthorized') {
        onUnauthorized();
        return;
      }
      if (result.state) {
        // Server re-validation rejected it — adopt its authoritative state.
        setAppt((prev) => ({ ...prev, ...result, state: result.state as VisitState }) as TodayAppointment);
        setError(result.error ?? null);
        return;
      }
      setError('Coś poszło nie tak. Spróbuj ponownie.');
      return;
    }

    setSuccessNewStatus(result.new_status ?? '');
    autoReturnRef.current = setTimeout(onDone, 1500);
  };

  const handleNoShow = () => {
    Alert.alert('Potwierdź', 'Oznaczyć wizytę jako: klient się nie stawił?', [
      { text: 'Anuluj', style: 'cancel' },
      { text: 'Tak', style: 'destructive', onPress: () => runAction('no_show') },
    ]);
  };

  return (
    <ScreenCard>
      <View style={styles.headerRow}>
        <Image source={require('../../assets/logo.png')} style={styles.logoSmall} resizeMode="contain" />
        <Pressable onPress={onBack}>
          <Text style={styles.backLink}>← Dzisiejsze wizyty</Text>
        </Pressable>
      </View>

      {error && <Text style={styles.errorMsg}>{error}</Text>}

      {successNewStatus !== null && (
        <View>
          <Text style={styles.icon}>✅</Text>
          <Text style={styles.heading}>Status zaktualizowany</Text>
          <Text style={styles.message}>{successMessageFor(successNewStatus)}</Text>
          <Pressable
            onPress={onDone}
            style={({ pressed }) => [styles.secondaryButton, pressed && styles.secondaryButtonPressed]}
          >
            <Text style={styles.secondaryButtonText}>← Wróć do dzisiejszych wizyt</Text>
          </Pressable>
        </View>
      )}

      {successNewStatus === null && appt.state === 'too_early' && (
        <View>
          <Text style={styles.icon}>⏳</Text>
          <Text style={styles.heading}>Za wcześnie</Text>
          <Text style={styles.message}>
            Formularz odblokuje się automatycznie za{' '}
            <Text style={styles.messageBold}>
              {appt.unlock_at ? formatCountdown(new Date(appt.unlock_at).getTime() - now) : '—'}
            </Text>{' '}
            (20 minut przed wizytą).
          </Text>
        </View>
      )}

      {successNewStatus === null && appt.state === 'already_done' && (
        <View>
          <Text style={styles.icon}>✅</Text>
          <Text style={styles.heading}>Wizyta już zakończona</Text>
          <Text style={styles.message}>Ta wizyta ma już finalny status. Brak dostępnych akcji.</Text>
        </View>
      )}

      {successNewStatus === null && appt.state === 'wrong_status' && (
        <View>
          <Text style={styles.icon}>⚠️</Text>
          <Text style={styles.heading}>Nieprawidłowy status</Text>
          <Text style={styles.message}>Wizyta ma status, który nie pozwala na zmianę przez ten formularz.</Text>
        </View>
      )}

      {successNewStatus === null && (appt.state === 'start_visit' || appt.state === 'end_visit') && (
        <View>
          <Text style={styles.heading}>{appt.state === 'start_visit' ? 'Rozpocznij wizytę' : 'Zakończ wizytę'}</Text>
          <Text style={styles.subheading}>
            {appt.state === 'start_visit' ? 'Potwierdź rozpoczęcie wizyty.' : 'Potwierdź zakończenie wizyty.'}
          </Text>
          <View style={styles.detailsBlock}>
            <DetailRow label="Klient" value={appt.client_name} />
            <DetailRow label="Data" value={formatToday()} />
            <DetailRow label="Godzina" value={appt.start_time} />
          </View>
          <ConfirmButton
            label={appt.state === 'start_visit' ? 'Wizyta rozpoczęta' : 'Wizyta zakończona'}
            onPress={() => runAction(appt.state === 'start_visit' ? 'start' : 'end')}
            loading={submitting === 'start' || submitting === 'end'}
            disabled={submitting !== null}
          />
          {appt.state === 'start_visit' && appt.can_no_show && (
            <Pressable
              onPress={handleNoShow}
              disabled={submitting !== null}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.secondaryButtonPressed,
                submitting !== null && styles.secondaryButtonDisabled,
              ]}
            >
              <Text style={styles.secondaryButtonTextMuted}>Klient się nie stawił</Text>
            </Pressable>
          )}
        </View>
      )}
    </ScreenCard>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  logoSmall: {
    width: 22 * LOGO_ASPECT,
    height: 22,
  },
  backLink: {
    fontFamily: fonts.regular,
    fontSize: 13,
    color: colors.inkMuted,
  },
  icon: {
    fontSize: 32,
    marginBottom: 12,
  },
  heading: {
    fontFamily: fonts.semiBold,
    fontSize: 20,
    color: colors.ink,
    marginBottom: 8,
  },
  subheading: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.inkMuted,
    marginBottom: 24,
  },
  message: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.inkMuted,
    marginTop: 8,
  },
  messageBold: {
    fontFamily: fonts.semiBold,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
  },
  detailsBlock: {
    backgroundColor: colors.surface,
    borderRadius: 6,
    padding: 16,
    marginBottom: 24,
  },
  // .btn-refined-secondary (GUI-GOLDEN-BOOK.md §6): white fill, border token,
  // 2px radius; pressed mirrors the hover (border darkens to ink-muted, bg -> surface).
  secondaryButton: {
    marginTop: 12,
    width: '100%',
    paddingVertical: 14,
    borderRadius: radii.control,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBackground,
    alignItems: 'center',
  },
  secondaryButtonPressed: {
    borderColor: colors.inkMuted,
    backgroundColor: colors.surface,
  },
  secondaryButtonDisabled: {
    opacity: 0.6,
  },
  secondaryButtonText: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.ink,
  },
  secondaryButtonTextMuted: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.inkMuted,
  },
  errorMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.error,
    marginBottom: 16,
  },
});
