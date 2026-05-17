import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { Colors } from '../constants/theme'
import AsyncStorage from '@react-native-async-storage/async-storage'

type Theme = 'light' | 'dark'

type ThemeContextType = {
  theme: Theme
  colors: typeof Colors.light
  toggleTheme: () => void
}

const THEME_KEY = 'futures_theme'
const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>('dark')

  useEffect(() => {
    AsyncStorage.getItem(THEME_KEY).then(saved => {
      if (saved === 'light' || saved === 'dark') setTheme(saved)
    })
  }, [])

  const toggleTheme = () => {
    setTheme(prev => {
      const next = prev === 'dark' ? 'light' : 'dark'
      AsyncStorage.setItem(THEME_KEY, next)
      return next
    })
  }

  const value = {
    theme,
    colors: Colors[theme],
    toggleTheme,
  }

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
