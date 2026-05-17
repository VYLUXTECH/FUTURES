import { useState } from 'react'
import { View, TextInput, TouchableOpacity, ScrollView, StyleSheet, Platform } from 'react-native'
import { ThemedView } from '../../components/ThemedView'
import { ThemedText } from '../../components/ThemedText'
import { ThemedCard } from '../../components/ThemedCard'
import { Header } from '../../components/Header'
import { useTheme } from '../../contexts/ThemeContext'
import { useToast } from '../../components/Toast'
import { api } from '../../utils/api'
import { FontSize, Spacing, BorderRadius } from '../../constants/theme'

const FAQS = [
  { q: 'How do I connect MT5?', a: 'Go to Settings and enter your MT5 credentials. Ensure automated trading is enabled in MT5.' },
  { q: 'What pairs does the bot trade?', a: 'GBPUSD, GBPJPY, and USDJPY.' },
  { q: 'How is risk managed?', a: 'The bot uses a 5% daily drawdown limit, max 5 trades/day, and a 3-loss cooldown.' },
  { q: 'What timeframe does the bot use?', a: '1-minute candles with analysis on multiple timeframes (M15, 1H, 4H).' },
  { q: 'Can I run the bot 24/7?', a: 'The bot only trades during 10:00-20:00 EAT market hours.' },
]

export default function SupportScreen() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [fileName, setFileName] = useState('')
  const [openFaq, setOpenFaq] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  const { colors } = useTheme()
  const { showToast } = useToast()

  async function handleSubmit() {
    if (!title || !description) {
      showToast('Title and description are required.', 'error')
      return
    }
    setLoading(true)
    try {
      await api.post('/support/ticket', {
        title,
        description,
      })
      setTitle('')
      setDescription('')
      setFileName('')
      showToast('Issue submitted. We will respond within 24 hours.', 'success')
    } catch (err: any) {
      showToast(err?.message || 'Submission failed. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ThemedView style={styles.container}>
      <Header title="Support" />
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* Issue Form */}
        <ThemedCard>
          <ThemedText heading style={styles.sectionTitle}>Report an Issue</ThemedText>
          <TextInput
            placeholder="Brief description of the issue"
            placeholderTextColor={colors.textMuted}
            value={title}
            onChangeText={setTitle}
            style={[styles.input, { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }]}
          />
          <TextInput
            placeholder="Please provide details..."
            placeholderTextColor={colors.textMuted}
            value={description}
            onChangeText={setDescription}
            multiline
            numberOfLines={4}
            style={[styles.input, styles.textArea, { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }]}
          />
          <TouchableOpacity style={[styles.uploadBtn, { borderColor: colors.border }]}>
            <ThemedText muted style={{ textAlign: 'center' }}>
              {fileName || 'Upload Image'}
            </ThemedText>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.button, { backgroundColor: colors.primary }]} onPress={handleSubmit} disabled={loading}>
            <ThemedText style={{ color: colors.primaryFg, fontWeight: '700', textAlign: 'center' }}>
              {loading ? 'Submitting...' : 'Submit Issue'}
            </ThemedText>
          </TouchableOpacity>
        </ThemedCard>

        {/* Contact */}
        <ThemedCard>
          <ThemedText heading style={styles.sectionTitle}>Contact Us</ThemedText>
          <TouchableOpacity style={styles.contactRow}>
            <ThemedText>✉️ support@futuretraders.net</ThemedText>
          </TouchableOpacity>
          <TouchableOpacity style={styles.contactRow}>
            <ThemedText>📱 @+256704909060</ThemedText>
          </TouchableOpacity>
        </ThemedCard>

        {/* FAQ */}
        <ThemedCard>
          <ThemedText heading style={styles.sectionTitle}>FAQ</ThemedText>
          {FAQS.map((faq, i) => (
            <TouchableOpacity
              key={i}
              style={[styles.faqItem, { borderBottomColor: colors.border }]}
              onPress={() => setOpenFaq(openFaq === i ? null : i)}
            >
              <View style={styles.faqHeader}>
                <ThemedText style={{ flex: 1, fontWeight: '600', fontSize: FontSize.sm }}>{faq.q}</ThemedText>
                <ThemedText muted>{openFaq === i ? '▲' : '▼'}</ThemedText>
              </View>
              {openFaq === i && (
                <ThemedText muted style={{ marginTop: Spacing.sm, lineHeight: 20 }}>{faq.a}</ThemedText>
              )}
            </TouchableOpacity>
          ))}
        </ThemedCard>
      </ScrollView>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: { padding: Spacing.md, gap: Spacing.md, paddingBottom: 100 },
  sectionTitle: { fontSize: FontSize.md, fontWeight: '700', marginBottom: Spacing.sm },
  input: { height: 48, borderWidth: 1, borderRadius: BorderRadius.md, paddingHorizontal: Spacing.md, fontSize: FontSize.md },
  textArea: { height: 100, paddingTop: Spacing.sm, textAlignVertical: 'top' },
  uploadBtn: { height: 48, borderWidth: 1, borderRadius: BorderRadius.md, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center' },
  button: { height: 48, borderRadius: BorderRadius.md, alignItems: 'center', justifyContent: 'center' },
  contactRow: { paddingVertical: Spacing.sm + 2 },
  faqItem: { paddingVertical: Spacing.sm, borderBottomWidth: 1 },
  faqHeader: { flexDirection: 'row', alignItems: 'center' },
})
