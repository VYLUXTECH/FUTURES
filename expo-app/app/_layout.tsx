import { Slot } from 'expo-router'
import { Platform, View } from 'react-native'
import { AuthProvider } from '../contexts/AuthContext'
import { ThemeProvider } from '../contexts/ThemeContext'
import { ToastProvider } from '../components/Toast'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { useTheme } from '../contexts/ThemeContext'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import { ResponsiveContainer } from '../components/ResponsiveContainer'

function AppContent() {
  const { theme } = useTheme()
  return (
    <>
      <StatusBar style={theme === 'dark' ? 'light' : 'dark'} />
      <ResponsiveContainer>
        <Slot />
      </ResponsiveContainer>
    </>
  )
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <AppContent />
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  )
}
