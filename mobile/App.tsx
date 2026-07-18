import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import {
  Inter_300Light,
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  useFonts,
} from '@expo-google-fonts/inter';
import { EmployeePickerScreen } from './src/screens/EmployeePickerScreen';
import { PinEntryScreen } from './src/screens/PinEntryScreen';
import { TodayListScreen } from './src/screens/TodayListScreen';
import { VisitDetailScreen } from './src/screens/VisitDetailScreen';
import { EmployeeSummary, TodayAppointment, fetchEmployees } from './src/api/mobileApi';
import { StoredSession, clearSession, loadSession, saveSession } from './src/storage/session';
import { colors } from './src/theme';

type Screen =
  | { kind: 'bootstrapping' }
  | { kind: 'picker' }
  | { kind: 'pin'; employee: EmployeeSummary }
  | { kind: 'today' }
  | { kind: 'detail'; appointment: TodayAppointment };

export default function App() {
  const [fontsLoaded] = useFonts({
    Inter_300Light,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
  });

  const [screen, setScreen] = useState<Screen>({ kind: 'bootstrapping' });
  const [session, setSession] = useState<StoredSession | null>(null);
  const [employees, setEmployees] = useState<EmployeeSummary[]>([]);
  const [employeesLoading, setEmployeesLoading] = useState(false);
  const [employeesError, setEmployeesError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const loadEmployees = useCallback(async () => {
    setEmployeesLoading(true);
    setEmployeesError(null);
    const result = await fetchEmployees();
    setEmployeesLoading(false);
    if (!result.success) {
      setEmployeesError(
        result.error === 'network_error' ? 'Brak połączenia z serwerem.' : 'Coś poszło nie tak.'
      );
      return;
    }
    setEmployees(result.employees);
  }, []);

  const goToPicker = useCallback(() => {
    setSession(null);
    setScreen({ kind: 'picker' });
    loadEmployees();
  }, [loadEmployees]);

  // On launch: resume a saved session straight to the today-list, otherwise
  // load the employee picker.
  useEffect(() => {
    (async () => {
      const stored = await loadSession();
      if (stored) {
        setSession(stored);
        setScreen({ kind: 'today' });
        return;
      }
      goToPicker();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUnauthorized = useCallback(async () => {
    await clearSession();
    goToPicker();
  }, [goToPicker]);

  if (!fontsLoaded) {
    return (
      <View style={[styles.splash, { backgroundColor: colors.surfaceWarm }]}>
        <ActivityIndicator color={colors.ink} />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="dark" />

      {screen.kind === 'bootstrapping' && (
        <View style={[styles.splash, { backgroundColor: colors.surfaceWarm }]}>
          <ActivityIndicator color={colors.ink} />
        </View>
      )}

      {screen.kind === 'picker' && (
        <EmployeePickerScreen
          employees={employees}
          loading={employeesLoading}
          error={employeesError}
          onSelect={(employee) => setScreen({ kind: 'pin', employee })}
          onRetry={loadEmployees}
        />
      )}

      {screen.kind === 'pin' && (
        <PinEntryScreen
          employee={screen.employee}
          onBack={() => setScreen({ kind: 'picker' })}
          onSuccess={async (newSession) => {
            await saveSession(newSession);
            setSession(newSession);
            setScreen({ kind: 'today' });
          }}
        />
      )}

      {screen.kind === 'today' && session && (
        <TodayListScreen
          sessionToken={session.sessionToken}
          employeeName={session.employeeName}
          refreshKey={refreshKey}
          onOpenAppointment={(appointment) => setScreen({ kind: 'detail', appointment })}
          onSwitchEmployee={async () => {
            await clearSession();
            goToPicker();
          }}
          onUnauthorized={handleUnauthorized}
        />
      )}

      {screen.kind === 'detail' && session && (
        <VisitDetailScreen
          sessionToken={session.sessionToken}
          appointment={screen.appointment}
          onBack={() => setScreen({ kind: 'today' })}
          onDone={() => {
            setRefreshKey((k) => k + 1);
            setScreen({ kind: 'today' });
          }}
          onUnauthorized={handleUnauthorized}
        />
      )}
    </>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
