import React from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { ScreenCard } from '../components/ScreenCard';
import { colors, fonts } from '../theme';
import { EmployeeSummary } from '../api/mobileApi';

interface Props {
  employees: EmployeeSummary[];
  loading: boolean;
  error: string | null;
  onSelect: (employee: EmployeeSummary) => void;
  onRetry: () => void;
}

export function EmployeePickerScreen({ employees, loading, error, onSelect, onRetry }: Props) {
  return (
    <ScreenCard>
      <Image source={require('../../assets/logo.png')} style={styles.logo} resizeMode="contain" />
      <Text style={styles.heading}>Kto się loguje?</Text>
      <Text style={styles.subheading}>Wybierz swoje imię z listy.</Text>

      {loading && (
        <View style={styles.centered}>
          <ActivityIndicator color={colors.textPrimary} />
        </View>
      )}

      {!loading && error && (
        <View>
          <Text style={styles.errorMsg}>{error}</Text>
          <Pressable onPress={onRetry}>
            <Text style={styles.retryLink}>Spróbuj ponownie</Text>
          </Pressable>
        </View>
      )}

      {!loading && !error && employees.length === 0 && (
        <Text style={styles.emptyMsg}>Brak aktywnych pracowników.</Text>
      )}

      {!loading && !error && employees.length > 0 && (
        <View style={styles.rowsWrapper}>
          {employees.map((emp) => (
            <Pressable
              key={emp.id}
              onPress={() => onSelect(emp)}
              style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
            >
              <Text style={styles.rowText}>{emp.name}</Text>
            </Pressable>
          ))}
        </View>
      )}
    </ScreenCard>
  );
}

const LOGO_ASPECT = 1645 / 478;

const styles = StyleSheet.create({
  logo: {
    width: 160,
    height: 160 / LOGO_ASPECT,
    marginBottom: 20,
  },
  heading: {
    fontFamily: fonts.semiBold,
    fontSize: 20,
    color: colors.textPrimary,
    marginBottom: 4,
  },
  subheading: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.textSecondary,
  },
  centered: {
    paddingVertical: 24,
    alignItems: 'center',
  },
  rowsWrapper: {
    marginTop: 16,
  },
  row: {
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: colors.rowBorder,
  },
  rowPressed: {
    backgroundColor: colors.detailsBlockBackground,
  },
  rowText: {
    fontFamily: fonts.medium,
    fontSize: 15,
    color: colors.textPrimary,
  },
  errorMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.error,
    marginTop: 12,
    marginBottom: 8,
  },
  retryLink: {
    fontFamily: fonts.medium,
    fontSize: 14,
    color: colors.textPrimary,
    textDecorationLine: 'underline',
  },
  emptyMsg: {
    fontFamily: fonts.regular,
    fontSize: 14,
    color: colors.textSecondary,
    paddingVertical: 24,
  },
});
