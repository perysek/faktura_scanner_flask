import React from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { colors, spacing } from '../theme';

interface Props {
  children: React.ReactNode;
  /** The today-list screen owns its own section padding and needs edge-to-edge rows. */
  noPadding?: boolean;
}

export function ScreenCard({ children, noPadding }: Props) {
  return (
    <KeyboardAvoidingView style={styles.page} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        <View style={[styles.card, noPadding && styles.cardNoPadding]}>{children}</View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
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
  cardNoPadding: {
    paddingVertical: 0,
    paddingHorizontal: 0,
    overflow: 'hidden',
  },
});
