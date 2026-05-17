import { useState, useEffect } from 'react'
import { View, TextInput, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator } from 'react-native'
import { router } from 'expo-router'
import { useFonts, DancingScript_700Bold } from '@expo-google-fonts/dancing-script'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { ThemedCard } from '../components/ThemedCard'
import { PasswordInput } from '../components/PasswordInput'
import { useTheme } from '../contexts/ThemeContext'
import { useToast } from '../components/Toast'
import { useAuth } from '../contexts/AuthContext'
import { supabase } from '../utils/supabase'
import { FontSize, Spacing, BorderRadius } from '../constants/theme'

export default function MT5Screen() {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [accountType, setAccountType] = useState<'Demo' | 'Real'>('Demo')
  const [showInstructions, setShowInstructions] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const { colors, theme, toggleTheme } = useTheme()
  const { showToast } = useToast()
  const { session } = useAuth()
  const [fontsLoaded] = useFonts({ DancingScript_700Bold })

  useEffect(() => {
    if (!session) router.replace('/sign')
    else checkVerified()
  }, [session])

  async function checkVerified() {
    try {
      const { data: profile } = await supabase
        .from('profiles')
        .select('broker_verified')
        .eq('id', session.user.id)
        .single()
      if (!profile?.broker_verified) {
        router.replace('/broker-connect')
      }
    } catch {}
  }

  async function handleSave() {
    if (!login || !password) {
      setError('Please fill in all fields')
      return
    }
    setLoading(true)
    setError('')
    setSaved(false)
    try {
      const { data: { user }, error: userError } = await supabase.auth.getUser()
      if (userError || !user) throw new Error('Not authenticated')

      const { error: dbError } = await supabase
        .from('mt5_credentials')
        .upsert({
          user_id: user.id,
          login: login.trim(),
          password: password,
          server: `HFM.com ${accountType} MT5`,
          updated_at: new Date().toISOString(),
        })
      if (dbError) throw dbError

      setSaved(true)
      showToast('Credentials saved! Set account type in Dashboard', 'success')
      setTimeout(() => router.push('/notifications'), 1500)
    } catch (e: any) {
      setError(e.message || 'Failed to save')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
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

          {error ? (
            <View style={[styles.msgBox, { backgroundColor: colors.dangerBg, borderColor: colors.dangerBorder }]}>
              <ThemedText style={[styles.msgText, { color: colors.danger }]}>{error}</ThemedText>
            </View>
          ) : null}

          {saved ? (
            <View style={[styles.msgBox, { backgroundColor: colors.inputBg, borderColor: colors.profit }]}>
              <ThemedText style={[styles.msgText, { color: colors.profit, fontWeight: '700' }]}>
                ✓ Credentials saved!
              </ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.xs }}>
                Configure your broker in Dashboard → Settings
              </ThemedText>
            </View>
          ) : null}

          <View style={styles.form}>
            <TextInput
              placeholder="MT5 Login ID"
              placeholderTextColor={colors.textMuted}
              value={login}
              onChangeText={setLogin}
              keyboardType="number-pad"
              style={[styles.input, { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }]}
            />

            <PasswordInput
              placeholder="MT5 Password"
              placeholderTextColor={colors.textMuted}
              value={password}
              onChangeText={setPassword}
              inputStyle={{ backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }}
            />

            <ThemedText muted style={styles.label}>Account Type</ThemedText>
            <View style={[styles.pillTabs, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
              <TouchableOpacity
                style={[
                  styles.pillTab,
                  accountType === 'Demo' && { backgroundColor: colors.card },
                ]}
                onPress={() => setAccountType('Demo')}
              >
                <ThemedText
                  style={[
                    styles.pillTabText,
                    accountType === 'Demo' ? { color: colors.text, fontWeight: '600' } : { color: colors.textMuted },
                  ]}
                >
                  Demo
                </ThemedText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.pillTab,
                  accountType === 'Real' && { backgroundColor: colors.card },
                ]}
                onPress={() => setAccountType('Real')}
              >
                <ThemedText
                  style={[
                    styles.pillTabText,
                    accountType === 'Real' ? { color: colors.text, fontWeight: '600' } : { color: colors.textMuted },
                  ]}
                >
                  Live
                </ThemedText>
              </TouchableOpacity>
            </View>

            <ThemedText muted style={styles.hint}>
              Set account type (Demo/Real) in Dashboard → Settings
            </ThemedText>

            <View style={[styles.instructionBox, { backgroundColor: colors.warningBg, borderColor: colors.warningBorder }]}>
              <TouchableOpacity style={styles.instructionHeader} onPress={() => setShowInstructions(!showInstructions)} activeOpacity={0.7}>
                <ThemedText style={[styles.instructionTitle, { color: colors.warning }]}>
                  ⚠️ Automated Trading Must Be Enabled
                </ThemedText>
                <ThemedText muted style={styles.chevron}>
                  {showInstructions ? '▲' : '▼'}
                </ThemedText>
              </TouchableOpacity>
              {showInstructions && (
                <View style={[styles.instructionContent, { borderTopColor: colors.warningBorder }]}>
                  <ThemedText muted style={styles.instructionStep}>
                    1. Open <ThemedText style={{ fontWeight: '600' }}>MetaTrader 5</ThemedText> on your computer or phone.
                  </ThemedText>
                  <ThemedText muted style={styles.instructionStep}>
                    2. Go to <ThemedText style={{ fontWeight: '600' }}>Tools → Options → Expert Advisors</ThemedText>.
                  </ThemedText>
                  <ThemedText muted style={styles.instructionStep}>
                    3. Check: <ThemedText style={{ fontWeight: '600' }}>Allow Automated Trading</ThemedText>.
                  </ThemedText>
                  <ThemedText muted style={styles.instructionStep}>
                    4. Check: <ThemedText style={{ fontWeight: '600' }}>Allow WebRequest for listed URLs</ThemedText> (if applicable).
                  </ThemedText>
                  <ThemedText muted style={styles.instructionStep}>
                    5. Click OK and reconnect your account.
                  </ThemedText>
                </View>
              )}
            </View>

            <TouchableOpacity
              style={[styles.button, { backgroundColor: colors.primary }]}
              onPress={handleSave}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color={colors.primaryFg} size="small" />
              ) : (
                <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md, textAlign: 'center' }}>
                  Connect MT5
                </ThemedText>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.backLink}
              onPress={() => { router.replace('/sign') }}
              activeOpacity={0.7}
            >
              <ThemedText muted style={styles.backText}>← Back to login</ThemedText>
            </TouchableOpacity>
          </View>
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
  msgBox: {
    padding: Spacing.sm + 2,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    marginBottom: Spacing.md,
    alignItems: 'center',
  },
  msgText: { fontWeight: '500', fontSize: FontSize.sm, textAlign: 'center' },
  form: { gap: Spacing.md },
  input: {
    height: 50,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    fontSize: FontSize.md,
  },
  hint: { fontSize: FontSize.xs, textAlign: 'center' },
  label: { fontSize: FontSize.xs, fontWeight: '500', marginBottom: 4 },
  pillTabs: {
    flexDirection: 'row',
    gap: 8,
    padding: 4,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  pillTab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 8,
  },
  pillTabText: { fontSize: FontSize.sm, fontWeight: '500' },
  instructionBox: {
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    padding: Spacing.md,
  },
  instructionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  instructionTitle: { fontWeight: '700', fontSize: FontSize.sm, flex: 1 },
  chevron: { fontSize: FontSize.xs, marginLeft: Spacing.sm },
  instructionContent: {
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    gap: Spacing.xs,
  },
  instructionStep: { fontSize: FontSize.xs, lineHeight: 20 },
  button: {
    height: 52,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Spacing.xs,
  },
  backLink: {
    alignItems: 'center',
    paddingVertical: Spacing.sm,
  },
  backText: { fontSize: FontSize.sm, fontWeight: '500' },
})
