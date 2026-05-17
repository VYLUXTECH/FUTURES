import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { supabase } from '../utils/supabase'
import type { Session } from '@supabase/supabase-js'
import * as SecureStore from 'expo-secure-store'
import * as AuthSession from 'expo-auth-session'
import * as WebBrowser from 'expo-web-browser'
import { Platform } from 'react-native'

WebBrowser.maybeCompleteAuthSession()

const redirectUri = AuthSession.makeRedirectUri({ scheme: 'futures' })

type AuthContextType = {
  session: Session | null
  isLoading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  verifyOtp: (email: string, token: string) => Promise<void>
  resendOtp: (email: string) => Promise<void>
  signInWithGoogle: () => Promise<void>
  resetPassword: (email: string) => Promise<void>
  updatePassword: (password: string) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setIsLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session?.access_token) {
        const storage = Platform.OS === 'web' ? localStorage : SecureStore
        storage.setItem('futures_token', session.access_token)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    await supabase.auth.signOut()
    const storage = Platform.OS === 'web' ? localStorage : SecureStore
    storage === SecureStore
      ? SecureStore.deleteItemAsync('futures_token')
      : localStorage.removeItem('futures_token')
  }

  const verifyOtp = async (email: string, token: string) => {
    const { error } = await supabase.auth.verifyOtp({ email, token, type: 'email' })
    if (error) throw error
  }

  const resendOtp = async (email: string) => {
    await supabase.auth.signInWithOtp({ email })
  }

  const resetPassword = async (email: string) => {
    const redirectTo = Platform.OS === 'web'
      ? `${window.location.origin}/forgot-password`
      : 'futures://forgot-password'
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo })
    if (error) throw error
  }

  const updatePassword = async (password: string) => {
    const { error } = await supabase.auth.updateUser({ password })
    if (error) throw error
  }

  const signInWithGoogle = async () => {
    if (Platform.OS === 'web') {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: window.location.origin },
      })
      if (error) throw error
    } else {
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: redirectUri, skipBrowserRedirect: true },
      })
      if (error) throw error
      if (data?.url) {
        const result = await WebBrowser.openAuthSessionAsync(data.url, redirectUri)
        if (result.type === 'success') {
          supabase.auth.startAutoRefresh()
        }
      }
    }
  }

  return (
    <AuthContext.Provider value={{ session, isLoading, signIn, signUp, signOut, verifyOtp, resendOtp, signInWithGoogle, resetPassword, updatePassword }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
