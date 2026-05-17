import { useState, useEffect, useCallback } from 'react'
import { View, TouchableOpacity, ScrollView, StyleSheet, Platform, TextInput, Modal, Alert } from 'react-native'
import { router } from 'expo-router'
import { useFonts, DancingScript_700Bold } from '@expo-google-fonts/dancing-script'
import { ThemedView } from '../../components/ThemedView'
import { ThemedText } from '../../components/ThemedText'
import { ThemedCard } from '../../components/ThemedCard'
import { useTheme } from '../../contexts/ThemeContext'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../components/Toast'
import { supabase } from '../../utils/supabase'
import { FontSize, Spacing, BorderRadius } from '../../constants/theme'
import { api } from '../../utils/api'

type DashboardState = {
  balance: number
  equity: number
  margin: number
  dailyPnl: number
  botActive: boolean
  mt5Connected: boolean
  riskPercent: number
  mode: string
  trades: any[]
  recentTrades: any[]
  health: 'green' | 'yellow' | 'red'
  cooldown: boolean
}

const healthTooltips: Record<string, string> = {
  green: 'All systems normal. MT5 connected, no news impact, bot ready.',
  yellow: 'News after-effect active – trading with reduced risk.',
  red: 'MT5 disconnected – check server connection.',
}

export default function DashboardScreen() {
  const [dash, setDash] = useState<DashboardState>({
    balance: 0, equity: 0, margin: 0, dailyPnl: 0,
    botActive: false, mt5Connected: false, riskPercent: 5,
    mode: 'long', trades: [], recentTrades: [],
    health: 'green', cooldown: false,
  })
  const [mode, setMode] = useState<'long' | 'short'>('long')
  const [tradeCount, setTradeCount] = useState(1)
  const [riskPercent, setRiskPercent] = useState(5)
  const [showHealthTooltip, setShowHealthTooltip] = useState(false)
  const [broker, setBroker] = useState('')
  const [accountType, setAccountType] = useState<'Demo' | 'Real'>('Demo')
  const [savingAccountType, setSavingAccountType] = useState(false)

  const { colors, theme, toggleTheme } = useTheme()
  const { session, signOut } = useAuth()
  const { showToast } = useToast()
  const [fontsLoaded] = useFonts({ DancingScript_700Bold })

  useEffect(() => {
    if (!session) {
      router.replace('/sign')
      return
    }
    checkVerified()
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

  const healthColor = dash.health === 'green' ? '#22C55E' : dash.health === 'yellow' ? '#EAB308' : '#EF4444'

  const loadDashboard = useCallback(async () => {
    try {
      const [status, dashboard, creds] = await Promise.all([
        api.get<{ running: boolean; mt5_connected: boolean; risk_percent: number }>('/status'),
        api.get<{ balance: number; equity: number; daily_pnl: number; open_trades: any[]; recent_trades: any[] }>('/dashboard'),
        api.get<{ login: string | null; server: string | null }>('/mt5/credentials'),
      ])
      const server = creds.server || ''
      const parts = server.split('-')
      const brk = parts[0] || ''
      const type = parts[1] === 'Real' ? 'Real' : 'Demo'
      setBroker(brk)
      setAccountType(type)

      setDash(prev => ({
        ...prev,
        balance: dashboard.balance,
        equity: dashboard.equity,
        dailyPnl: dashboard.daily_pnl,
        botActive: status.running,
        mt5Connected: status.mt5_connected,
        riskPercent: status.risk_percent || 5,
        trades: dashboard.open_trades,
        recentTrades: dashboard.recent_trades,
        health: status.mt5_connected ? 'green' : 'red',
      }))
    } catch { /* offline */ }
  }, [])

  useEffect(() => {
    loadDashboard()
    const interval = setInterval(loadDashboard, 15000)
    return () => clearInterval(interval)
  }, [loadDashboard])

  async function handleToggleAccountType() {
    const next = accountType === 'Demo' ? 'Real' : 'Demo'
    if (next === 'Real') {
      const confirmed = await new Promise(resolve => {
        Alert.alert(
          'Switch to Real?',
          'You are about to enable live trading with real funds. Are you sure?',
          [{ text: 'Cancel', style: 'cancel', onPress: () => resolve(false) }, { text: 'Confirm', style: 'destructive', onPress: () => resolve(true) }],
        )
      })
      if (!confirmed) return
    }
    setSavingAccountType(true)
    try {
      const server = broker ? `${broker}-${next}` : next
      await api.put('/mt5/credentials', { server })
      setAccountType(next)
      showToast(`Account set to ${next}`, 'success')
    } catch (e: any) {
      showToast(e.message || 'Failed to update account type', 'error')
    } finally {
      setSavingAccountType(false)
    }
  }

  async function handleStartBot() {
    try {
      await api.post('/user/start', { mode, tradeCount, riskPercent })
      setDash(prev => ({ ...prev, botActive: true }))
      showToast('Bot started', 'success')
    } catch (e: any) {
      showToast(e.message || 'Failed to start bot', 'error')
    }
  }

  async function handleStopBot() {
    try {
      await api.post('/user/stop')
      setDash(prev => ({ ...prev, botActive: false }))
      showToast('Bot stopped', 'success')
    } catch (e: any) {
      showToast(e.message || 'Failed to stop bot', 'error')
    }
  }

  const ActionButton = ({ label, icon, onPress }: { label: string; icon: string; onPress: () => void }) => (
    <TouchableOpacity style={[styles.actionBtn, { backgroundColor: colors.bg, borderColor: colors.cardBorder }]} onPress={onPress}>
      <ThemedText style={styles.actionIcon}>{icon}</ThemedText>
      <ThemedText muted style={styles.actionLabel}>{label}</ThemedText>
    </TouchableOpacity>
  )

  const dailyUsed = dash.trades.length
  const dailyLimit = 5
  const pct = Math.min(100, (dailyUsed / dailyLimit) * 100)

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <ThemedText
            heading
            style={[styles.logo, fontsLoaded ? { fontFamily: 'DancingScript_700Bold' } : undefined]}
          >
            FUTURES
          </ThemedText>
          <TouchableOpacity style={[styles.themeToggle, { backgroundColor: colors.card, borderColor: colors.cardBorder }]} onPress={toggleTheme}>
            {theme === 'dark' ? (
              <ThemedText style={{ fontSize: 18 }}>☀️</ThemedText>
            ) : (
              <ThemedText style={{ fontSize: 18 }}>🌙</ThemedText>
            )}
          </TouchableOpacity>
        </View>

        {/* Account Card */}
        <ThemedCard style={styles.card}>
          <ThemedText heading style={styles.balance}>${dash.balance.toLocaleString()}</ThemedText>
          <View style={styles.subBalance}>
            <ThemedText muted>Equity: <ThemedText style={{ fontWeight: '600' }}>${dash.equity.toLocaleString()}</ThemedText></ThemedText>
            <ThemedText muted>Margin: <ThemedText style={{ fontWeight: '600' }}>${dash.margin.toLocaleString()}</ThemedText></ThemedText>
          </View>

          <View style={styles.accountTypeRow}>
            <ThemedText muted style={{ fontSize: FontSize.xs, textTransform: 'uppercase', letterSpacing: 1 }}>Account</ThemedText>
            <View style={[styles.typeSelector, { backgroundColor: colors.cardBorder }]}>
              <TouchableOpacity
                style={[styles.typeBtn, accountType === 'Demo' && { backgroundColor: colors.card }]}
                onPress={handleToggleAccountType}
                disabled={savingAccountType || accountType === 'Demo'}
              >
                <ThemedText style={[styles.typeBtnText, accountType === 'Demo' ? { color: colors.text } : { color: colors.textMuted }]}>
                  Demo
                </ThemedText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.typeBtn, accountType === 'Real' && { backgroundColor: colors.card }]}
                onPress={handleToggleAccountType}
                disabled={savingAccountType || accountType === 'Real'}
              >
                <ThemedText style={[styles.typeBtnText, accountType === 'Real' ? { color: colors.text } : { color: colors.textMuted }]}>
                  Real
                </ThemedText>
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.dailyLimit}>
            <View style={styles.limitLabel}>
              <ThemedText muted style={{ fontSize: FontSize.xs }}>
                Daily trades used <ThemedText style={{ fontSize: FontSize.xs }}>(max 5 per 24h)</ThemedText>
              </ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.xs }}>
                ∞ <ThemedText style={{ fontSize: FontSize.xs }}>|</ThemedText> {dailyUsed} / {dailyLimit}
              </ThemedText>
            </View>
            <View style={[styles.limitBarBg, { backgroundColor: colors.cardBorder }]}>
              <View style={[styles.limitBarFill, { backgroundColor: colors.primary, width: `${pct}%` }]} />
            </View>
          </View>

          <TouchableOpacity style={styles.healthRow} onPress={() => setShowHealthTooltip(true)} activeOpacity={0.7}>
            <View style={[styles.healthDot, { backgroundColor: healthColor, shadowColor: healthColor }]} />
            <ThemedText style={styles.healthText}>
              {dash.botActive ? 'Bot Running' : dash.mt5Connected ? 'Bot Active' : 'MT5 Disconnected'}
            </ThemedText>
          </TouchableOpacity>
        </ThemedCard>

        {/* Bot Control Card */}
        <ThemedCard style={styles.card}>
          <View style={styles.controlsRow}>
            <TouchableOpacity
              style={[styles.controlBtn, styles.btnStart]}
              onPress={handleStartBot}
              disabled={dash.botActive || dash.cooldown}
              activeOpacity={0.8}
            >
              <ThemedText style={styles.controlBtnText}>▶ START BOT</ThemedText>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.controlBtn, styles.btnStop]}
              onPress={handleStopBot}
              disabled={!dash.botActive}
              activeOpacity={0.8}
            >
              <ThemedText style={styles.controlBtnText}>⏹ STOP BOT</ThemedText>
            </TouchableOpacity>
          </View>

          {dash.botActive && (
            <View style={[styles.autoStopInfo, { backgroundColor: colors.warningBg, borderColor: colors.warningBorder }]}>
              <ThemedText style={{ color: colors.warning, fontSize: FontSize.xs, textAlign: 'center', lineHeight: 18 }}>
                Bot runs until 1:3 R:R target is hit or market conditions trigger exit. Tap STOP to intervene.
              </ThemedText>
            </View>
          )}

          <View style={[styles.modeSelector, { backgroundColor: colors.cardBorder }]}>
            <TouchableOpacity
              style={[styles.modeBtn, mode === 'long' && { backgroundColor: colors.card }]}
              onPress={() => setMode('long')}
              disabled={dash.botActive}
            >
              <ThemedText style={[styles.modeBtnText, mode === 'long' ? { color: colors.text } : { color: colors.textMuted }]}>
                Long-term
              </ThemedText>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modeBtn, mode === 'short' && { backgroundColor: colors.card }]}
              onPress={() => setMode('short')}
              disabled={dash.botActive}
            >
              <ThemedText style={[styles.modeBtnText, mode === 'short' ? { color: colors.text } : { color: colors.textMuted }]}>
                Short-term
              </ThemedText>
            </TouchableOpacity>
          </View>

          <View style={styles.modeParams}>
            {mode === 'long' ? (
              <View style={styles.paramRow}>
                <ThemedText muted>Number of trades</ThemedText>
                <TextInput
                  style={[styles.paramInput, { backgroundColor: colors.bg, borderColor: colors.cardBorder, color: colors.text, opacity: dash.botActive ? 0.4 : 1 }]}
                  value={String(tradeCount)}
                  onChangeText={t => setTradeCount(Math.max(1, Math.min(5, parseInt(t) || 1)))}
                  keyboardType="number-pad"
                  editable={!dash.botActive}
                />
              </View>
            ) : (
              <View style={[styles.shortTermInfo, { backgroundColor: colors.bg, borderColor: colors.cardBorder }]}>
                <ThemedText muted style={{ fontSize: FontSize.xs }}>
                  One trade will be executed, then bot stops. Adjust risk as needed.
                </ThemedText>
              </View>
            )}
            <View style={styles.paramRow}>
              <ThemedText muted>Risk %</ThemedText>
              <ThemedText style={{ fontWeight: '600' }}>
                {riskPercent}% <ThemedText muted style={{ fontWeight: '400' }}>(${(dash.balance * riskPercent / 100).toFixed(2)})</ThemedText>
              </ThemedText>
            </View>
            <View style={styles.sliderTrack}>
              <View style={[styles.sliderFill, { backgroundColor: colors.primary, width: `${(riskPercent / 10) * 100}%` }]} />
            </View>
            <View style={styles.sliderLabels}>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                <TouchableOpacity key={n} onPress={() => !dash.botActive && setRiskPercent(n)} hitSlop={4}>
                  <ThemedText style={{
                    fontSize: FontSize.xs,
                    fontWeight: n === riskPercent ? '700' : '400',
                    color: n === riskPercent ? colors.primary : colors.textMuted,
                  }}>
                    {n}
                  </ThemedText>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </ThemedCard>

        {/* Recent Trades Card */}
        <ThemedCard style={styles.card}>
          <View style={styles.cardHeader}>
            <ThemedText muted style={styles.cardTitle}>📋 Recent Trades</ThemedText>
          </View>
          {dash.recentTrades.length === 0 ? (
            <ThemedText muted style={{ textAlign: 'center', paddingVertical: Spacing.lg, fontSize: FontSize.sm }}>
              No trades yet
            </ThemedText>
          ) : (
            <>
              <View style={styles.tradeHeader}>
                <ThemedText muted style={styles.th}>Pair</ThemedText>
                <ThemedText muted style={styles.th}>Type</ThemedText>
                <ThemedText muted style={styles.th}>P&L</ThemedText>
                <ThemedText muted style={styles.th}>Time</ThemedText>
              </View>
              {dash.recentTrades.slice(0, 5).map((t: any, i: number) => (
                <View key={i} style={styles.tradeRow}>
                  <ThemedText style={styles.td}>{t.pair || '-'}</ThemedText>
                  <ThemedText style={styles.td}>{t.direction || '-'}</ThemedText>
                  <ThemedText style={[styles.td, { color: (t.profit || 0) >= 0 ? colors.profit : colors.loss, fontWeight: '600' }]}>
                    {(t.profit || 0) >= 0 ? '+' : ''}${(t.profit || 0).toFixed(2)}
                  </ThemedText>
                  <ThemedText muted style={styles.td}>{t.close_time ? t.close_time.slice(11, 16) : '-'}</ThemedText>
                </View>
              ))}
            </>
          )}
          <TouchableOpacity onPress={() => router.push('/(tabs)/accountability')}>
            <ThemedText style={[styles.seeAll, { color: colors.primary }]}>See all →</ThemedText>
          </TouchableOpacity>
        </ThemedCard>

        {/* Performance & Actions Card */}
        <ThemedCard style={styles.card}>
          <View style={styles.performanceRow}>
            <ThemedText muted style={styles.cardTitle}>Today's P&L</ThemedText>
            <ThemedText style={[styles.todayPnl, { color: dash.dailyPnl >= 0 ? colors.profit : colors.loss }]}>
              {dash.dailyPnl >= 0 ? '+' : ''}${dash.dailyPnl.toFixed(2)}
            </ThemedText>
          </View>
          <View style={styles.actionsGrid}>
            <ActionButton label="Chat" icon="💬" onPress={() => router.push('/(tabs)/copilot')} />
            <ActionButton label="History" icon="📖" onPress={() => router.push('/(tabs)/accountability')} />
            <ActionButton label="Settings" icon="⚙️" onPress={() => router.push('/(tabs)/settings')} />
            <ActionButton label="Support" icon="🆘" onPress={() => router.push('/(tabs)/support')} />
          </View>
          {dash.cooldown && (
            <View style={[styles.warningBanner, { backgroundColor: colors.warningBg, borderColor: colors.warningBorder }]}>
              <ThemedText style={{ color: colors.warning, fontSize: FontSize.xs }}>
                ⚠️ Bot paused due to 3 consecutive losses (cooldown 24h).
              </ThemedText>
            </View>
          )}
        </ThemedCard>

        {/* Sign Out */}
        <TouchableOpacity style={styles.signOut} onPress={() => signOut().then(() => router.replace('/sign'))}>
          <ThemedText style={{ color: colors.loss, textAlign: 'center', fontWeight: '500' }}>Sign Out</ThemedText>
        </TouchableOpacity>
      </ScrollView>

      {/* Health Tooltip Modal */}
      <Modal visible={showHealthTooltip} transparent animationType="fade" onRequestClose={() => setShowHealthTooltip(false)}>
        <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={() => setShowHealthTooltip(false)}>
          <View style={[styles.tooltip, { backgroundColor: colors.card, borderColor: colors.cardBorder }]}>
            <ThemedText muted style={{ fontSize: FontSize.sm, lineHeight: 20 }}>
              {healthTooltips[dash.health]}
            </ThemedText>
          </View>
        </TouchableOpacity>
      </Modal>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { padding: Spacing.md, gap: Spacing.md, paddingBottom: 60 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  logo: { fontSize: 28, fontWeight: '700' },
  themeToggle: {
    width: 40, height: 40,
    borderRadius: 20,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  card: { padding: Spacing.md + 4 },
  balance: { fontSize: 36, fontWeight: '800', marginBottom: Spacing.sm },
  subBalance: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.md },
  accountTypeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  typeSelector: {
    flexDirection: 'row',
    padding: 3,
    borderRadius: 8,
    gap: 3,
  },
  typeBtn: {
    paddingVertical: Spacing.xs + 2,
    paddingHorizontal: Spacing.md,
    borderRadius: 6,
  },
  typeBtnText: { fontSize: FontSize.sm, fontWeight: '600' },
  dailyLimit: { marginBottom: Spacing.md },
  limitLabel: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.xs },
  limitBarBg: { height: 6, borderRadius: 3, overflow: 'hidden' },
  limitBarFill: { height: '100%', borderRadius: 3 },
  healthRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  healthDot: { width: 10, height: 10, borderRadius: 5, shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.8, shadowRadius: 6, elevation: 4 },
  healthText: { fontSize: FontSize.sm, fontWeight: '500' },
  controlsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md },
  controlBtn: {
    flex: 1, paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center', justifyContent: 'center',
  },
  btnStart: { backgroundColor: '#16A34A' },
  btnStop: { backgroundColor: '#DC2626' },
  controlBtnText: { color: '#FFF', fontWeight: '700', fontSize: FontSize.sm },
  autoStopInfo: { padding: Spacing.sm, borderRadius: 8, borderWidth: 1, marginBottom: Spacing.sm },
  modeSelector: {
    flexDirection: 'row', padding: 4, borderRadius: 10,
    marginBottom: Spacing.md, gap: 4,
  },
  modeBtn: { flex: 1, paddingVertical: Spacing.sm + 2, borderRadius: 8, alignItems: 'center' },
  modeBtnText: { fontSize: FontSize.sm, fontWeight: '600' },
  modeParams: { gap: Spacing.sm },
  paramRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  paramInput: {
    width: 60, paddingVertical: Spacing.xs + 2, paddingHorizontal: Spacing.sm,
    borderWidth: 1, borderRadius: 6, textAlign: 'center', fontSize: FontSize.md,
  },
  shortTermInfo: { padding: Spacing.sm + 2, borderRadius: 10, borderWidth: 1 },
  sliderTrack: { height: 4, borderRadius: 2, overflow: 'hidden', backgroundColor: '#333' },
  sliderFill: { height: '100%', borderRadius: 2 },
  sliderLabels: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 2 },
  cardTitle: { fontSize: FontSize.sm, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  cardHeader: { marginBottom: Spacing.sm },
  tradeHeader: { flexDirection: 'row', paddingBottom: Spacing.sm, borderBottomWidth: 1, borderBottomColor: '#222' },
  th: { flex: 1, fontSize: FontSize.xs, fontWeight: '500' },
  tradeRow: { flexDirection: 'row', paddingVertical: Spacing.sm + 2, borderBottomWidth: 1, borderBottomColor: '#222' },
  td: { flex: 1, fontSize: FontSize.sm },
  seeAll: { textAlign: 'right', marginTop: Spacing.sm, fontSize: FontSize.sm, fontWeight: '600' },
  performanceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.md },
  todayPnl: { fontSize: 24, fontWeight: '700' },
  actionsGrid: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm },
  actionBtn: {
    flex: 1, alignItems: 'center', gap: Spacing.xs + 2,
    paddingVertical: Spacing.md, borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  actionIcon: { fontSize: 20 },
  actionLabel: { fontSize: FontSize.xs, fontWeight: '600' },
  warningBanner: { padding: Spacing.sm + 2, borderRadius: 10, borderWidth: 1 },
  signOut: { paddingVertical: Spacing.lg, marginBottom: Spacing.xl },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: Spacing.xl },
  tooltip: { padding: Spacing.md, borderRadius: 10, borderWidth: 1, maxWidth: 300, width: '100%' },
})
