import { useState, createContext, useContext, useCallback, type ReactNode } from 'react'
import { Animated, StyleSheet, Text } from 'react-native'
import { useTheme } from '../contexts/ThemeContext'
import { FontSize, BorderRadius, Spacing } from '../constants/theme'

type ToastType = 'success' | 'error' | 'info'

type ToastContextType = {
  showToast: (msg: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const { colors } = useTheme()
  const [message, setMessage] = useState('')
  const [type, setType] = useState<ToastType>('info')
  const [visible, setVisible] = useState(false)

  const showToast = useCallback((msg: string, t: ToastType = 'info') => {
    setMessage(msg)
    setType(t)
    setVisible(true)
    setTimeout(() => setVisible(false), 3000)
  }, [])

  const bgColor =
    type === 'success' ? colors.profit :
    type === 'error' ? colors.loss :
    colors.primary

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {visible && (
        <Animated.View style={[styles.toast, { backgroundColor: bgColor }]}>
          <Text style={styles.toastText}>{message}</Text>
        </Animated.View>
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

const styles = StyleSheet.create({
  toast: {
    position: 'absolute',
    bottom: 100,
    left: 20,
    right: 20,
    paddingVertical: Spacing.sm + 2,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    zIndex: 9999,
  },
  toastText: {
    color: '#FFFFFF',
    fontSize: FontSize.sm,
    fontWeight: '600',
  },
})
