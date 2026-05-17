import { useState, useRef, useEffect } from 'react'
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Keyboard,
  Platform,
} from 'react-native'
import { router, useLocalSearchParams } from 'expo-router'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { ThemedCard } from '../components/ThemedCard'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'
import { FontSize, Spacing, BorderRadius } from '../constants/theme'

export default function VerifyScreen() {
  const { email } = useLocalSearchParams<{ email: string }>()
  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [timer, setTimer] = useState(60)
  const [loading, setLoading] = useState(false)

  const { colors } = useTheme()
  const { verifyOtp, resendOtp } = useAuth()
  const { showToast } = useToast()
  const otpRefs = useRef<(TextInput | null)[]>([])

  useEffect(() => {
    if (!email) {
      router.replace('/sign')
      return
    }
    startTimer()
    setTimeout(() => otpRefs.current[0]?.focus(), 400)
  }, [])

  useEffect(() => {
    if (otp.every(d => d)) {
      handleVerify()
    }
  }, [otp])

  function startTimer() {
    setTimer(60)
    const interval = setInterval(() => {
      setTimer(prev => {
        if (prev <= 1) { clearInterval(interval); return 0 }
        return prev - 1
      })
    }, 1000)
  }

  function handleOtpChange(text: string, index: number) {
    const digit = text.replace(/[^0-9]/g, '').slice(0, 1)
    const newOtp = [...otp]
    newOtp[index] = digit
    setOtp(newOtp)
    if (digit && index < 5) otpRefs.current[index + 1]?.focus()
  }

  function handleOtpKeyPress(e: any, index: number) {
    if (e.nativeEvent.key === 'Backspace' && !otp[index] && index > 0) {
      const newOtp = [...otp]
      newOtp[index - 1] = ''
      setOtp(newOtp)
      otpRefs.current[index - 1]?.focus()
    }
  }

  function handleOtpPaste(e: any) {
    const text = e.clipboardData?.getData('text') || ''
    const digits = text.replace(/[^0-9]/g, '').slice(0, 6).split('')
    if (digits.length > 0) {
      const newOtp = [...otp]
      digits.forEach((d: string, i: number) => { newOtp[i] = d })
      setOtp(newOtp)
      const focusIndex = Math.min(digits.length, 5)
      otpRefs.current[focusIndex]?.focus()
    }
  }

  async function handleVerify() {
    const code = otp.join('')
    if (code.length < 6) return
    Keyboard.dismiss()
    setLoading(true)
    try {
      await verifyOtp(email!, code)
      showToast('Email verified!', 'success')
      setTimeout(() => router.replace('/broker-connect'), 1200)
    } catch (e: any) {
      showToast(e.message || 'Invalid code. Try again.', 'error')
      setOtp(['', '', '', '', '', ''])
      otpRefs.current[0]?.focus()
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    if (timer > 0) return
    try {
      await resendOtp(email!)
      showToast('New code sent!', 'success')
      startTimer()
    } catch (e: any) {
      showToast(e.message || 'Failed to resend', 'error')
    }
  }

  return (
    <ThemedView style={styles.container}>
      <View style={styles.content}>
        <ThemedCard>
          <View style={styles.stepRow}>
            {[0, 1, 2, 3, 4, 5].map(i => (
              <View
                key={i}
                style={[
                  styles.stepDot,
                  otp.every(d => d) && i >= 3
                    ? { backgroundColor: colors.primary, width: i === 3 ? 24 : 8, borderRadius: i === 3 ? 12 : 4 }
                    : otp[i] || (i > 0 && otp[i - 1])
                    ? { backgroundColor: colors.primary, width: 8, borderRadius: 4 }
                    : { backgroundColor: colors.textMuted, width: 8, borderRadius: 4 },
                ]}
              />
            ))}
          </View>

          <View style={styles.form}>
            <ThemedText heading style={styles.title}>Verify your email</ThemedText>
            <ThemedText muted style={styles.subtitle}>
              Enter the 6-digit verification code sent to{'\n'}{email}
            </ThemedText>

            <View style={styles.otpRow}>
              {otp.map((digit, i) => (
                <TextInput
                  key={i}
                  ref={ref => { otpRefs.current[i] = ref }}
                  value={digit}
                  onChangeText={t => handleOtpChange(t, i)}
                  onKeyPress={e => handleOtpKeyPress(e, i)}
                  {...(Platform.OS === 'web' ? { onPaste: handleOtpPaste } : {})}
                  keyboardType="number-pad"
                  textContentType="oneTimeCode"
                  maxLength={1}
                  style={[
                    styles.otpInput,
                    {
                      backgroundColor: colors.inputBg,
                      color: colors.text,
                      borderColor: digit ? colors.primary : colors.border,
                    },
                  ]}
                />
              ))}
            </View>

            <TouchableOpacity
              style={[styles.button, { backgroundColor: colors.primary, opacity: otp.every(d => d) ? 1 : 0.5 }]}
              onPress={handleVerify}
              disabled={loading || !otp.every(d => d)}
            >
              <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', textAlign: 'center', fontSize: FontSize.md }}>
                {loading ? 'Verifying...' : 'Verify Email'}
              </ThemedText>
            </TouchableOpacity>

            <TouchableOpacity disabled={timer > 0} onPress={handleResend} style={styles.resendRow}>
              <ThemedText
                muted
                style={[styles.resendText, timer > 0 && { color: colors.textMuted }]}
              >
                {timer > 0 ? `Resend code in ${timer}s` : 'Resend verification code'}
              </ThemedText>
            </TouchableOpacity>
          </View>
        </ThemedCard>
      </View>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { flex: 1, justifyContent: 'center', padding: Spacing.md },
  stepRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: Spacing.lg },
  stepDot: { height: 8 },
  form: { gap: Spacing.md },
  title: { fontSize: FontSize.lg, fontWeight: '700' },
  subtitle: { fontSize: FontSize.sm, lineHeight: 20 },
  otpRow: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginVertical: Spacing.sm },
  otpInput: { width: 44, height: 52, borderWidth: 1.5, borderRadius: BorderRadius.sm, textAlign: 'center', fontSize: FontSize.lg, fontWeight: '700' },
  button: { height: 52, borderRadius: BorderRadius.md, alignItems: 'center', justifyContent: 'center', marginTop: Spacing.sm },
  resendRow: { alignItems: 'center', paddingVertical: Spacing.sm },
  resendText: { fontSize: FontSize.sm, fontWeight: '600' },
})
