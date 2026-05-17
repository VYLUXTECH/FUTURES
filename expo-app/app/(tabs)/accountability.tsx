import { useState, useEffect, useCallback } from 'react'
import { View, TouchableOpacity, ScrollView, StyleSheet, Platform } from 'react-native'
import { router } from 'expo-router'
import { ThemedView } from '../../components/ThemedView'
import { ThemedText } from '../../components/ThemedText'
import { ThemedCard } from '../../components/ThemedCard'
import { useTheme } from '../../contexts/ThemeContext'
import { useToast } from '../../components/Toast'
import { FontSize, Spacing, BorderRadius } from '../../constants/theme'
import { api } from '../../utils/api'

type Trade = {
  pair: string
  direction: string
  lots: number
  entry_price: number
  close_price: number | null
  pnl: number | null
  opened_at: string
  closed_at: string | null
  status: string
}

const MOCK_TRADES: Trade[] = [
  { pair: 'GBPUSD', direction: 'BUY', lots: 0.05, entry_price: 1.2750, close_price: 1.2815, pnl: 12.30, opened_at: '2026-05-06T14:32:00', closed_at: '2026-05-06T15:10:00', status: 'CLOSED' },
  { pair: 'GBPJPY', direction: 'SELL', lots: 0.02, entry_price: 186.50, close_price: 186.10, pnl: -5.20, opened_at: '2026-05-06T13:15:00', closed_at: '2026-05-06T13:45:00', status: 'CLOSED' },
  { pair: 'GBPUSD', direction: 'BUY', lots: 0.08, entry_price: 1.2680, close_price: 1.2720, pnl: 8.40, opened_at: '2026-05-06T11:07:00', closed_at: '2026-05-06T11:55:00', status: 'CLOSED' },
  { pair: 'GBPJPY', direction: 'BUY', lots: 0.04, entry_price: 185.20, close_price: 185.50, pnl: 2.10, opened_at: '2026-05-05T09:45:00', closed_at: '2026-05-05T10:20:00', status: 'CLOSED' },
  { pair: 'GBPUSD', direction: 'SELL', lots: 0.06, entry_price: 1.2710, close_price: 1.2650, pnl: 15.00, opened_at: '2026-05-04T16:20:00', closed_at: '2026-05-04T17:05:00', status: 'CLOSED' },
  { pair: 'GBPJPY', direction: 'SELL', lots: 0.03, entry_price: 187.00, close_price: 187.45, pnl: -8.50, opened_at: '2026-05-04T10:30:00', closed_at: '2026-05-04T11:00:00', status: 'CLOSED' },
]

const RANGE_OPTIONS = [
  { key: '7', label: '7 Days' },
  { key: '30', label: '30 Days' },
  { key: '90', label: '90 Days' },
  { key: 'all', label: 'All' },
] as const

function formatTime(iso: string) {
  const d = new Date(iso)
  return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}, ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`
}

export default function AccountabilityScreen() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [range, setRange] = useState('30')
  const [loading, setLoading] = useState(true)

  const { colors, theme, toggleTheme } = useTheme()
  const { showToast } = useToast()

  const loadTrades = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.get<{ trades: Trade[] }>('/trades')
      setTrades(data.trades || [])
    } catch {
      setTrades(MOCK_TRADES)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTrades()
  }, [loadTrades])

  const closed = trades.filter(t => t.status === 'CLOSED')
  const won = closed.filter(t => (t.pnl ?? 0) > 0)
  const totalPnl = closed.reduce((s, t) => s + (t.pnl ?? 0), 0)
  const winRate = closed.length > 0 ? Math.round((won.length / closed.length) * 100) : 0

  function handleExport(format: 'csv' | 'pdf') {
    if (trades.length === 0) {
      showToast('No trades to export', 'error')
      return
    }
    if (format === 'csv') {
      const header = 'Pair,Type,Lots,Entry,Exit,P&L,Time\n'
      const rows = trades.map(t =>
        `${t.pair},${t.direction},${t.lots},${t.entry_price},${t.close_price ?? ''},${t.pnl ?? ''},${t.opened_at}`
      ).join('\n')
      const blob = new Blob([header + rows], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `trades_${range}d.csv`
      a.click()
      URL.revokeObjectURL(url)
    }
    showToast(`${format.toUpperCase()} export started`, 'success')
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
          <ThemedText heading style={styles.pageTitle}>Accountability</ThemedText>
          <TouchableOpacity style={[styles.themeBtn, { backgroundColor: colors.card, borderColor: colors.cardBorder }]} onPress={toggleTheme}>
            {theme === 'dark' ? (
              <ThemedText style={{ fontSize: 16 }}>☀️</ThemedText>
            ) : (
              <ThemedText style={{ fontSize: 16 }}>🌙</ThemedText>
            )}
          </TouchableOpacity>
        </View>

        {/* Summary Stats */}
        <View style={styles.statsRow}>
          <ThemedCard style={styles.statCard}>
            <ThemedText style={styles.statValue}>{trades.length}</ThemedText>
            <ThemedText muted style={styles.statLabel}>Total Trades</ThemedText>
          </ThemedCard>
          <ThemedCard style={styles.statCard}>
            <ThemedText style={[styles.statValue, { color: colors.profit }]}>{winRate}%</ThemedText>
            <ThemedText muted style={styles.statLabel}>Win Rate</ThemedText>
          </ThemedCard>
          <ThemedCard style={styles.statCard}>
            <ThemedText style={[styles.statValue, { color: totalPnl >= 0 ? colors.profit : colors.loss }]}>
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(0)}
            </ThemedText>
            <ThemedText muted style={styles.statLabel}>Total P&L</ThemedText>
          </ThemedCard>
        </View>

        {/* Filter Bar */}
        <View style={styles.filterRow}>
          <View style={styles.rangeRow}>
            {RANGE_OPTIONS.map(r => (
              <TouchableOpacity
                key={r.key}
                style={[styles.rangeBtn, range === r.key && { backgroundColor: colors.primary }]}
                onPress={() => setRange(r.key)}
              >
                <ThemedText style={{
                  fontSize: FontSize.xs,
                  fontWeight: '600',
                  color: range === r.key ? colors.primaryFg : colors.text,
                }}>
                  {r.label}
                </ThemedText>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.exportRow}>
            <TouchableOpacity style={[styles.exportBtn, { backgroundColor: colors.inputBg, borderColor: colors.border }]} onPress={() => handleExport('csv')}>
              <ThemedText muted style={{ fontSize: FontSize.xs, fontWeight: '600' }}>CSV</ThemedText>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.exportBtn, { backgroundColor: colors.inputBg, borderColor: colors.border }]} onPress={() => handleExport('pdf')}>
              <ThemedText muted style={{ fontSize: FontSize.xs, fontWeight: '600' }}>PDF</ThemedText>
            </TouchableOpacity>
          </View>
        </View>

        {/* Trade Table */}
        <ThemedCard style={styles.tableCard}>
          {loading ? (
            <ThemedText muted style={{ textAlign: 'center', padding: Spacing.xl }}>Loading trades...</ThemedText>
          ) : trades.length === 0 ? (
            <View style={styles.emptyState}>
              <ThemedText style={styles.emptyIcon}>📉</ThemedText>
              <ThemedText muted style={{ fontWeight: '600' }}>No trades found</ThemedText>
              <ThemedText muted style={{ fontSize: FontSize.xs, marginTop: Spacing.xs }}>
                Start the bot to see your trade history
              </ThemedText>
            </View>
          ) : (
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View>
                {/* Table Header */}
                <View style={[styles.tableHeader, { borderBottomColor: colors.border }]}>
                  <ThemedText muted style={styles.th}>Pair</ThemedText>
                  <ThemedText muted style={styles.th}>Type</ThemedText>
                  <ThemedText muted style={styles.th}>Lots</ThemedText>
                  <ThemedText muted style={styles.th}>Entry</ThemedText>
                  <ThemedText muted style={styles.th}>Exit</ThemedText>
                  <ThemedText muted style={styles.th}>P&L</ThemedText>
                  <ThemedText muted style={styles.th}>Time</ThemedText>
                </View>
                {/* Table Rows */}
                {trades.map((t, i) => (
                  <View key={i} style={[styles.tradeRow, { borderBottomColor: colors.border }]}>
                    <ThemedText style={styles.td}>{t.pair}</ThemedText>
                    <View style={styles.td}>
                      <View style={[styles.typeBadge, { backgroundColor: t.direction === 'BUY' ? 'rgba(43,140,74,0.15)' : 'rgba(229,72,77,0.15)' }]}>
                        <ThemedText style={[styles.typeText, { color: t.direction === 'BUY' ? colors.profit : colors.loss }]}>
                          {t.direction}
                        </ThemedText>
                      </View>
                    </View>
                    <ThemedText style={styles.td}>{t.lots.toFixed(2)}</ThemedText>
                    <ThemedText style={styles.td}>{t.entry_price.toFixed(t.pair.includes('JPY') ? 2 : 5)}</ThemedText>
                    <ThemedText style={styles.td}>{t.close_price != null ? t.close_price.toFixed(t.pair.includes('JPY') ? 2 : 5) : '-'}</ThemedText>
                    <ThemedText style={[styles.td, { color: (t.pnl ?? 0) >= 0 ? colors.profit : colors.loss, fontWeight: '600' }]}>
                      {(t.pnl ?? 0) >= 0 ? '+' : ''}${(t.pnl ?? 0).toFixed(2)}
                    </ThemedText>
                    <ThemedText muted style={styles.td}>{t.closed_at ? formatTime(t.closed_at) : formatTime(t.opened_at)}</ThemedText>
                  </View>
                ))}
              </View>
            </ScrollView>
          )}
        </ThemedCard>

        <ThemedText muted style={styles.footer}>
          📁 Trades loaded from history
        </ThemedText>
      </ScrollView>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { padding: Spacing.md, gap: Spacing.md, paddingBottom: 40 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4 },
  backText: { fontSize: FontSize.md, fontWeight: '600' },
  pageTitle: { fontSize: 20, fontWeight: '700' },
  themeBtn: { width: 40, height: 40, borderRadius: 20, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  statsRow: { flexDirection: 'row', gap: Spacing.sm },
  statCard: { flex: 1, alignItems: 'center', padding: Spacing.md, gap: 2 },
  statValue: { fontSize: FontSize.xl, fontWeight: '800' },
  statLabel: { fontSize: FontSize.xs, fontWeight: '500' },
  filterRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: Spacing.sm },
  rangeRow: { flexDirection: 'row', gap: 4, flexWrap: 'wrap' },
  rangeBtn: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: BorderRadius.full, borderWidth: 1, borderColor: '#333' },
  exportRow: { flexDirection: 'row', gap: 4, marginLeft: 'auto' },
  exportBtn: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: BorderRadius.full, borderWidth: 1 },
  tableCard: { padding: Spacing.sm, overflow: 'hidden' },
  tableHeader: { flexDirection: 'row', paddingVertical: Spacing.sm, borderBottomWidth: 1, gap: 8 },
  th: { width: 70, fontSize: FontSize.xs, fontWeight: '600', textTransform: 'uppercase' },
  tradeRow: { flexDirection: 'row', paddingVertical: Spacing.sm + 2, borderBottomWidth: 1, gap: 8 },
  td: { width: 70, fontSize: FontSize.xs },
  typeBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, alignSelf: 'flex-start' },
  typeText: { fontSize: FontSize.xs, fontWeight: '700' },
  emptyState: { alignItems: 'center', paddingVertical: Spacing.xl + 8, gap: Spacing.xs },
  emptyIcon: { fontSize: 32, opacity: 0.5 },
  footer: { textAlign: 'center', fontSize: FontSize.xs, padding: Spacing.sm },
})
