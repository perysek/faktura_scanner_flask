import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { ConfirmButton } from '../components/ConfirmButton';
import { DetailRow } from '../components/DetailRow';
import { colors, fonts, spacing } from '../theme';
import {
  extractToken,
  fetchVisitStatus,
  submitVisitAction,
  VisitStatusResponse,
} from '../api/visitApi';

interface Props {
  initialToken?: string | null;
}

type Screen =
  | { kind: 'needs_token' }
  | { kind: 'loading' }
  | { kind: 'loaded'; data: VisitStatusResponse }
  | { kind: 'load_error'; message: string };

function describeError(code: string | undefined): string {
  switch (code) {
    case 'not_found':
      return 'Nie znaleziono wizyty dla tego linku.';
    case 'network_error':
      return 'Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.';
    default:
      return 'Coś poszło nie tak. Spróbuj ponownie.';
  }
}

export function VisitStatusScreen({ initialToken }: Props) {
  const [token, setToken] = useState<string | null>(initialToken ?? null);
  const [tokenInput, setTokenInput] = useState('');
  const [screen, setScreen] = useState<Screen>(
    initialToken ? { kind: 'loading' } : { kind: 'needs_token' }
  );
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async (t: string) => {
    setScreen({ kind: 'loading' });
    const data = await fetchVisitStatus(t);
    if (!data.success) {
      setScreen({ kind: 'load_error', message: describeError(data.error) });
      return;
    }
    setScreen({ kind: 'loaded', data });
  }, []);

  useEffect(() => {
    if (token) load(token);
  }, [token, load]);

  const handleTokenSubmit = () => {
    const extracted = extractToken(tokenInput);
    if (!extracted) return;
    setToken(extracted);
  };

  const handleAction = async (action: 'start' | 'end') => {
    if (!token) return;
    setSubmitting(true);
    const data = await submitVisitAction(token, action);
    setSubmitting(false);

    if (!data.success && data.state === undefined) {
      // Transport-level failure — the server never re-validated the action.
      setScreen({ kind: 'load_error', message: describeError(data.error) });
      return;
    }
    // Either the action succeeded (state: 'success') or the server's
    // re-validation rejected it (state carries the real current state + error).
    setScreen({ kind: 'loaded', data });
  };

  return (
    <KeyboardAvoidingView
      style={styles.page}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.card}>
          <Text style={styles.salonName}>MyWay Beauty Salon</Text>

          {screen.kind === 'needs_token' && (
            <TokenEntry value={tokenInput} onChangeText={setTokenInput} onSubmit={handleTokenSubmit} />
          )}

          {screen.kind === 'loading' && (
            <View style={styles.centered}>
              <ActivityIndicator color={colors.textPrimary} />
            </View>
          )}

          {screen.kind === 'load_error' && (
            <View>
              <Text style={styles.errorMsg}>{screen.message}</Text>
              {token && (
                <Pressable onPress={() => load(token)}>
                  <Text style={styles.retryLink}>Spróbuj ponownie</Text>
                </Pressable>
              )}
            </View>
          )}

          {screen.kind === 'loaded' && (
            <VisitContent
              data={screen.data}
              submitting={submitting}
              onStart={() => handleAction('start')}
              onEnd={() => handleAction('end')}
            />
          )}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function TokenEntry({
  value,
  onChangeText,
  onSubmit,
}: {
  value: string;
  onChangeText: (v: string) => void;
  onSubmit: () => void;
}) {
  return (
    <View>
      <Text style={styles.heading}>Wklej link z SMS-a</Text>
      <Text style={styles.subheading}>
        Otwórz aplikację przez link ze smsa albo wklej go poniżej.
      </Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder="https://www.my-way-solutions.com/visit/..."
        placeholderTextColor={colors.textMuted}
        autoCapitalize="none"
        autoCorrect={false}
        style={styles.tokenInput}
        onSubmitEditing={onSubmit}
        returnKeyType="go"
      />
      <ConfirmButton label="Sprawdź wizytę" onPress={onSubmit} disabled={value.trim().length === 0} />
    </View>
  );
}

function VisitContent({
  data,
  submitting,
  onStart,
  onEnd,
}: {
  data: VisitStatusResponse;
  submitting: boolean;
  onStart: () => void;
  onEnd: () => void;
}) {
  const appt = data.appointment;

  if (data.error) {
    return <Text style={styles.errorMsg}>{data.error}</Text>;
  }

  switch (data.state) {
    case 'too_early':
      return (
        <View>
          <Text style={styles.statusIcon}>⏳</Text>
          <Text style={styles.heading}>Za wcześnie</Text>
          <Text style={styles.statusMessage}>
            Formularz będzie dostępny
            {data.minutes_remaining !== undefined ? ` za ${data.minutes_remaining} min` : ''} (30
            minut przed wizytą).
          </Text>
        </View>
      );

    case 'already_done':
      return (
        <View>
          <Text style={styles.statusIcon}>✅</Text>
          <Text style={styles.heading}>Wizyta już zakończona</Text>
          <Text style={styles.statusMessage}>
            Ta wizyta ma już finalny status. Brak dostępnych akcji.
          </Text>
        </View>
      );

    case 'wrong_status':
      return (
        <View>
          <Text style={styles.statusIcon}>⚠️</Text>
          <Text style={styles.heading}>Nieprawidłowy status</Text>
          <Text style={styles.statusMessage}>
            Wizyta ma status, który nie pozwala na zmianę przez ten formularz.
          </Text>
        </View>
      );

    case 'success':
      return (
        <View>
          <Text style={styles.statusIcon}>✅</Text>
          <Text style={styles.heading}>Status zaktualizowany</Text>
          <Text style={styles.statusMessage}>
            Wizyta oznaczona jako{' '}
            <Text style={styles.statusMessageBold}>
              {data.new_status === 'in_progress' ? 'W trakcie' : 'Zakończona'}
            </Text>
            .
          </Text>
        </View>
      );

    case 'start_visit':
    case 'end_visit': {
      const isStart = data.state === 'start_visit';
      return (
        <View>
          <Text style={styles.heading}>{isStart ? 'Rozpocznij wizytę' : 'Zakończ wizytę'}</Text>
          <Text style={styles.subheading}>
            {isStart ? 'Potwierdź rozpoczęcie wizyty.' : 'Potwierdź zakończenie wizyty.'}
          </Text>
          {appt && (
            <View style={styles.detailsBlock}>
              <DetailRow label="Klient" value={`${appt.first_name} ${appt.last_name}`} />
              <DetailRow label="Data" value={appt.appointment_date} />
              <DetailRow label="Godzina" value={appt.start_time} />
            </View>
          )}
          <ConfirmButton
            label={isStart ? 'Wizyta rozpoczęta' : 'Wizyta zakończona'}
            onPress={isStart ? onStart : onEnd}
            loading={submitting}
          />
        </View>
      );
    }

    default:
      return null;
  }
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: colors.pageBackground,
  },
  scrollContent: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.screenPadding,
  },
  card: {
    width: '100%',
    maxWidth: spacing.cardMaxWidth,
    backgroundColor: colors.cardBackground,
    borderRadius: 8,
    paddingVertical: spacing.cardPaddingVertical,
    paddingHorizontal: spacing.cardPaddingHorizontal,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 20,
    elevation: 4,
  },
  centered: {
    alignItems: 'center',
    paddingVertical: 12,
  },
  salonName: {
    fontFamily: fonts.medium,
    fontSize: 12,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: colors.textMuted,
    marginBottom: 24,
  },
  heading: {
    fontFamily: fonts.semiBold,
    fontSize: 20,
    color: colors.textPrimary,
    marginBottom: 8,
  },
  subheading: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 24,
  },
  detailsBlock: {
    backgroundColor: colors.detailsBlockBackground,
    borderRadius: 6,
    padding: 16,
    marginBottom: 24,
  },
  statusIcon: {
    fontSize: 32,
    marginBottom: 12,
  },
  statusMessage: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 8,
  },
  statusMessageBold: {
    fontFamily: fonts.semiBold,
    color: colors.textPrimary,
  },
  errorMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.error,
    marginBottom: 16,
  },
  retryLink: {
    fontFamily: fonts.medium,
    fontSize: 14,
    color: colors.textPrimary,
    textDecorationLine: 'underline',
  },
  tokenInput: {
    fontFamily: fonts.regular,
    fontSize: 16,
    color: colors.textPrimary,
    backgroundColor: colors.detailsBlockBackground,
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 12,
    marginBottom: 16,
  },
});
