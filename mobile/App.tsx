import * as Linking from 'expo-linking';
import { StatusBar } from 'expo-status-bar';
import { useMemo } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import {
  Inter_300Light,
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  useFonts,
} from '@expo-google-fonts/inter';
import { VisitStatusScreen } from './src/screens/VisitStatusScreen';
import { colors } from './src/theme';

function tokenFromUrl(url: string | null): string | null {
  if (!url) return null;
  const { path } = Linking.parse(url);
  if (!path) return null;
  const segments = path.split('/').filter(Boolean);
  const visitIndex = segments.indexOf('visit');
  if (visitIndex === -1 || visitIndex + 1 >= segments.length) return null;
  return segments[visitIndex + 1];
}

export default function App() {
  const [fontsLoaded] = useFonts({
    Inter_300Light,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
  });
  const url = Linking.useURL();
  const initialToken = useMemo(() => tokenFromUrl(url), [url]);

  if (!fontsLoaded) {
    return (
      <View style={[styles.splash, { backgroundColor: colors.pageBackground }]}>
        <ActivityIndicator color={colors.textPrimary} />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="dark" />
      {/* key forces a clean remount when a new SMS link opens the app
          while it's already showing a different visit */}
      <VisitStatusScreen key={initialToken ?? 'no-token'} initialToken={initialToken} />
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
