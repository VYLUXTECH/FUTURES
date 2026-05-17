import { useState, useEffect, useRef } from 'react'
import { View, TouchableOpacity, ScrollView, Switch, StyleSheet, ActivityIndicator, Platform } from 'react-native'
import { router } from 'expo-router'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { ThemedCard } from '../components/ThemedCard'
import { useTheme } from '../contexts/ThemeContext'
import { useToast } from '../components/Toast'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../utils/api'
import { supabase } from '../utils/supabase'
import * as Notifications from 'expo-notifications'
import * as Device from 'expo-device'
import { FontSize, Spacing, BorderRadius } from '../constants/theme'

const PREF_ITEMS = [
  { key: 'trade_execution', label: 'Trade Execution', desc: 'Alert when a new trade is placed' },
  { key: 'trade_closed', label: 'Trade Closed', desc: 'Alert on profit or loss' },
  { key: 'daily_summary', label: 'Daily Summary', desc: 'End-of-day performance report' },
  { key: 'loss_cooldown', label: 'Safety Alerts', desc: '3-loss cooldowns, MT5 disconnects' },
  { key: 'maintenance', label: 'Maintenance & Updates', desc: 'System downtime and features' },
]

export default function NotificationsScreen() {
  const [systemEnabled, setSystemEnabled] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [prefs, setPrefs] = useState<Record<string, boolean>>(
    Object.fromEntries(PREF_ITEMS.map(p => [p.key, true]))
  )
  const [saving, setSaving] = useState(false)
  const [skipLoading, setSkipLoading] = useState(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout>>()

  const { colors, theme, toggleTheme } = useTheme()
  const { showToast } = useToast()
  const { session } = useAuth()

  useEffect(() => {
    loadSettings()
  }, [])

  async function loadSettings() {
    try {
      const data = await api.get<{ notifications: Record<string, boolean> }>('/settings')
      if (data.notifications) setPrefs(prev => ({ ...prev, ...data.notifications }))
    } catch {}
  }

  function queueSave(updated: Record<string, boolean>) {
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await api.post('/settings', { notifications: updated })
      } catch {}
    }, 500)
  }

  function togglePref(key: string) {
    const next = { ...prefs, [key]: !prefs[key] }
    setPrefs(next)
    queueSave(next)
  }

  async function handleSystemToggle(enabled: boolean) {
    setSystemEnabled(enabled)
    if (!enabled) return

    setRequesting(true)
    try {
      let granted = false
      if (Platform.OS === 'web') {
        if ('Notification' in window) {
          const result = await Notification.requestPermission()
          granted = result === 'granted'
        } else {
          granted = true
        }
      } else {
        try {
          const { status } = await Notifications.requestPermissionsAsync()
          granted = status === 'granted'
          if (granted) {
            Notifications.setNotificationHandler({
              handleNotification: async () => ({
                shouldShowAlert: true,
                shouldPlaySound: true,
                shouldSetBadge: false,
              }),
            })
          }
        } catch {
          granted = true
        }
      }
      if (granted) {
        showToast('Notifications enabled!', 'success')
        // Save Expo push token to Supabase
        if (session?.user?.id && Platform.OS !== 'web') {
          try {
            const token = (await Notifications.getExpoPushTokenAsync({ projectId: 'futures-trading-bot' })).data
            if (token) {
              await supabase
                .from('profiles')
                .update({ expo_push_token: token })
                .eq('id', session.user.id)
            }
          } catch {}
        }
      } else {
        showToast('Permission denied — enable in device settings', 'error')
        setSystemEnabled(false)
        setRequesting(false)
        return
      }
    } catch {
      showToast('Could not request permission', 'error')
      setSystemEnabled(false)
      setRequesting(false)
      return
    }
    setRequesting(false)
  }

  async function saveAndGo() {
    setSaving(true)
    try {
      await api.post('/settings', { notifications: prefs })
      showToast('Preferences saved!', 'success')
      router.replace('/(tabs)/dashboard')
    } catch {
      showToast('Failed to save', 'error')
    } finally {
      setSaving(false)
    }
  }

  async function skip() {
    setSkipLoading(true)
    try {
      await api.post('/settings', { notifications: prefs })
    } catch {}
    router.replace('/(tabs)/dashboard')
  }

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <ThemedText style={{ fontSize: 16 }}>←</ThemedText>
            <ThemedText style={styles.backText}>Back</ThemedText>
          </TouchableOpacity>
          <ThemedText heading style={styles.pageTitle}>Notifications</ThemedText>
          <TouchableOpacity style={[styles.themeBtn, { backgroundColor: colors.card, borderColor: colors.cardBorder }]} onPress={toggleTheme}>
            {theme === 'dark' ? <ThemedText style={{ fontSize: 16 }}>☀️</ThemedText> : <ThemedText style={{ fontSize: 16 }}>🌙</ThemedText>}
          </TouchableOpacity>
        </View>

        {/* Permission Card */}
        <ThemedCard style={styles.permissionCard}>
          <View style={styles.bellWrap}>
            <ThemedText style={{ fontSize: 32 }}>🔔</ThemedText>
          </View>
          <ThemedText heading style={styles.permissionTitle}>Enable Notifications?</ThemedText>
          <ThemedText muted style={styles.permissionDesc}>
            Receive real-time alerts for trade executions, profits, and safety cooldowns.
            Critical for staying in control of your bot.
          </ThemedText>

          <View style={[styles.systemRow, { backgroundColor: colors.inputBg, borderColor: colors.border }]}>
            <ThemedText style={styles.systemLabel}>Allow Push Notifications</ThemedText>
            {requesting ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Switch
                value={systemEnabled}
                onValueChange={handleSystemToggle}
                trackColor={{ false: '#444', true: colors.primary }}
                thumbColor={systemEnabled ? colors.primaryFg : '#ccc'}
              />
            )}
          </View>

          {systemEnabled && (
            <View style={[styles.statusBadge, { backgroundColor: 'rgba(43,140,74,0.1)' }]}>
              <ThemedText style={{ color: colors.profit, fontSize: FontSize.xs, fontWeight: '700' }}>
                ✅ Notifications Enabled
              </ThemedText>
            </View>
          )}
        </ThemedCard>

        {/* Preferences Card */}
        <ThemedCard style={[styles.prefsCard, !systemEnabled && styles.prefsDisabled]}>
          <ThemedText muted style={styles.prefsLabel}>Notification Categories</ThemedText>
          {PREF_ITEMS.map(item => (
            <View key={item.key} style={[styles.prefRow, { borderBottomColor: colors.border }]}>
              <View style={styles.prefLabelWrap}>
                <ThemedText style={styles.prefLabel}>{item.label}</ThemedText>
                <ThemedText muted style={styles.prefDesc}>{item.desc}</ThemedText>
              </View>
              <Switch
                value={prefs[item.key]}
                onValueChange={() => togglePref(item.key)}
                disabled={!systemEnabled}
                trackColor={{ false: '#444', true: colors.primary }}
                thumbColor={prefs[item.key] ? colors.primaryFg : '#ccc'}
              />
            </View>
          ))}
        </ThemedCard>

        {/* Actions */}
        <TouchableOpacity
          style={[styles.saveBtn, { backgroundColor: colors.primary, opacity: saving ? 0.5 : 1 }]}
          onPress={saveAndGo}
          disabled={saving}
          activeOpacity={0.8}
        >
          {saving ? (
            <ActivityIndicator color={colors.primaryFg} size="small" />
          ) : (
            <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', fontSize: FontSize.md, textAlign: 'center' }}>
              Save Preferences
            </ThemedText>
          )}
        </TouchableOpacity>

        <TouchableOpacity style={styles.skipBtn} onPress={skip} disabled={skipLoading}>
          {skipLoading ? (
            <ThemedText muted style={{ textAlign: 'center' }}>Loading...</ThemedText>
          ) : (
            <ThemedText muted style={{ textAlign: 'center' }}>Skip for now</ThemedText>
          )}
        </TouchableOpacity>

        <ThemedText muted style={styles.footer}>You can change these later in Settings</ThemedText>
      </ScrollView>
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
  permissionCard: { alignItems: 'center', padding: Spacing.lg, gap: Spacing.sm },
  bellWrap: {
    width: 64, height: 64, borderRadius: 32,
    backgroundColor: 'rgba(43,110,240,0.1)',
    alignItems: 'center', justifyContent: 'center',
    marginBottom: Spacing.xs,
  },
  permissionTitle: { fontSize: 20, fontWeight: '700', textAlign: 'center' },
  permissionDesc: { fontSize: FontSize.sm, color: '#888', textAlign: 'center', lineHeight: 20 },
  systemRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: Spacing.md, borderRadius: 12, borderWidth: 1, width: '100%',
  },
  systemLabel: { fontWeight: '600', fontSize: FontSize.sm },
  statusBadge: { paddingHorizontal: Spacing.sm, paddingVertical: 4, borderRadius: 6 },
  prefsCard: { padding: Spacing.md + 4, gap: Spacing.xs },
  prefsDisabled: { opacity: 0.5 },
  prefsLabel: {
    fontSize: FontSize.sm, fontWeight: '600', textTransform: 'uppercase',
    letterSpacing: 0.5, marginBottom: Spacing.sm,
  },
  prefRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: Spacing.sm + 2, borderBottomWidth: 1,
  },
  prefLabelWrap: { flex: 1, gap: 2 },
  prefLabel: { fontSize: FontSize.sm, fontWeight: '500' },
  prefDesc: { fontSize: FontSize.xs },
  saveBtn: {
    height: 52, borderRadius: BorderRadius.md,
    alignItems: 'center', justifyContent: 'center',
  },
  skipBtn: { paddingVertical: Spacing.md },
  footer: { textAlign: 'center', fontSize: FontSize.xs },
})
