import { View, type ViewProps } from 'react-native'
import { useTheme } from '../contexts/ThemeContext'

export function ThemedView({ style, ...props }: ViewProps) {
  const { colors } = useTheme()
  return <View style={[{ backgroundColor: colors.bg }, style]} {...props} />
}
