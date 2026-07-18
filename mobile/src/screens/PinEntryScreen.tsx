import React, { useState } from 'react';
import { Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { ScreenCard } from '../components/ScreenCard';
import { ConfirmButton } from '../components/ConfirmButton';
import { colors, fonts, radii } from '../theme';
import { EmployeeSummary, submitPin } from '../api/mobileApi';
import { StoredSession } from '../storage/session';

interface Props {
  employee: EmployeeSummary;
  onSuccess: (session: StoredSession) => void;
  onBack: () => void;
}

function describeError(code: string | undefined): string {
  switch (code) {
    case 'wrong_pin':
      return 'Nieprawidłowy PIN.';
    case 'invalid_pin_format':
      return 'PIN musi mieć od 4 do 6 cyfr.';
    case 'not_found':
      return 'Nie znaleziono pracownika — odśwież listę.';
    case 'network_error':
      return 'Brak połączenia z serwerem.';
    default:
      return 'Coś poszło nie tak. Spróbuj ponownie.';
  }
}

export function PinEntryScreen({ employee, onSuccess, onBack }: Props) {
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isNewPin = !employee.has_pin;
  const pinValid = pin.length >= 4;
  const mismatch = isNewPin && confirmPin.length >= 4 && pin !== confirmPin;
  const canSubmit = pinValid && (!isNewPin || (confirmPin.length >= 4 && pin === confirmPin));

  const handleSubmit = async () => {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    const result = await submitPin(employee.id, pin);
    setSubmitting(false);
    if (!result.success || !result.session_token) {
      setError(describeError(result.error));
      return;
    }
    onSuccess({
      employeeId: employee.id,
      employeeName: employee.name,
      sessionToken: result.session_token,
    });
  };

  return (
    <ScreenCard>
      <View style={styles.headerRow}>
        <Image source={require('../../assets/logo.png')} style={styles.logoSmall} resizeMode="contain" />
        <Pressable onPress={onBack}>
          <Text style={styles.backLink}>← Wybierz inną osobę</Text>
        </Pressable>
      </View>

      <Text style={styles.heading}>{isNewPin ? 'Ustaw PIN' : 'Wprowadź PIN'}</Text>
      <Text style={styles.subheading}>
        {isNewPin
          ? `Cześć, ${employee.name}. Ustaw swój PIN (4–6 cyfr) — będziesz go używać przy każdym logowaniu.`
          : `Cześć, ${employee.name}. Wprowadź swój PIN.`}
      </Text>

      {error && <Text style={styles.errorMsg}>{error}</Text>}

      <TextInput
        value={pin}
        onChangeText={(v) => setPin(v.replace(/\D/g, '').slice(0, 6))}
        placeholder="PIN"
        placeholderTextColor={colors.inkSubtle}
        keyboardType="number-pad"
        secureTextEntry
        style={styles.pinInput}
        autoFocus
        returnKeyType={isNewPin ? 'next' : 'go'}
        onSubmitEditing={isNewPin ? undefined : handleSubmit}
      />

      {isNewPin && (
        <TextInput
          value={confirmPin}
          onChangeText={(v) => setConfirmPin(v.replace(/\D/g, '').slice(0, 6))}
          placeholder="Powtórz PIN"
          placeholderTextColor={colors.inkSubtle}
          keyboardType="number-pad"
          secureTextEntry
          style={styles.pinInput}
          onSubmitEditing={handleSubmit}
          returnKeyType="go"
        />
      )}

      {mismatch && <Text style={styles.hintMsg}>PIN-y się nie zgadzają.</Text>}

      <ConfirmButton
        label={isNewPin ? 'Ustaw PIN i kontynuuj' : 'Zaloguj'}
        onPress={handleSubmit}
        loading={submitting}
        disabled={!canSubmit}
      />
    </ScreenCard>
  );
}

const LOGO_ASPECT = 1645 / 478;

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
  pinInput: {
    fontFamily: fonts.light,
    fontSize: 20,
    letterSpacing: 4,
    color: colors.ink,
    backgroundColor: colors.cardBackground,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.control,
    paddingHorizontal: 16,
    paddingVertical: 14,
    marginBottom: 12,
    textAlign: 'center',
  },
  hintMsg: {
    fontFamily: fonts.regular,
    fontSize: 13,
    color: colors.error,
    marginBottom: 12,
  },
  errorMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.error,
    marginBottom: 16,
  },
});
