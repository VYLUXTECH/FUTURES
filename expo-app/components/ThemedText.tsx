import { Text, type TextProps } from 'react-native'
import { useTheme } from '../contexts/ThemeContext'

type ThemedTextProps = TextProps & {
  muted?: boolean
  heading?: boolean
}

export function ThemedText({ style, muted, heading, ...props }: ThemedTextProps) {
  const { colors } = useTheme()
  const color = muted ? colors.textMuted : heading ? colors.textHeading : colors.text
  return <Text style={[{ color }, style]} {...props} />
}
