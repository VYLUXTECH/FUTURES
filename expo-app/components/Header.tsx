import { View, TouchableOpacity, Pressable, Platform } from 'react-native'
import { useTheme } from '../contexts/ThemeContext'
import { ThemedText } from './ThemedText'
import { Spacing, FontSize, BorderRadius } from '../constants/theme'
import { router } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

type HeaderProps = {
  title: string
  showBack?: boolean
}

export function Header({ title, showBack }: HeaderProps) {
  const { colors, theme, toggleTheme } = useTheme()
  const insets = useSafeAreaInsets()

  return (
    <View
      style={{
        paddingTop: insets.top + Spacing.sm,
        paddingBottom: Spacing.sm,
        paddingHorizontal: Spacing.md,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: colors.bg,
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.sm }}>
        {showBack && (
          <TouchableOpacity onPress={() => router.back()} style={{ padding: Spacing.xs }}>
            <ThemedText style={{ fontSize: FontSize.lg }}>{'←'}</ThemedText>
          </TouchableOpacity>
        )}
        <ThemedText heading style={{ fontSize: FontSize.lg, fontWeight: '600' }}>
          {title}
        </ThemedText>
      </View>

      <Pressable
        onPress={toggleTheme}
        style={{
          width: 36,
          height: 36,
          borderRadius: BorderRadius.full,
          backgroundColor: colors.card,
          borderWidth: 1,
          borderColor: colors.cardBorder,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <ThemedText style={{ fontSize: 16 }}>
          {theme === 'dark' ? '☀️' : '🌙'}
        </ThemedText>
      </Pressable>
    </View>
  )
}
