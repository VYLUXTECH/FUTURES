import { useState, useEffect, useRef } from 'react'
import { View, TextInput, TouchableOpacity, ScrollView, Switch, StyleSheet, Modal, Alert, Platform } from 'react-native'
import { router } from 'expo-router'
import { ThemedView } from '../../components/ThemedView'
import { ThemedText } from '../../components/ThemedText'
import { ThemedCard } from '../../components/ThemedCard'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
import { supabase } from '../../utils/supabase'
import { useToast } from '../../components/Toast'
import { api } from '../../utils/api'
import { FontSize, Spacing, BorderRadius } from '../../constants/theme'

const NOTIF_CATEGORIES = [
  { key: 'trade_execution', label: 'Trade Execution' },
  { key: 'trade_closed', label: 'Trade Closed' },
  { key: 'daily_summary', label: 'Daily Summary' },
  { key: 'loss_cooldown', label: 'Loss Cooldown' },
  { key: 'maintenance', label: 'Maintenance' },
  { key: 'package_expiry', label: 'Package Expiry' },
  { key: 'email_trade', label: 'Email Notifications' },
]

const BE_OPTIONS = [
  { key: 'auto', label: 'Auto BE (Move SL to entry after profit)' },
  { key: 'notify', label: 'Notify & Exit (Alert user, auto-close)' },
  { key: 'none', label: 'No BE (Trailing stop only)' },
] as const

export default function SettingsScreen() {
  const [riskPercent, setRiskPercent] = useState(5)
  const [maxDailyTrades, setMaxDailyTrades] = useState(5)
  const [bePolicy, setBePolicy] = useState<'auto' | 'notify' | 'none'>('auto')
  const [autoCompounding, setAutoCompounding] = useState(false)
  const [dryRun, setDryRun] = useState(false)
  const [notifications, setNotifications] = useState<Record<string, boolean>>(
    Object.fromEntries(NOTIF_CATEGORIES.map(n => [n.key, true]))
  )
  const [displayName, setDisplayName] = useState('Trader')
  const [newName, setNewName] = useState('')
  const [showNameModal, setShowNameModal] = useState(false)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [curPassword, setCurPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  const [mt5Login, setMt5Login] = useState<string | null>(null)
  const [mt5Server, setMt5Server] = useState('')
  const [mt5Connected, setMt5Connected] = useState(false)
  const [mt5Broker, setMt5Broker] = useState<'HFM' | 'Exness'>('HFM')
  const [mt5AccountType, setMt5AccountType] = useState<'Demo' | 'Live' | 'Real'>('Demo')
  const [testing, setTesting] = useState(false)

  const { colors, theme, toggleTheme } = useTheme()
  const { signOut, session, updatePassword } = useAuth()
  const { showToast } = useToast()
  const saveTimer = useRef<ReturnType<typeof setTimeout>>()

  // ── Load ─────────────────────────────────────────────────

  useEffect(() => {
    api.get<{
      risk_percent: number; be_policy: string; dry_run: boolean
      auto_compounding: boolean; display_name: string; notifications: Record<string, boolean>
      max_daily_trades: number
    }>('/settings').then(data => {
      setRiskPercent(data.risk_percent ?? 5)
      setMaxDailyTrades(data.max_daily_trades ?? 5)
      if (['auto', 'notify', 'none'].includes(data.be_policy)) setBePolicy(data.be_policy as any)
      setDryRun(data.dry_run ?? false)
      setAutoCompounding(data.auto_compounding ?? false)
      setDisplayName(data.display_name || 'Trader')
      if (data.notifications) setNotifications(prev => ({ ...prev, ...data.notifications }))
    }).catch(() => {})

    api.get<{ login: string | null; server: string | null; connected: boolean }>('/mt5/credentials')
      .then(data => {
        setMt5Login(data.login)
        setMt5Server(data.server || '')
        setMt5Connected(data.connected || false)
        const parts = (data.server || '').split('-')
        if (parts[0] === 'Exness' || parts[0] === 'HFM') setMt5Broker(parts[0])
        if (parts[1] === 'Demo' || parts[1] === 'Live' || parts[1] === 'Real') setMt5AccountType(parts[1])
      }).catch(() => {})
  }, [])

  // ── Auto-save ────────────────────────────────────────────

  function queueSave() {
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      api.post('/settings', {
        risk_percent: riskPercent,
        max_daily_trades: maxDailyTrades,
        be_policy: bePolicy,
        dry_run: dryRun,
        auto_compounding: autoCompounding,
        display_name: displayName,
        notifications,
      }).catch(() => {})
    }, 500)
  }

  useEffect(() => { queueSave() }, [riskPercent, maxDailyTrades, bePolicy, dryRun, autoCompounding, notifications, displayName])

  // ── Handlers ─────────────────────────────────────────────

  async function handleChangePassword() {
    if (!curPassword || !newPassword || !confirmPassword) { showToast('Fill all fields', 'error'); return }
    if (newPassword !== confirmPassword) { showToast('Passwords do not match', 'error'); return }
    if (newPassword.length < 6) { showToast('Password must be at least 6 characters', 'error'); return }
    setChangingPassword(true)
    try {
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: session?.user?.email || '',
        password: curPassword,
      })
      if (signInError) { showToast('Current password is incorrect', 'error'); return }
      await updatePassword(newPassword)
      showToast('Password updated', 'success')
      setShowPasswordModal(false)
      setCurPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (e: any) {
      showToast(e.message || 'Failed to change password', 'error')
    } finally {
      setChangingPassword(false)
    }
  }

  async function saveName() {
    const name = newName.trim()
    if (!name) { showToast('Name cannot be empty', 'error'); return }
    setDisplayName(name)
    setShowNameModal(false)
    showToast('Name updated', 'success')
  }

  async function handleTestConnection() {
    if (!mt5Login) { showToast('Set up MT5 credentials on the Connect screen first', 'error'); return }
    setTesting(true)
    try {
      const server = `${mt5Broker}-${mt5AccountType}`
      await api.put('/mt5/credentials', { server })
      setMt5Server(server)
      const data = await api.post<{ status: string; error?: string }>('/mt5/connect', {
        login: mt5Login, password: '', server,
      })
      if (data.status === 'connected_ea_ready') {
        setMt5Connected(true)
        showToast('✅ Connected — EA Ready', 'success')
      } else if (data.status === 'connected_no_ea') {
        setMt5Connected(true)
        showToast('⚠️ Connected — Enable Automated Trading in MT5', 'info')
      } else {
        showToast('❌ ' + (data.error || 'Connection failed'), 'error')
      }
    } catch (e: any) {
      showToast(e.message || 'Connection test failed', 'error')
    } finally {
      setTesting(false)
    }
  }

  function handleExport(format: 'csv' | 'pdf') {
    if (Platform.OS === 'web') {
      window.location.href = `/api/trades/export?format=${format}`
    } else {
      showToast(`${format.toUpperCase()} export — use the web dashboard`, 'info')
    }
  }

  function toggleNotif(key: string) {
    setNotifications(prev => ({ ...prev, [key]: !prev[key] }))
  }

  // ── Render ───────────────────────────────────────────────

  const inputStyle = { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }
  const serverStr = `${mt5Broker}-${mt5AccountType}`

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <ThemedText style={{ fontSize: 16 }}>←</ThemedText>
            <ThemedText style={styles.backText}>Back</ThemedText>
          </TouchableOpacity>
          <ThemedText heading style={styles.pageTitle}>Settings</ThemedText>
          <TouchableOpacity style={[styles.themeBtn, { backgroundColor: colors.card, borderColor: colors.cardBorder }]} onPress={toggleTheme}>
            {theme === 'dark' ? <ThemedText style={{ fontSize: 16 }}>☀️</ThemedText> : <ThemedText style={{ fontSize: 16 }}>🌙</ThemedText>}
          </TouchableOpacity>
        </View>

        {/* Account Card */}
        <ThemedCard style={styles.card}>
          <ThemedText muted style={styles.cardTitle}>👤 Account</ThemedText>
          <View style={styles.settingRow}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Display name</ThemedText>
              <ThemedText muted style={styles.settingDesc}>{displayName}</ThemedText>
            </View>
            <TouchableOpacity onPress={() => { setNewName(displayName); setShowNameModal(true) }}>
              <ThemedText style={styles.settingAction}>Edit</ThemedText>
            </TouchableOpacity>
          </View>
          <View style={styles.settingRow}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Password</ThemedText>
              <ThemedText muted style={styles.settingDesc}>Change your password</ThemedText>
            </View>
            <TouchableOpacity onPress={() => setShowPasswordModal(true)}>
              <ThemedText style={styles.settingAction}>Update</ThemedText>
            </TouchableOpacity>
          </View>
          <View style={[styles.settingRow, { borderBottomWidth: 0 }]}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Two-factor authentication</ThemedText>
              <ThemedText muted style={styles.settingDesc}>Enhance security with TOTP</ThemedText>
            </View>
            <Switch
              value={false}
              onValueChange={() => showToast('2FA — coming soon', 'info')}
              trackColor={{ false: '#444', true: colors.primary }}
              thumbColor="#ccc"
            />
          </View>
        </ThemedCard>

        {/* Trading Preferences Card */}
        <ThemedCard style={styles.card}>
          <ThemedText muted style={styles.cardTitle}>📊 Trading Preferences</ThemedText>

          <View style={styles.settingRow}>
            <ThemedText style={styles.settingTitle}>Risk per trade</ThemedText>
            <ThemedText style={{ fontWeight: '600' }}>{riskPercent}%</ThemedText>
          </View>
          <View style={styles.sliderContainer}>
            <View style={[styles.sliderTrack, { backgroundColor: colors.cardBorder }]}>
              <View style={[styles.sliderFill, { backgroundColor: colors.primary, width: `${(riskPercent / 10) * 100}%` }]} />
            </View>
            <View style={styles.sliderLabels}>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                <TouchableOpacity key={n} onPress={() => setRiskPercent(n)} hitSlop={6}>
                  <ThemedText style={{
                    fontSize: FontSize.xs,
                    fontWeight: n === riskPercent ? '700' : '400',
                    color: n === riskPercent ? colors.primary : colors.textMuted,
                  }}>{n}</ThemedText>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <View style={styles.settingRow}>
            <ThemedText style={styles.settingTitle}>Max daily trades</ThemedText>
            <ThemedText style={{ fontWeight: '600' }}>{maxDailyTrades}</ThemedText>
          </View>
          <View style={styles.sliderContainer}>
            <View style={[styles.sliderTrack, { backgroundColor: colors.cardBorder }]}>
              <View style={[styles.sliderFill, { backgroundColor: colors.primary, width: `${((maxDailyTrades - 1) / 24) * 100}%` }]} />
            </View>
            <View style={styles.sliderLabels}>
              {Array.from({ length: 25 }, (_, i) => i + 1).map(n => (
                <TouchableOpacity key={n} onPress={() => setMaxDailyTrades(n)} hitSlop={6}>
                  <ThemedText style={{
                    fontSize: FontSize.xs,
                    fontWeight: n === maxDailyTrades ? '700' : '400',
                    color: n === maxDailyTrades ? colors.primary : colors.textMuted,
                  }}>{n}</ThemedText>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <View style={styles.sectionLabel}><ThemedText style={styles.settingTitle}>Breakeven policy</ThemedText></View>
          <View style={styles.radioGroup}>
            {BE_OPTIONS.map(opt => (
              <TouchableOpacity
                key={opt.key}
                style={[styles.radioOption, { backgroundColor: colors.inputBg, borderColor: colors.border }, bePolicy === opt.key && { borderColor: colors.primary, backgroundColor: 'rgba(37,99,235,0.08)' }]}
                onPress={() => setBePolicy(opt.key)}
              >
                <View style={[styles.radioDot, { borderColor: bePolicy === opt.key ? colors.primary : colors.textMuted }]}>
                  {bePolicy === opt.key && <View style={[styles.radioDotFill, { backgroundColor: colors.primary }]} />}
                </View>
                <ThemedText style={styles.radioLabel}>{opt.label}</ThemedText>
              </TouchableOpacity>
            ))}
          </View>

          {autoCompounding && (
            <View style={[styles.warningBanner, { backgroundColor: colors.warningBg, borderColor: colors.warningBorder }]}>
              <ThemedText style={{ color: colors.warning, fontSize: FontSize.xs }}>
                ⚠️ Auto-compounding reinvests profits – risk increases after wins. Use with caution.
              </ThemedText>
            </View>
          )}

          <View style={styles.settingRow}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Auto-compounding</ThemedText>
              <ThemedText muted style={styles.settingDesc}>Recalculate risk based on new balance</ThemedText>
            </View>
            <Switch value={autoCompounding} onValueChange={setAutoCompounding} trackColor={{ false: '#444', true: colors.primary }} />
          </View>
          <View style={[styles.settingRow, { borderBottomWidth: 0 }]}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Dry-run mode</ThemedText>
              <ThemedText muted style={styles.settingDesc}>Simulate trades without real orders</ThemedText>
            </View>
            <Switch value={dryRun} onValueChange={setDryRun} trackColor={{ false: '#444', true: colors.primary }} />
          </View>
        </ThemedCard>

        {/* MT5 Connection Card */}
        <ThemedCard style={styles.card}>
          <ThemedText muted style={styles.cardTitle}>📡 MT5 Connection</ThemedText>

          <View style={styles.settingRow}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Account</ThemedText>
              <ThemedText muted style={styles.settingDesc}>{mt5Login ? `Account ${mt5Login}` : 'Not configured'}</ThemedText>
            </View>
          </View>

          <View style={styles.sectionLabel}><ThemedText style={styles.settingTitle}>Broker</ThemedText></View>
          <View style={styles.radioGroup}>
            {(['HFM', 'Exness'] as const).map(b => (
              <TouchableOpacity
                key={b}
                style={[styles.radioOption, { backgroundColor: colors.inputBg, borderColor: colors.border }, mt5Broker === b && { borderColor: colors.primary, backgroundColor: 'rgba(37,99,235,0.08)' }]}
                onPress={() => setMt5Broker(b)}
              >
                <View style={[styles.radioDot, { borderColor: mt5Broker === b ? colors.primary : colors.textMuted }]}>
                  {mt5Broker === b && <View style={[styles.radioDotFill, { backgroundColor: colors.primary }]} />}
                </View>
                <ThemedText style={styles.radioLabel}>{b}</ThemedText>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.sectionLabel}><ThemedText style={styles.settingTitle}>Account Type</ThemedText></View>
          <View style={styles.radioGroup}>
            {(['Demo', 'Live', 'Real'] as const).map(t => (
              <TouchableOpacity
                key={t}
                style={[styles.radioOption, { backgroundColor: colors.inputBg, borderColor: colors.border }, mt5AccountType === t && { borderColor: colors.primary, backgroundColor: 'rgba(37,99,235,0.08)' }]}
                onPress={() => setMt5AccountType(t)}
              >
                <View style={[styles.radioDot, { borderColor: mt5AccountType === t ? colors.primary : colors.textMuted }]}>
                  {mt5AccountType === t && <View style={[styles.radioDotFill, { backgroundColor: colors.primary }]} />}
                </View>
                <ThemedText style={styles.radioLabel}>{t}</ThemedText>
              </TouchableOpacity>
            ))}
          </View>

          <View style={[styles.settingRow, { borderBottomWidth: 0 }]}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Server</ThemedText>
              <ThemedText muted style={styles.settingDesc}>{serverStr}</ThemedText>
            </View>
            <ThemedText muted style={{ fontSize: FontSize.xs }}>
              {mt5Connected ? '✅ Connected' : mt5Server ? '⚠️ Not connected' : '⚪ Not configured'}
            </ThemedText>
          </View>

          <TouchableOpacity style={[styles.actionBtn, { borderColor: colors.primary }]} onPress={handleTestConnection} disabled={testing}>
            <ThemedText style={{ color: colors.primary, fontWeight: '600', fontSize: FontSize.sm }}>
              {testing ? 'Testing...' : 'Test Connection'}
            </ThemedText>
          </TouchableOpacity>
        </ThemedCard>

        {/* Notifications Card */}
        <ThemedCard style={styles.card}>
          <ThemedText muted style={styles.cardTitle}>🔔 Notifications</ThemedText>
          {NOTIF_CATEGORIES.map(n => (
            <View key={n.key} style={[styles.settingRow, { borderBottomWidth: 0, paddingVertical: Spacing.sm }]}>
              <ThemedText style={styles.settingTitle}>{n.label}</ThemedText>
              <Switch
                value={notifications[n.key]}
                onValueChange={() => toggleNotif(n.key)}
                trackColor={{ false: '#444', true: colors.primary }}
              />
            </View>
          ))}
        </ThemedCard>

        {/* Appearance Card */}
        <ThemedCard style={styles.card}>
          <ThemedText muted style={styles.cardTitle}>🎨 Appearance</ThemedText>
          <View style={styles.settingRow}>
            <View style={styles.settingLabel}>
              <ThemedText style={styles.settingTitle}>Dark mode</ThemedText>
              <ThemedText muted style={styles.settingDesc}>Switch app theme</ThemedText>
            </View>
            <Switch value={theme === 'dark'} onValueChange={toggleTheme} trackColor={{ false: '#444', true: colors.primary }} />
          </View>
        </ThemedCard>

        {/* Data Management Card */}
        <ThemedCard style={styles.card}>
          <ThemedText muted style={styles.cardTitle}>📁 Data Management</ThemedText>
          <View style={{ gap: Spacing.sm }}>
            <TouchableOpacity style={[styles.actionBtn, { borderColor: colors.primary }]} onPress={() => handleExport('csv')}>
              <ThemedText style={{ color: colors.primary, fontWeight: '600' }}>Export Trade History</ThemedText>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.actionBtn, { borderColor: colors.loss }]} onPress={() => showToast('Chat cache cleared', 'success')}>
              <ThemedText style={{ color: colors.loss, fontWeight: '600' }}>Clear Cached Chat History</ThemedText>
            </TouchableOpacity>
          </View>
        </ThemedCard>

        {/* Logout */}
        <TouchableOpacity style={styles.logoutBtn} onPress={() => {
          Alert.alert('Logout', 'Are you sure?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Logout', style: 'destructive', onPress: () => { signOut(); router.replace('/sign') } },
          ])
        }}>
          <ThemedText style={{ color: colors.loss, textAlign: 'center', fontWeight: '600' }}>Logout</ThemedText>
        </TouchableOpacity>

        <ThemedText muted style={styles.footer}>Settings are saved automatically</ThemedText>
      </ScrollView>

      {/* Edit Name Modal */}
      <Modal visible={showNameModal} transparent animationType="fade" onRequestClose={() => setShowNameModal(false)}>
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShowNameModal(false)}>
          <View style={[styles.modalContent, { backgroundColor: colors.card, borderColor: colors.cardBorder }]}>
            <View style={styles.modalHeader}>
              <ThemedText heading style={{ fontSize: 18 }}>Edit Display Name</ThemedText>
              <TouchableOpacity onPress={() => setShowNameModal(false)}><ThemedText style={{ fontSize: 22 }}>×</ThemedText></TouchableOpacity>
            </View>
            <TextInput
              style={[styles.modalInput, inputStyle]}
              value={newName}
              onChangeText={setNewName}
              placeholder="Enter new name"
              placeholderTextColor={colors.textMuted}
              autoFocus
            />
            <TouchableOpacity style={[styles.actionBtn, { borderColor: colors.primary }]} onPress={saveName}>
              <ThemedText style={{ color: colors.primary, fontWeight: '600' }}>Save Changes</ThemedText>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Change Password Modal */}
      <Modal visible={showPasswordModal} transparent animationType="fade" onRequestClose={() => setShowPasswordModal(false)}>
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShowPasswordModal(false)}>
          <View style={[styles.modalContent, { backgroundColor: colors.card, borderColor: colors.cardBorder }]}>
            <View style={styles.modalHeader}>
              <ThemedText heading style={{ fontSize: 18 }}>Change Password</ThemedText>
              <TouchableOpacity onPress={() => setShowPasswordModal(false)}><ThemedText style={{ fontSize: 22 }}>×</ThemedText></TouchableOpacity>
            </View>
            <TextInput
              style={[styles.modalInput, inputStyle]}
              value={curPassword}
              onChangeText={setCurPassword}
              placeholder="Current password"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              autoFocus
            />
            <TextInput
              style={[styles.modalInput, inputStyle]}
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder="New password"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
            />
            <TextInput
              style={[styles.modalInput, inputStyle]}
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Confirm new password"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
            />
            <TouchableOpacity
              style={[styles.actionBtn, { borderColor: colors.primary, opacity: changingPassword ? 0.5 : 1 }]}
              onPress={handleChangePassword}
              disabled={changingPassword}
            >
              <ThemedText style={{ color: colors.primary, fontWeight: '600' }}>
                {changingPassword ? 'Updating...' : 'Update Password'}
              </ThemedText>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { padding: Spacing.md, gap: Spacing.md, paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4 },
  backText: { fontSize: FontSize.md, fontWeight: '600' },
  pageTitle: { fontSize: 20, fontWeight: '700' },
  themeBtn: { width: 40, height: 40, borderRadius: 20, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  card: { padding: Spacing.md + 4 },
  cardTitle: { fontSize: FontSize.sm, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: Spacing.sm },
  settingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: Spacing.sm + 2, borderBottomWidth: 1, borderBottomColor: '#222' },
  settingLabel: { flex: 1 },
  settingTitle: { fontSize: FontSize.sm, fontWeight: '500' },
  settingDesc: { fontSize: FontSize.xs, marginTop: 2 },
  settingAction: { fontSize: FontSize.sm, fontWeight: '600', color: '#888', paddingHorizontal: Spacing.sm, paddingVertical: Spacing.xs },
  sliderContainer: { paddingBottom: Spacing.md },
  sliderTrack: { height: 4, borderRadius: 2, overflow: 'hidden', marginBottom: Spacing.xs },
  sliderFill: { height: '100%', borderRadius: 2 },
  sliderLabels: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 2 },
  sectionLabel: { marginBottom: Spacing.xs, marginTop: Spacing.sm },
  radioGroup: { gap: Spacing.xs, marginBottom: Spacing.md },
  radioOption: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, padding: Spacing.sm + 2, borderWidth: 1, borderRadius: 10 },
  radioDot: { width: 16, height: 16, borderRadius: 8, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  radioDotFill: { width: 10, height: 10, borderRadius: 5 },
  radioLabel: { fontSize: FontSize.sm, fontWeight: '500', flex: 1 },
  warningBanner: { padding: Spacing.sm + 2, borderRadius: 10, borderWidth: 1, marginBottom: Spacing.sm },
  actionBtn: { padding: Spacing.md, borderRadius: BorderRadius.md, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  logoutBtn: { paddingVertical: Spacing.lg },
  footer: { textAlign: 'center', fontSize: FontSize.xs },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: Spacing.xl },
  modalContent: { width: '100%', maxWidth: 380, padding: Spacing.lg, borderRadius: 20, borderWidth: 1 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.md },
  modalInput: { height: 48, borderWidth: 1, borderRadius: 10, paddingHorizontal: Spacing.md, fontSize: FontSize.md, marginBottom: Spacing.md },
})
