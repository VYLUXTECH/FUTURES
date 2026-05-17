import { View, StyleSheet, Platform, type ViewProps } from 'react-native'

const MAX_WIDTH = 960

export function ResponsiveContainer({ style, children, ...props }: ViewProps) {
  return (
    <View style={styles.wrapper}>
      <View style={[styles.container, style]} {...props}>
        {children}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  wrapper: {
    flex: 1,
    alignItems: Platform.OS === 'web' ? 'center' : undefined,
    backgroundColor: 'transparent',
  },
  container: {
    flex: 1,
    width: '100%',
    maxWidth: Platform.OS === 'web' ? MAX_WIDTH : undefined,
  },
})
