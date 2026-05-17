import { useEffect, useRef } from 'react'
import { View, ScrollView, StyleSheet, Platform } from 'react-native'
import { useLocalSearchParams } from 'expo-router'
import * as Application from 'expo-application'
import { ThemedView } from '../components/ThemedView'
import { ThemedText } from '../components/ThemedText'
import { ThemedCard } from '../components/ThemedCard'
import { Header } from '../components/Header'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { supabase } from '../utils/supabase'
import { FontSize, Spacing, BorderRadius } from '../constants/theme'

const TERMS_SECTIONS = [
  {
    title: '1. Acknowledgement of Extreme Risk',
    body: 'Forex trading on margin is ONE OF THE RISKIEST FORMS OF INVESTMENT. You understand that automated trading software may exhibit unexpected behaviour due to market volatility, software errors, or connectivity issues. You accept full responsibility for all trading outcomes.',
  },
  {
    title: '2. No Financial or Investment Advice',
    body: 'FUTURES does not provide financial, investment, legal, tax, or trading advice. All information, chat responses, and software features are for informational and educational purposes only. Not Financial Advice.',
  },
  {
    title: '3. User Solely Responsible for All Trades',
    body: 'The Platform is execution-only. You are solely and exclusively responsible for all trading decisions and positions, regardless of whether placed manually or automatically. No fiduciary duty is assumed by VYLUX TECH',
  },
  {
    title: '4. Eligibility & Representations',
    body: 'You warrant that you are 18+, understand leveraged Forex risks, have sufficient capital to bear losses, and your use complies with local laws. We reserve the right to refuse service at our discretion.',
  },
  {
    title: '5. Account Registration & Security',
    body: 'You are responsible for maintaining credential confidentiality and all activities under your account. Notify us immediately of unauthorised use.',
  },
  {
    title: '6. Subscription Packages & Fees',
    body: 'Access requires a subscription (TRIAL, SPARK, SURGE, MEGA). ALL FEES ARE FINAL AND NON-REFUNDABLE regardless of profitability or unused trades. Fees are processed via Flutterwave. We may change fees with 30 days notice.',
  },
  {
    title: '7. Prohibited Conduct',
    body: 'You agree not to reverse-engineer, disable security, engage in fraud/money laundering, or access other users data.',
  },
  {
    title: '8. Technical Limitations & Third-Party Services',
    body: 'We rely on MT5, Supabase, Flutterwave, and cloud infrastructure. We are not responsible for third-party uptime, accuracy, or failures. Internet/electronic delays are inherent.',
  },
  {
    title: '9. DISCLAIMER OF WARRANTIES',
    body: 'THE PLATFORM IS PROVIDED "AS IS" AND "AS AVAILABLE". WE SPECIFICALLY DISCLAIM ALL IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT, ACCURACY, AND SECURITY. NO GUARANTEE OF PROFITABILITY OR UNINTERRUPTED SERVICE IS MADE.',
  },
  {
    title: '10. LIMITATION OF LIABILITY',
    body: 'TO THE MAXIMUM EXTENT PERMITTED BY LAW, VYLUX TECH SHALL NOT BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS OR TRADING LOSSES. OUR AGGREGATE LIABILITY SHALL NOT EXCEED THE TOTAL FEES PAID BY YOU IN THE SIX (6) MONTHS IMMEDIATELY PRECEDING THE CLAIM.',
  },
  {
    title: '11. Indemnification',
    body: 'You agree to indemnify and hold harmless VYLUX TECH from any claims arising from your use, breach of terms, or negligence.',
  },
  {
    title: '12. Governing Law & Dispute Resolution',
    body: 'This Agreement is governed by the laws of the Republic of Uganda. Any dispute shall be resolved by binding arbitration in Kampala under the Uganda Arbitration Centre rules. YOU WAIVE THE RIGHT TO A JURY TRIAL AND CLASS ACTION.',
  },
  {
    title: '13. Termination',
    body: 'You may terminate by deleting your account (no refunds). We may suspend/terminate for breach, fraud, or non-payment. Upon termination, remaining trades are forfeited.',
  },
  {
    title: '14. Modifications',
    body: 'We may amend terms by posting. Continued use constitutes acceptance. If you disagree, you must stop using the Platform.',
  },
  {
    title: '15. Entire Agreement & Severability',
    body: 'This Agreement, Privacy Policy, and Risk Disclosure constitute the entire agreement. If any provision is invalid, the remainder remains enforceable.',
  },
  {
    title: '16. Survival',
    body: 'Sections 1, 3, 9, 10, 11, 12, and indemnification clauses survive termination.',
  },
  {
    title: '17. Contact',
    body: 'Questions? Email: support@futuretraders.com | Whatsapp: +256704909060',
  },
]

const RISK_SECTIONS = [
  {
    title: 'IMPORTANT: READ CAREFULLY',
    body: 'Trading foreign exchange on margin carries a HIGH LEVEL OF RISK and may not be suitable for all investors. Leverage can work against you. YOU COULD SUSTAIN A TOTAL LOSS OF YOUR INITIAL CAPITAL.',
  },
  {
    title: '1. High Risk of Loss',
    body: 'You should not invest money you cannot afford to lose entirely. Past performance does not guarantee future results.',
  },
  {
    title: '2. Automated Trading Software Risks',
    body: 'The FUTURES bot is autonomous. Risks include: technical failures, connectivity issues, broker/MT5 limitations, market volatility, slippage, and news events. The bot mitigates but cannot eliminate these risks.',
  },
  {
    title: '3. No Guarantee of Profit',
    body: 'Historical performance is not indicative of future results. Markets are influenced by unpredictable factors. No assurance of target risk-reward ratios is made.',
  },
  {
    title: '4. User Responsibility',
    body: 'You are solely responsible for configuring parameters, monitoring balance, and disabling the bot when appropriate. The bot is a tool, not an advisor.',
  },
  {
    title: '5. No Advisory or Fiduciary Duty',
    body: 'VYLUX TECH is not registered as an investment adviser. No fiduciary relationship exists. We have no duty to evaluate trade suitability.',
  },
  {
    title: '6. Third-Party Services',
    body: 'We rely on MT5, chart providers, Supabase, and Flutterwave. We are not responsible for losses resulting from third-party failure or misperformance.',
  },
  {
    title: '7. Leverage Risks',
    body: 'Leverage magnifies gains and losses. A small adverse movement can quickly deplete your account. Risk settings do not limit total loss over multiple trades.',
  },
  {
    title: '8. Force Majeure',
    body: 'We are not liable for delays/failures due to acts of God, war, internet failures, power outages, or third-party interruptions.',
  },
  {
    title: '9. No Refund Policy',
    body: 'All subscription fees are non-refundable regardless of performance, technical difficulties, or other reasons. By purchasing, you accept full risk.',
  },
  {
    title: '10. Acknowledgement',
    body: 'I confirm I have read this disclosure, understand the high risks, accept sole responsibility for outcomes, and will not hold VYLUX TECH liable for financial or technical losses.',
  },
]

export default function LegalScreen() {
  const { tab: initialTab } = useLocalSearchParams<{ tab?: string }>()
  const tab = initialTab === 'risk' ? 'risk' : 'terms'
  const scrollRef = useRef<ScrollView>(null)
  const { colors } = useTheme()
  const { session } = useAuth()

  useEffect(() => {
    if (!session?.user?.id) return
    ;(async () => {
      try {
        let ip = ''
        try { const r = await fetch('https://api.ipify.org?format=json'); const d = await r.json(); ip = d.ip } catch {}
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
        let appVer = ''
        try { appVer = Application.nativeApplicationVersion || '' } catch {}
        const fingerprint = `${Platform.OS} | ${Platform.OS === 'web' ? screen.width : ''}x${Platform.OS === 'web' ? screen.height : ''} | ${tz} | v${appVer}`.trim()
        await supabase.from('legal_acceptances').insert({
          user_id: session.user.id,
          terms_version: '2.0',
          risk_version: '2.0',
          ip_address: ip,
          device_fingerprint: fingerprint,
          scroll_verified: false,
        })
      } catch {}
    })()
  }, [session])

  const title = tab === 'terms' ? 'Terms & Conditions' : 'Risk Disclosure'
  const sections = tab === 'terms' ? TERMS_SECTIONS : RISK_SECTIONS

  return (
    <ThemedView style={styles.container}>
      <Header title={title} showBack />

      <ScrollView ref={scrollRef} style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        <ThemedCard>
          <ThemedText muted style={styles.effective}>Effective: May 07, 2026</ThemedText>
          {sections.map((section, i) => (
            <View key={i} style={styles.section}>
              <ThemedText heading style={styles.sectionTitle}>{section.title}</ThemedText>
              <ThemedText muted style={styles.sectionBody}>{section.body}</ThemedText>
            </View>
          ))}
        </ThemedCard>
      </ScrollView>
    </ThemedView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scroll: { flex: 1, paddingHorizontal: Spacing.md },
  scrollContent: { paddingVertical: Spacing.md, gap: Spacing.md },
  effective: { fontSize: FontSize.xs, fontWeight: '600', marginBottom: Spacing.sm },
  section: { marginBottom: Spacing.md, paddingBottom: Spacing.md, borderBottomWidth: 1, borderBottomColor: '#222' },
  sectionTitle: { fontSize: FontSize.md, fontWeight: '600', marginBottom: Spacing.xs },
  sectionBody: { fontSize: FontSize.sm, lineHeight: 20 },
})
