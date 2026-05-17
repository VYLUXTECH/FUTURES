import { useState, useEffect, useRef } from 'react'
import { View, TouchableOpacity, StyleSheet, ActivityIndicator, Platform, Modal, BackHandler, TextInput } from 'react-native'
import { router } from 'expo-router'
import { WebView } from 'react-native-webview'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../components/Toast'
import { supabase } from '../utils/supabase'
import { Spacing, BorderRadius, FontSize } from '../constants/theme'

const HFM_REGISTER_URL = 'https://www.hfm.com/sv/en/?refid=30489955'
const HFM_LOGIN_URL = 'https://my.hfm.com/login'

type FlowStep = 'intro' | 'registering' | 'verify-email' | 'logging-in' | 'credentials'

export default function BrokerConnectScreen() {
  const [flowStep, setFlowStep] = useState<FlowStep>('intro')
  const [showWebView, setShowWebView] = useState(false)
  const [webViewUrl, setWebViewUrl] = useState('')
  const [webLoading, setWebLoading] = useState(true)
  const [checking, setChecking] = useState(true)
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [accountType, setAccountType] = useState<'Demo' | 'Real'>('Demo')
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState('')

  const webViewRef = useRef<WebView>(null)
  const { colors, theme } = useTheme()
  const { showToast } = useToast()
  const { session } = useAuth()

  useEffect(() => {
    if (!session) {
      router.replace('/sign')
      return
    }
    checkVerification()
  }, [session])

  useEffect(() => {
    if (Platform.OS === 'android') {
      const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
        if (showWebView && webViewRef.current) {
          webViewRef.current.goBack()
          return true
        }
        return false
      })
      return () => backHandler.remove()
    }
  }, [showWebView])

  async function checkVerification() {
    try {
      const { data: profile } = await supabase
        .from('profiles')
        .select('broker_verified, broker_name')
        .eq('id', session.user.id)
        .single()

      if (profile?.broker_verified) {
        router.replace('/(tabs)/dashboard')
        return
      }
    } catch {}
    setChecking(false)
  }

  function handleNavState(navState: any) {
    const url = navState.url || ''
    setWebViewUrl(url)

    if (flowStep === 'registering') {
      // Detect registration submitted — "check your email" or similar
      const submitted =
        url.includes('/verify') ||
        url.includes('/confirm') ||
        url.includes('/success') ||
        url.includes('/thank') ||
        url.includes('/check-email') ||
        navState.title?.toLowerCase().includes('verify') ||
        navState.title?.toLowerCase().includes('confirm') ||
        navState.title?.toLowerCase().includes('success')

      if (submitted && !url.includes('/new-live-account') && !url.includes('/register')) {
        setShowWebView(false)
        setFlowStep('verify-email')
        return
      }

      // Block login attempts during registration phase
      if (url.includes('/login') || url.includes('/myhf') || url.includes('/dashboard')) {
        webViewRef.current?.injectJavaScript(`window.location.href = '${HFM_REGISTER_URL}'; true;`)
        return
      }
    }

    if (flowStep === 'logging-in') {
      // Detect successful login — reached dashboard/myHF
      const reachedDashboard =
        url.includes('/myhf') ||
        url.includes('/dashboard') ||
        url.includes('/portal')

      if (reachedDashboard && !url.includes('/login')) {
        setShowWebView(false)
        setFlowStep('credentials')
        showToast('Account verified! Enter your MT5 credentials to activate the bot.', 'success')
        return
      }
    }
  }

  function openRegisterWebView() {
    setWebViewUrl(HFM_REGISTER_URL)
    setFlowStep('registering')
    setShowWebView(true)
  }

  function openLoginWebView() {
    setWebViewUrl(HFM_LOGIN_URL)
    setFlowStep('logging-in')
    setShowWebView(true)
  }

  async function handleVerifyCredentials() {
    if (!login || !password) {
      setError('Please enter your MT5 Login ID and Password')
      return
    }
    setVerifying(true)
    setError('')
    try {
      await supabase
        .from('mt5_credentials')
        .upsert({
          user_id: session.user.id,
          login: login.trim(),
          password,
          server: `HFM.com ${accountType} MT5`,
          updated_at: new Date().toISOString(),
        })

      await supabase
        .from('profiles')
        .update({ broker_verified: true, broker_name: 'HFM' })
        .eq('id', session.user.id)

      showToast('Verified! Redirecting to dashboard...', 'success')
      setTimeout(() => router.replace('/(tabs)/dashboard'), 1500)
    } catch (e: any) {
      setError(e.message || 'Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  if (checking) {
    return (
      <ThemedView style={styles.container}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
          <ThemedText muted style={{ marginTop: Spacing.md }}>Checking account...</ThemedText>
        </View>
      </ThemedView>
    )
  }

  if (flowStep === 'credentials') {
    return (
      <ThemedView style={styles.container}>
        <View style={styles.scroll}>
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.logoSection}>
              <ThemedText heading style={styles.logo}>FUTURES</ThemedText>
              <ThemedText muted style={styles.motto}>ACTIVATE TRADING BOT</ThemedText>
            </View>

            {error ? (
              <View style={[styles.msgBox, { backgroundColor: colors.dangerBg, borderColor: colors.dangerBorder }]}>
                <ThemedText style={[styles.msgText, { color: colors.danger }]}>{error}</ThemedText>
              </View>
            ) : null}

            <View style={[styles.successBox, { backgroundColor: colors.profitBg, borderColor: colors.profit }]}>
              <ThemedText style={{ color: colors.profit, fontWeight: '600', fontSize: FontSize.md }}>
                ✓ HFM Account Verified
              </ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.sm }}>
                Enter your MT5 login to activate the trading bot.
              </ThemedText>
            </View>

            <View style={styles.form}>
              <ThemedText muted style={styles.label}>MT5 Login ID</ThemedText>
              <View style={[styles.inputWrap, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
                <ThemedText style={[styles.inputIcon, { color: colors.textMuted }]}>#</ThemedText>
                <TextInput
                  placeholder="e.g. 50123456"
                  placeholderTextColor={colors.textMuted}
                  value={login}
                  onChangeText={setLogin}
                  keyboardType="number-pad"
                  style={{ flex: 1, backgroundColor: 'transparent', color: colors.text, fontSize: FontSize.md, padding: 0 }}
                />
              </View>

              <ThemedText muted style={styles.label}>MT5 Password</ThemedText>
              <View style={[styles.inputWrap, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
                <ThemedText style={[styles.inputIcon, { color: colors.textMuted }]}>🔒</ThemedText>
                <TextInput
                  placeholder="Your MT5 password"
                  placeholderTextColor={colors.textMuted}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                  style={{ flex: 1, backgroundColor: 'transparent', color: colors.text, fontSize: FontSize.md, padding: 0 }}
                />
              </View>

              <ThemedText muted style={styles.label}>Account Type</ThemedText>
              <View style={[styles.pillTabs, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
                <TouchableOpacity
                  style={[styles.pillTab, accountType === 'Demo' && { backgroundColor: colors.card }]}
                  onPress={() => setAccountType('Demo')}
                >
                  <ThemedText style={[styles.pillTabText, accountType === 'Demo' ? { color: colors.text, fontWeight: '600' } : { color: colors.textMuted }]}>
                    Demo
                  </ThemedText>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.pillTab, accountType === 'Real' && { backgroundColor: colors.card }]}
                  onPress={() => setAccountType('Real')}
                >
                  <ThemedText style={[styles.pillTabText, accountType === 'Real' ? { color: colors.text, fontWeight: '600' } : { color: colors.textMuted }]}>
                    Live
                  </ThemedText>
                </TouchableOpacity>
              </View>

              <TouchableOpacity
                style={[styles.button, { backgroundColor: colors.primary, opacity: verifying ? 0.6 : 1 }]}
                onPress={handleVerifyCredentials}
                disabled={verifying}
                activeOpacity={0.8}
              >
                {verifying ? (
                  <ActivityIndicator color={colors.primaryFg} size="small" />
                ) : (
                  <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md }}>
                    Activate Trading Bot
                  </ThemedText>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backLink}
                onPress={() => setFlowStep('intro')}
                activeOpacity={0.7}
              >
                <ThemedText muted style={styles.backText}>← Start over</ThemedText>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </ThemedView>
    )
  }

  if (flowStep === 'verify-email') {
    return (
      <ThemedView style={styles.container}>
        <View style={styles.scroll}>
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.logoSection}>
              <ThemedText heading style={styles.logo}>FUTURES</ThemedText>
              <ThemedText muted style={styles.motto}>VERIFY YOUR EMAIL</ThemedText>
            </View>

            <View style={[styles.stepBox, { backgroundColor: colors.inputBg, borderColor: colors.primary }]}>
              <View style={[styles.stepBadge, { backgroundColor: colors.primary }]}>
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.lg }}>✓</ThemedText>
              </View>
              <View style={styles.stepContent}>
                <ThemedText style={{ fontWeight: '600', fontSize: FontSize.md }}>
                  Registration Submitted
                </ThemedText>
                <ThemedText muted style={{ fontSize: FontSize.sm, marginTop: 4 }}>
                  HFM sent a verification email. Check your inbox and click the link.
                </ThemedText>
              </View>
            </View>

            <View style={[styles.stepBox, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
              <View style={[styles.stepBadge, { backgroundColor: colors.warning }]}>
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.lg }}>2</ThemedText>
              </View>
              <View style={styles.stepContent}>
                <ThemedText style={{ fontWeight: '600', fontSize: FontSize.md }}>
                  Come Back & Login
                </ThemedText>
                <ThemedText muted style={{ fontSize: FontSize.sm, marginTop: 4 }}>
                  After verifying, tap below to login to your HFM account.
                </ThemedText>
              </View>
            </View>

            <TouchableOpacity
              style={[styles.button, { backgroundColor: colors.primary }]}
              onPress={openLoginWebView}
              activeOpacity={0.8}
            >
              <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md }}>
                I've Verified — Login Now
              </ThemedText>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.backLink}
              onPress={() => setFlowStep('intro')}
              activeOpacity={0.7}
            >
              <ThemedText muted style={styles.backText}>← Start over</ThemedText>
            </TouchableOpacity>
          </View>
        </View>
      </ThemedView>
    )
  }

  return (
    <ThemedView style={styles.container}>
      <View style={styles.scroll}>
        <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.logoSection}>
            <ThemedText heading style={styles.logo}>FUTURES</ThemedText>
            <ThemedText muted style={styles.motto}>ACTIVATE YOUR ACCOUNT</ThemedText>
          </View>

          <View style={[styles.infoBox, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
            <View style={[styles.stepBadge, { backgroundColor: colors.primary }]}>
              <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.lg }}>1</ThemedText>
            </View>
            <View style={styles.stepContent}>
              <ThemedText style={{ fontWeight: '600', fontSize: FontSize.md }}>
                Create HFM Account
              </ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.sm, marginTop: 4 }}>
                Open a free account with our partner broker. Takes 2 minutes.
              </ThemedText>
            </View>
          </View>

          <View style={[styles.infoBox, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
            <View style={[styles.stepBadge, { backgroundColor: colors.warning }]}>
              <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.lg }}>2</ThemedText>
            </View>
            <View style={styles.stepContent}>
              <ThemedText style={{ fontWeight: '600', fontSize: FontSize.md }}>
                Verify Email & Login
              </ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.sm, marginTop: 4 }}>
                Check your email for the verification link, then login.
              </ThemedText>
            </View>
          </View>

          <View style={[styles.infoBox, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
            <View style={[styles.stepBadge, { backgroundColor: colors.profit }]}>
              <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.lg }}>3</ThemedText>
            </View>
            <View style={styles.stepContent}>
              <ThemedText style={{ fontWeight: '600', fontSize: FontSize.md }}>
                Enter MT5 Credentials
              </ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.sm, marginTop: 4 }}>
                After logging in, enter your MT5 login to activate the bot.
              </ThemedText>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.button, { backgroundColor: colors.primary }]}
            onPress={openRegisterWebView}
            activeOpacity={0.8}
          >
            <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md }}>
              Create HFM Account
            </ThemedText>
          </TouchableOpacity>

          <ThemedText muted style={styles.hint}>
            Already registered? Login below.
          </ThemedText>

          <TouchableOpacity
            style={[styles.button, { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.border }]}
            onPress={openLoginWebView}
            activeOpacity={0.8}
          >
            <ThemedText style={{ color: colors.text, fontWeight: '600', fontSize: FontSize.sm }}>
              I Already Have an HFM Account
            </ThemedText>
          </TouchableOpacity>
        </View>
      </View>

      <Modal visible={showWebView} animationType="slide" onRequestClose={() => setShowWebView(false)}>
        <View style={{ flex: 1 }}>
          <View style={[styles.webviewHeader, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
            <TouchableOpacity
              style={styles.closeBtn}
              onPress={() => { setShowWebView(false); setFlowStep('intro') }}
              activeOpacity={0.7}
            >
              <ThemedText style={{ color: colors.text, fontSize: FontSize.lg }}>✕</ThemedText>
            </TouchableOpacity>
            <ThemedText style={{ color: colors.text, fontWeight: '600', fontSize: FontSize.sm }} numberOfLines={1}>
              {flowStep === 'registering' ? 'Create HFM Account' : 'Login to HFM'}
            </ThemedText>
            <View style={{ width: 32 }} />
          </View>

          {webLoading && (
            <View style={[styles.loadingOverlay, { backgroundColor: colors.card }]}>
              <ActivityIndicator size="large" color={colors.primary} />
              <ThemedText muted style={{ marginTop: Spacing.md }}>Loading...</ThemedText>
            </View>
          )}

          <WebView
            ref={webViewRef}
            source={{ uri: webViewUrl }}
            onNavigationStateChange={handleNavState}
            onLoadStart={() => setWebLoading(true)}
            onLoadEnd={() => setWebLoading(false)}
            style={{ flex: 1 }}
            javaScriptEnabled
            domStorageEnabled
            startInLoadingState
            sharedCookiesEnabled
            thirdPartyCookiesEnabled
          />
        </View>
      </Modal>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flex: 1, padding: Spacing.md },
  card: {
    borderRadius: 24, borderWidth: 1, padding: Spacing.lg, gap: Spacing.lg,
    maxWidth: 440, width: '100%', alignSelf: 'center',
  },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  logoSection: { alignItems: 'center' },
  logo: { fontSize: 48, fontWeight: '700' },
  motto: { fontSize: FontSize.xs, letterSpacing: 2.5, textTransform: 'uppercase' },
  infoBox: {
    flexDirection: 'row', alignItems: 'center', padding: Spacing.md,
    borderRadius: BorderRadius.md, borderWidth: 1, gap: Spacing.md,
  },
  stepBox: {
    flexDirection: 'row', alignItems: 'center', padding: Spacing.md,
    borderRadius: BorderRadius.md, borderWidth: 1, gap: Spacing.md,
  },
  stepBadge: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
  },
  stepContent: { flex: 1 },
  button: {
    height: 52, borderRadius: BorderRadius.md,
    alignItems: 'center', justifyContent: 'center',
  },
  hint: { fontSize: FontSize.xs, textAlign: 'center' },
  form: { gap: Spacing.md },
  label: { fontSize: FontSize.xs, fontWeight: '500' },
  inputWrap: {
    flexDirection: 'row', alignItems: 'center', height: 50,
    borderWidth: 1, borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md, gap: Spacing.sm,
  },
  inputIcon: { fontSize: FontSize.md },
  pillTabs: {
    flexDirection: 'row', gap: 8, padding: 4,
    borderRadius: BorderRadius.md, borderWidth: 1,
  },
  pillTab: {
    flex: 1, paddingVertical: 12, alignItems: 'center',
    borderRadius: 8,
  },
  pillTabText: { fontSize: FontSize.sm, fontWeight: '500' },
  msgBox: {
    padding: Spacing.sm + 2, borderRadius: BorderRadius.md,
    borderWidth: 1, alignItems: 'center',
  },
  msgText: { fontWeight: '500', fontSize: FontSize.sm, textAlign: 'center' },
  successBox: {
    padding: Spacing.md, borderRadius: BorderRadius.md,
    borderWidth: 1, alignItems: 'center', gap: 4,
  },
  backLink: { alignItems: 'center', paddingVertical: Spacing.sm },
  backText: { fontSize: FontSize.sm, fontWeight: '500' },
  webviewHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.md, borderBottomWidth: 1,
  },
  closeBtn: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  loadingOverlay: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    alignItems: 'center', justifyContent: 'center', zIndex: 10,
  },
})
