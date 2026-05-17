import { useState, useEffect, useRef, useCallback } from 'react'
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native'
import { router } from 'expo-router'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { ThemedCard } from '../components/ThemedCard'
import { PasswordInput } from '../components/PasswordInput'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'
import { supabase } from '../utils/supabase'
import { FontSize, Spacing, BorderRadius } from '../constants/theme'

type Step = 'email' | 'otp' | 'password'

export default function ForgotPasswordScreen() {
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [password, setPassword] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [loading, setLoading] = useState(false)
  const [otpTimer, setOtpTimer] = useState(300)
  const [verifyTimer, setVerifyTimer] = useState(300)
  const [verifyingOtp, setVerifyingOtp] = useState(false)

  const { colors, theme, toggleTheme } = useTheme()
  const { updatePassword } = useAuth()
  const { showToast } = useToast()
  const otpRefs = useRef<(TextInput | null)[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval>>()

  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  const startOtpTimer = useCallback(() => {
    setOtpTimer(300)
    setVerifyTimer(300)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setVerifyTimer(prev => {
        if (prev <= 1) { clearInterval(timerRef.current); timerRef.current = undefined; return 0 }
        return prev - 1
      })
      setOtpTimer(prev => {
        if (prev <= 1) { return 0 }
        return prev - 1
      })
    }, 1000)
  }, [])

  function handleOtpChange(text: string, index: number) {
    const digit = text.replace(/[^0-9]/g, '').slice(0, 1)
    setOtp(prev => {
      const next = [...prev]
      next[index] = digit
      return next
    })
    if (text && text.length > 1 && index === 0) {
      const pasted = text.replace(/[^0-9]/g, '').slice(0, 6).split('')
      setOtp(prev => {
        const next = [...prev]
        pasted.forEach((d, i) => { if (i < 6) next[i] = d })
        return next
      })
      const focusIndex = Math.min(pasted.length, 5)
      otpRefs.current[focusIndex]?.focus()
      return
    }
    if (digit && index < 5) otpRefs.current[index + 1]?.focus()
  }

  function handleOtpKeyPress(e: any, index: number) {
    if (e.nativeEvent.key === 'Backspace' && !otp[index] && index > 0) {
      setOtp(prev => { const next = [...prev]; next[index - 1] = ''; return next })
      otpRefs.current[index - 1]?.focus()
    }
  }

  async function handleSendCode() {
    if (!email) { showToast('Please enter a valid email', 'error'); return }
    setLoading(true)
    try {
      await supabase.auth.resetPasswordForEmail(email.trim())
      startOtpTimer()
      setStep('otp')
      setTimeout(() => otpRefs.current[0]?.focus(), 300)
      showToast('Code sent to your email!', 'success')
    } catch (e: any) {
      showToast(e.message || 'Failed to send code', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleResendCode() {
    try {
      await supabase.auth.resetPasswordForEmail(email.trim())
      startOtpTimer()
      showToast('New code sent!', 'success')
    } catch (e: any) {
      showToast(e.message || 'Failed to resend', 'error')
    }
  }

  async function handleVerifyCode() {
    const code = otp.join('')
    if (code.length < 6) { showToast('Enter the full 6-digit code', 'error'); return }
    setVerifyingOtp(true)
    try {
      const { error } = await supabase.auth.verifyOtp({ email: email.trim(), token: code, type: 'recovery' })
      if (error) throw error
      setStep('password')
      showToast('Code verified!', 'success')
    } catch (e: any) {
      showToast(e.message || 'Invalid code. Try again.', 'error')
      setOtp(['', '', '', '', '', ''])
      otpRefs.current[0]?.focus()
    } finally {
      setVerifyingOtp(false)
    }
  }

  async function handleUpdatePassword() {
    if (password.length < 6) { showToast('Password must be at least 6 characters', 'error'); return }
    if (password !== confirmPw) { showToast('Passwords do not match', 'error'); return }
    setLoading(true)
    try {
      await updatePassword(password)
      showToast('Password updated successfully!', 'success')
      router.replace('/mt5')
    } catch (e: any) {
      showToast(e.message || 'Failed to update password', 'error')
    } finally {
      setLoading(false)
    }
  }

  const stepDots: Step[] = ['email', 'otp', 'password']
  const isDark = colors.bg === '#000000'

  return (
    <ThemedView style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: colors.bg }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <ThemedText style={styles.backText}>← Back</ThemedText>
        </TouchableOpacity>
        <ThemedText heading style={styles.pageTitle}>Reset Password</ThemedText>
        <TouchableOpacity onPress={toggleTheme} style={[styles.themeBtn, { backgroundColor: colors.card, borderColor: colors.cardBorder }]}>
          <ThemedText style={{ fontSize: 16 }}>{isDark ? '☀️' : '🌙'}</ThemedText>
        </TouchableOpacity>
      </View>

      <View style={styles.content}>
        <ThemedCard>
          {/* Step Indicator */}
          <View style={styles.stepRow}>
            {stepDots.map((s, i) => (
              <View
                key={s}
                style={[
                  styles.stepDot,
                  { backgroundColor: stepDots.indexOf(step) >= i ? colors.primary : colors.border },
                  stepDots.indexOf(step) === i && styles.stepDotActive,
                ]}
              />
            ))}
          </View>

          {/* Step 1: Email */}
          {step === 'email' && (
            <View>
              <ThemedText muted style={styles.instruction}>
                Enter your email address. We'll send you a 6-digit code to reset your password.
              </ThemedText>
              <View style={styles.formGroup}>
                <ThemedText muted style={styles.label}>Email Address</ThemedText>
                <TextInput
                  placeholder="trader@example.com"
                  placeholderTextColor={colors.textMuted}
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoComplete="email"
                  style={[styles.input, { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }]}
                />
              </View>
              <TouchableOpacity
                style={[styles.btnPrimary, { backgroundColor: colors.primary, opacity: loading ? 0.6 : 1 }]}
                onPress={handleSendCode}
                disabled={loading}
              >
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md }}>
                  {loading ? 'Sending...' : 'Send Code'}
                </ThemedText>
              </TouchableOpacity>
            </View>
          )}

          {/* Step 2: OTP */}
          {step === 'otp' && (
            <View>
              <ThemedText muted style={styles.instruction}>
                We've sent a 6-digit code to{' '}
                <ThemedText style={{ fontWeight: '600', color: colors.text }}>{email}</ThemedText>.
                Please check your inbox and spam folder.
              </ThemedText>
              <View style={styles.otpRow}>
                {otp.map((digit, i) => (
                  <TextInput
                    key={i}
                    ref={ref => { otpRefs.current[i] = ref }}
                    value={digit}
                    onChangeText={t => handleOtpChange(t, i)}
                    onKeyPress={e => handleOtpKeyPress(e, i)}
                    keyboardType="number-pad"
                    maxLength={6}
                    selectTextOnFocus
                    style={[
                      styles.otpInput,
                      { backgroundColor: colors.inputBg, color: colors.text, borderColor: digit ? colors.primary : colors.border },
                    ]}
                  />
                ))}
              </View>
              <View style={styles.resendRow}>
                <ThemedText muted style={styles.timerText}>
                  Code expires in {Math.floor(verifyTimer / 60)}:{String(verifyTimer % 60).padStart(2, '0')}
                </ThemedText>
              </View>
              <View style={styles.resendRow}>
                <TouchableOpacity
                  disabled={otpTimer > 0}
                  onPress={handleResendCode}
                >
                  <ThemedText style={[styles.resendText, otpTimer > 0 && { color: colors.textMuted }]}>
                    Resend Code{otpTimer > 0 ? ` (${Math.floor(otpTimer / 60)}:${String(otpTimer % 60).padStart(2, '0')})` : ''}
                  </ThemedText>
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                style={[styles.btnPrimary, { backgroundColor: colors.primary, opacity: otp.join('').length < 6 || verifyingOtp ? 0.5 : 1 }]}
                onPress={handleVerifyCode}
                disabled={otp.join('').length < 6 || verifyingOtp}
              >
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md }}>
                  {verifyingOtp ? 'Verifying...' : 'Verify Code'}
                </ThemedText>
              </TouchableOpacity>
            </View>
          )}

          {/* Step 3: New Password */}
          {step === 'password' && (
            <View>
              <ThemedText muted style={styles.instruction}>
                Code verified. Enter your new password below.
              </ThemedText>
              <View style={styles.formGroup}>
                <ThemedText muted style={styles.label}>New Password</ThemedText>
                <PasswordInput
                  placeholder="Min. 6 characters"
                  placeholderTextColor={colors.textMuted}
                  value={password}
                  onChangeText={setPassword}
                  autoCapitalize="none"
                />
              </View>
              <View style={styles.formGroup}>
                <ThemedText muted style={styles.label}>Confirm New Password</ThemedText>
                <PasswordInput
                  placeholder="••••••••"
                  placeholderTextColor={colors.textMuted}
                  value={confirmPw}
                  onChangeText={setConfirmPw}
                  autoCapitalize="none"
                />
              </View>
              <TouchableOpacity
                style={[styles.btnPrimary, { backgroundColor: colors.primary, opacity: loading ? 0.6 : 1 }]}
                onPress={handleUpdatePassword}
                disabled={loading}
              >
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md }}>
                  {loading ? 'Updating...' : 'Update Password'}
                </ThemedText>
              </TouchableOpacity>
            </View>
          )}
        </ThemedCard>
      </View>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingTop: Platform.OS === 'web' ? Spacing.md : 56,
    paddingBottom: Spacing.sm,
  },
  backBtn: { padding: Spacing.xs },
  backText: { fontSize: FontSize.md, fontWeight: '600' },
  pageTitle: { fontSize: FontSize.lg, fontWeight: '700' },
  themeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: { flex: 1, justifyContent: 'center', padding: Spacing.md },
  stepRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: Spacing.lg },
  stepDot: { width: 8, height: 8, borderRadius: 4 },
  stepDotActive: { width: 24, borderRadius: 12 },
  instruction: { fontSize: FontSize.sm, lineHeight: 20, textAlign: 'center', marginBottom: Spacing.lg },
  formGroup: { marginBottom: Spacing.md },
  label: { fontSize: FontSize.xs, fontWeight: '500', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 },
  input: { height: 50, borderWidth: 1, borderRadius: BorderRadius.md, paddingHorizontal: Spacing.md, fontSize: FontSize.md },
  otpRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: Spacing.md },
  otpInput: { width: 44, height: 52, borderWidth: 2, borderRadius: BorderRadius.sm, textAlign: 'center', fontSize: FontSize.lg, fontWeight: '700' },
  resendRow: { alignItems: 'center', marginBottom: Spacing.sm },
  resendText: { fontSize: FontSize.sm, fontWeight: '600' },
  timerText: { fontSize: FontSize.xs },
  btnPrimary: { height: 52, borderRadius: BorderRadius.md, alignItems: 'center', justifyContent: 'center', marginTop: Spacing.xs },
})
