import { useState } from 'react'
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Platform,
} from 'react-native'
import { router } from 'expo-router'
import { useFonts, DancingScript_700Bold } from '@expo-google-fonts/dancing-script'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { ThemedCard } from '../components/ThemedCard'
import { PasswordInput } from '../components/PasswordInput'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'
import { supabase } from '../utils/supabase'
import { FontSize, Spacing, BorderRadius } from '../constants/theme'

export default function SignScreen() {
  const [tab, setTab] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [loading, setLoading] = useState(false)

  const { colors, theme, toggleTheme } = useTheme()
  const { signIn, signUp, signInWithGoogle } = useAuth()
  const { showToast } = useToast()
  const [fontsLoaded] = useFonts({ DancingScript_700Bold })

  async function handleLogin() {
    if (!email || !password) {
      showToast('Please fill in all fields', 'error')
      return
    }
    setLoading(true)
    try {
      await signIn(email, password)
      showToast('Welcome back!', 'success')
      router.replace('/broker-connect')
    } catch (e: any) {
      showToast(e.message || 'Log in failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleSignUp() {
    if (!email || !password || !name) {
      showToast('Please fill in all fields', 'error')
      return
    }
    if (password !== confirmPassword) {
      showToast('Passwords do not match', 'error')
      return
    }
    if (!agreed) {
      showToast('You must agree to the Terms & Conditions', 'error')
      return
    }
    setLoading(true)
    try {
      await signUp(email, password)
      // Save display_name to profile
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        await supabase
          .from('profiles')
          .update({ display_name: name })
          .eq('id', user.id)
      }
      router.replace(`/verify?email=${encodeURIComponent(email)}`)
    } catch (e: any) {
      showToast(e.message || 'Sign up failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    backgroundColor: colors.inputBg,
    color: colors.text,
    borderColor: colors.border,
  }

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={[styles.scroll, { paddingBottom: Platform.OS === 'web' ? 40 : 60 }]} keyboardShouldPersistTaps="handled">
        <TouchableOpacity style={styles.themeToggle} onPress={toggleTheme} activeOpacity={0.7}>
          {theme === 'dark' ? (
            <ThemedText style={styles.themeIcon}>☀️</ThemedText>
          ) : (
            <ThemedText style={styles.themeIcon}>🌙</ThemedText>
          )}
        </TouchableOpacity>

        <ThemedCard style={styles.card}>
          <View style={styles.logoSection}>
            <ThemedText
              heading
              style={[
                styles.logo,
                fontsLoaded ? { fontFamily: 'DancingScript_700Bold' } : undefined,
              ]}
            >
              FUTURES
            </ThemedText>
            <ThemedText muted style={styles.motto}>
              PRICE IS THE ONLY INDICATOR
            </ThemedText>
          </View>

          <View style={[styles.pillTabs, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
            <TouchableOpacity
              style={[
                styles.pillTab,
                tab === 'login' && { backgroundColor: colors.card, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 2 },
              ]}
              onPress={() => setTab('login')}
            >
              <ThemedText
                style={[
                  styles.pillTabText,
                  tab === 'login' && { color: colors.text, fontWeight: '600' },
                  tab !== 'login' && { color: colors.textMuted },
                ]}
              >
                Log In
              </ThemedText>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.pillTab,
                tab === 'signup' && { backgroundColor: colors.card, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 2 },
              ]}
              onPress={() => setTab('signup')}
            >
              <ThemedText
                style={[
                  styles.pillTabText,
                  tab === 'signup' && { color: colors.text, fontWeight: '600' },
                  tab !== 'signup' && { color: colors.textMuted },
                ]}
              >
                Sign Up
              </ThemedText>
            </TouchableOpacity>
          </View>

          {tab === 'login' ? (
            <View style={styles.form}>
              <TextInput
                placeholder="trader@example.com"
                placeholderTextColor={colors.textMuted}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                style={[styles.input, inputStyle]}
              />
              <PasswordInput
                placeholder="Password"
                placeholderTextColor={colors.textMuted}
                value={password}
                onChangeText={setPassword}
                inputStyle={inputStyle}
              />
              <TouchableOpacity onPress={() => router.push('/forgot-password')}>
                <ThemedText muted style={styles.forgot}>Forgot password?</ThemedText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.button, { backgroundColor: colors.primary }]}
                onPress={handleLogin}
                disabled={loading}
              >
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', textAlign: 'center', fontSize: FontSize.md }}>
                  {loading ? 'Logging In...' : 'Log In'}
                </ThemedText>
              </TouchableOpacity>
              <View style={styles.divider}>
                <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
                <ThemedText muted style={styles.dividerText}>or continue with</ThemedText>
                <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
              </View>
              <TouchableOpacity
                style={[styles.socialBtn, { backgroundColor: colors.inputBg, borderColor: colors.border }]}
                onPress={signInWithGoogle}
                activeOpacity={0.7}
              >
                <ThemedText style={styles.googleIcon}>G</ThemedText>
                <ThemedText style={styles.socialBtnText}>Google</ThemedText>
              </TouchableOpacity>
              <View style={styles.formFooter}>
                <ThemedText muted style={styles.footerText}>
                  Don't have an account?
                </ThemedText>
              </View>
            </View>
          ) : (
            <View style={styles.form}>
              <TextInput
                placeholder="Future Trader"
                placeholderTextColor={colors.textMuted}
                value={name}
                onChangeText={setName}
                style={[styles.input, inputStyle]}
              />
              <TextInput
                placeholder="trader@example.com"
                placeholderTextColor={colors.textMuted}
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                style={[styles.input, inputStyle]}
              />
              <PasswordInput
                placeholder="Password"
                placeholderTextColor={colors.textMuted}
                value={password}
                onChangeText={setPassword}
                inputStyle={inputStyle}
              />
              <PasswordInput
                placeholder="Confirm Password"
                placeholderTextColor={colors.textMuted}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                inputStyle={inputStyle}
              />
              <TouchableOpacity style={styles.checkboxRow} onPress={() => setAgreed(!agreed)} activeOpacity={0.7}>
                <View
                  style={[
                    styles.checkbox,
                    {
                      borderColor: colors.border,
                      backgroundColor: agreed ? colors.primary : 'transparent',
                    },
                  ]}
                >
                  {agreed && <ThemedText style={[styles.checkmark, { color: colors.primaryFg }]}>✓</ThemedText>}
                </View>
                <ThemedText muted style={styles.checkboxLabel}>
                  I agree to the{' '}
                  <ThemedText style={styles.checkboxLink} onPress={() => router.push('/legal?tab=terms')}>
                    Terms & Conditions
                  </ThemedText>{' '}
                  and{' '}
                  <ThemedText style={styles.checkboxLink} onPress={() => router.push('/legal?tab=risk')}>
                    Risk Disclosure
                  </ThemedText>
                </ThemedText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.button, { backgroundColor: colors.primary }]}
                onPress={handleSignUp}
                disabled={loading}
              >
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', textAlign: 'center', fontSize: FontSize.md }}>
                  {loading ? 'Creating Account...' : 'Create Account'}
                </ThemedText>
              </TouchableOpacity>
              <View style={styles.divider}>
                <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
                <ThemedText muted style={styles.dividerText}>or continue with</ThemedText>
                <View style={[styles.dividerLine, { backgroundColor: colors.border }]} />
              </View>
              <TouchableOpacity
                style={[styles.socialBtn, { backgroundColor: colors.inputBg, borderColor: colors.border }]}
                onPress={signInWithGoogle}
                activeOpacity={0.7}
              >
                <ThemedText style={styles.googleIcon}>G</ThemedText>
                <ThemedText style={styles.socialBtnText}>Google</ThemedText>
              </TouchableOpacity>
            </View>
          )}
        </ThemedCard>
      </ScrollView>


    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: Spacing.md },
  card: { maxWidth: 440, width: '100%', alignSelf: 'center', borderRadius: 24, padding: 32 },
  themeToggle: {
    position: 'absolute',
    top: 24,
    right: 24,
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  themeIcon: { fontSize: 20 },
  logoSection: { alignItems: 'center', marginBottom: 24 },
  logo: { fontSize: 48, fontWeight: '700', marginBottom: 4 },
  motto: { fontSize: FontSize.xs, letterSpacing: 2.5, textTransform: 'uppercase' },
  pillTabs: {
    flexDirection: 'row',
    gap: 8,
    padding: 4,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    marginBottom: 16,
  },
  pillTab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 8,
  },
  pillTabText: { fontSize: FontSize.sm, fontWeight: '500' },
  form: { gap: 16 },
  input: {
    height: 50,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    fontSize: FontSize.md,
  },
  forgot: { textAlign: 'right', fontSize: FontSize.sm, marginTop: -8 },
  button: {
    height: 52,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    marginVertical: 4,
  },
  dividerLine: { flex: 1, height: 1 },
  dividerText: { fontSize: FontSize.xs, textTransform: 'uppercase', letterSpacing: 1 },
  socialBtn: {
    flexDirection: 'row',
    height: 48,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  googleIcon: { fontSize: 18, fontWeight: '700' },
  socialBtnText: { fontSize: FontSize.sm, fontWeight: '600' },
  formFooter: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
  },
  footerText: { fontSize: FontSize.sm },
  footerLink: { fontSize: FontSize.sm, fontWeight: '600' },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 4,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  checkmark: { fontSize: 11, fontWeight: 'bold', lineHeight: 14 },
  checkboxLabel: { fontSize: FontSize.xs, lineHeight: 18, flex: 1 },
  checkboxLink: { fontWeight: '600', textDecorationLine: 'underline' },
})
