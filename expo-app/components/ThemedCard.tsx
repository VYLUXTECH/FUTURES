import { View, type ViewProps } from 'react-native'
import { useTheme } from '../contexts/ThemeContext'
import { BorderRadius } from '../constants/theme'

export function ThemedCard({ style, ...props }: ViewProps) {
  const { colors } = useTheme()
  return (
    <View
      style={[
        {
          backgroundColor: colors.card,
          borderRadius: BorderRadius.xl,
          borderWidth: 1,
          borderColor: colors.cardBorder,
          padding: 20,
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 10 },
          shadowOpacity: 0.4,
          shadowRadius: 30,
          elevation: 10,
        },
        style,
      ]}
      {...props}
    />
  )
}
