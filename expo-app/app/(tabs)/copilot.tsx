import { useState, useRef } from 'react'
import { View, TextInput, TouchableOpacity, ScrollView, KeyboardAvoidingView, Platform, Image, StyleSheet } from 'react-native'
import { ThemedView } from '../../components/ThemedView'
import { ThemedText } from '../../components/ThemedText'
import { Header } from '../../components/Header'
import { useTheme } from '../../contexts/ThemeContext'
import { useToast } from '../../components/Toast'
import { api } from '../../utils/api'
import { FontSize, Spacing, BorderRadius } from '../../constants/theme'

type Message = {
  role: 'user' | 'bot'
  text: string
  imageUrl?: string
}

const SUGGESTIONS = [
  { label: 'Balance', action: 'What is my account balance?' },
  { label: 'Trades', action: 'Show my open trades' },
  { label: 'Last trade', action: 'Explain the last trade' },
  { label: 'News', action: 'Any news affecting the market?' },
  { label: 'Chart', action: 'Generate a chart for GBPUSD' },
  { label: 'Stop', action: 'Stop the bot now' },
  { label: 'Clear', action: 'clear' },
]

export default function CopilotScreen() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: "👋 Hi, I'm FUTURES. Ask me anything trading related and your account management." }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState<string | null>(null)
  const scrollRef = useRef<ScrollView>(null)

  const { colors } = useTheme()
  const { showToast } = useToast()

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return

    if (text === 'clear') {
      setMessages([{ role: 'bot', text: 'Chat cleared. How can I help?' }])
      setInput('')
      return
    }

    const userMsg: Message = { role: 'user', text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setPendingConfirm(null)

    try {
      const res = await api.post<{
        reply: string
        image_url?: string
        requires_confirmation?: boolean
        confirmation_id?: string
        tool_results?: any
      }>('/copilot/chat', { message: text })

      if (res.reply) {
        const botMsg: Message = { role: 'bot', text: res.reply, imageUrl: res.image_url }
        setMessages(prev => [...prev, botMsg])
      }

      if (res.requires_confirmation && res.confirmation_id) {
        setPendingConfirm(res.confirmation_id)
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'bot', text: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  async function confirmAction() {
    if (!pendingConfirm) return
    setLoading(true)
    try {
      const res = await api.post<{ reply: string }>('/copilot/confirm', { confirmation_id: pendingConfirm })
      setMessages(prev => [...prev, { role: 'bot', text: res.reply }])
      setPendingConfirm(null)
    } catch (err: any) {
      showToast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  function handleSuggestion(label: string, action: string) {
    if (label === 'Clear') {
      setMessages([{ role: 'bot', text: 'Chat cleared. How can I help?' }])
      return
    }
    sendMessage(action)
  }

  return (
    <ThemedView style={styles.container}>
      <Header title="FUTURES" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.chatArea}
          contentContainerStyle={styles.chatContent}
          onContentSizeChange={() => scrollRef.current?.scrollToEnd()}
        >
          {messages.map((msg, i) => (
            <View
              key={i}
              style={[
                styles.messageBubble,
                msg.role === 'user'
                  ? { alignSelf: 'flex-end', backgroundColor: colors.primary }
                  : { alignSelf: 'flex-start', backgroundColor: colors.card },
              ]}
            >
              <ThemedText style={msg.role === 'user' ? { color: colors.primaryFg } : {}}>
                {msg.text}
              </ThemedText>
              {msg.imageUrl && (
                <Image
                  source={{ uri: msg.imageUrl }}
                  style={styles.chartImage}
                  resizeMode="contain"
                />
              )}
            </View>
          ))}

          {loading && (
            <View style={[styles.messageBubble, styles.typingIndicator, { alignSelf: 'flex-start', backgroundColor: colors.card }]}>
              <View style={styles.typingDots}>
                <View style={[styles.dot, { backgroundColor: colors.textMuted }]} />
                <View style={[styles.dot, styles.dot2, { backgroundColor: colors.textMuted }]} />
                <View style={[styles.dot, styles.dot3, { backgroundColor: colors.textMuted }]} />
              </View>
            </View>
          )}

          {/* Suggestions */}
          {messages.length <= 2 && !loading && (
            <View style={styles.suggestions}>
              {SUGGESTIONS.map((s, i) => (
                <TouchableOpacity
                  key={i}
                  style={[styles.chip, { borderColor: colors.cardBorder }]}
                  onPress={() => handleSuggestion(s.label, s.action)}
                >
                  <ThemedText muted style={{ fontSize: FontSize.xs }}>{s.label}</ThemedText>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {pendingConfirm && (
            <View style={styles.confirmRow}>
              <ThemedText muted style={{ fontSize: FontSize.xs, flex: 1 }}>
                This action requires confirmation:
              </ThemedText>
              <TouchableOpacity
                style={[styles.confirmBtn, { backgroundColor: colors.profit }]}
                onPress={confirmAction}
              >
                <ThemedText style={{ color: '#FFF', fontWeight: '700', fontSize: FontSize.xs }}>
                  Confirm
                </ThemedText>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>

        {/* Input */}
        <View style={[styles.inputRow, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Ask FUTURES..."
            placeholderTextColor={colors.textMuted}
            style={[styles.input, { backgroundColor: colors.inputBg, color: colors.text, borderColor: colors.border }]}
            onSubmitEditing={() => sendMessage(input)}
            returnKeyType="send"
          />
          <TouchableOpacity
            style={[styles.sendBtn, { backgroundColor: colors.primary }]}
            onPress={() => sendMessage(input)}
            disabled={loading}
          >
            <ThemedText style={{ color: colors.primaryFg, fontSize: 18 }}>→</ThemedText>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  flex: { flex: 1 },
  chatArea: { flex: 1, paddingHorizontal: Spacing.md },
  chatContent: { paddingVertical: Spacing.md, gap: Spacing.sm },
  messageBubble: { maxWidth: '85%', padding: Spacing.sm + 4, borderRadius: BorderRadius.lg, marginBottom: 4 },
  chartImage: { width: 250, height: 200, marginTop: Spacing.sm, borderRadius: BorderRadius.sm },
  typingIndicator: { paddingVertical: Spacing.sm, paddingHorizontal: Spacing.md, borderBottomLeftRadius: 4 },
  typingDots: { flexDirection: 'row', gap: 5, alignItems: 'center' },
  dot: { width: 6, height: 6, borderRadius: 3, opacity: 0.6 },
  dot2: { opacity: 0.4 },
  dot3: { opacity: 0.2 },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginTop: Spacing.md },
  chip: { paddingVertical: 6, paddingHorizontal: 14, borderRadius: BorderRadius.full, borderWidth: 1 },
  confirmRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, padding: Spacing.sm },
  confirmBtn: { paddingVertical: 8, paddingHorizontal: 20, borderRadius: BorderRadius.sm },
  inputRow: { flexDirection: 'row', alignItems: 'center', padding: Spacing.sm, gap: Spacing.sm, borderTopWidth: 1 },
  input: { flex: 1, height: 44, borderWidth: 1, borderRadius: BorderRadius.lg, paddingHorizontal: Spacing.md, fontSize: FontSize.md },
  sendBtn: { width: 44, height: 44, borderRadius: BorderRadius.full, alignItems: 'center', justifyContent: 'center' },
})
