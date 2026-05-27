import type { NavigateFn } from '../App';
interface Props { navigate: NavigateFn; tab: 'terms' | 'risk'; }

export default function Legal({ navigate, tab }: Props) {
  return (
    <div className="auth-page">
      <div className="terms-card">
        <div className="card">
          <div className="terms-header">
            <button className="terms-back" onClick={() => navigate('signup')}>← Back</button>
            <h1>{tab === 'terms' ? 'Terms & Conditions' : 'Risk Disclosure'}</h1>
          </div>
          <div className="terms-body">
            {tab === 'terms' ? (
              <>
                <div className="terms-section"><h2>1. Acceptance of Terms</h2><p>By accessing and using the FUTURES trading platform, you agree to be bound by these Terms & Conditions. If you do not agree with any part of these terms, you must discontinue use immediately.</p></div>
                <div className="terms-section"><h2>2. Risk Acknowledgment</h2><p>Trading forex and other financial instruments carries significant risk. You acknowledge that you understand these risks and accept full responsibility for any losses incurred while using the platform.</p></div>
                <div className="terms-section"><h2>3. User Responsibilities</h2><p>You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You agree to use the platform in compliance with all applicable laws.</p></div>
                <div className="terms-section"><h2>4. Service Availability</h2><p>While we strive to provide uninterrupted service, we do not guarantee that the platform will be available at all times. We reserve the right to modify, suspend, or discontinue any aspect of the service at any time.</p></div>
                <div className="terms-section"><h2>5. Limitation of Liability</h2><p>FUTURES and its affiliates shall not be held liable for any direct, indirect, incidental, or consequential damages arising from your use of the platform, including but not limited to trading losses or technical failures.</p></div>
                <div className="terms-section"><h2>6. Amendments</h2><p>We reserve the right to update these terms at any time. Continued use of the platform after changes constitutes acceptance of the revised terms. You are encouraged to review these terms periodically.</p></div>
                <div className="terms-section"><h2>7. Contact</h2><p>If you have any questions about these Terms & Conditions, please contact us at support@futuretraders.com.</p></div>
              </>
            ) : (
              <>
                <div className="terms-section"><h2>Risk Disclosure</h2><p>Trading foreign exchange on margin carries a high level of risk and may not be suitable for all investors. You could sustain a total loss of your initial investment. Past performance does not guarantee future results.</p></div>
                <div className="terms-section"><h2>Leverage Risk</h2><p>Leverage can magnify both gains and losses. Small market movements can result in significant losses that may exceed your initial deposit. You should never risk more than you can afford to lose.</p></div>
                <div className="terms-section"><h2>Automated Trading</h2><p>Automated trading software may exhibit unexpected behavior due to market volatility, technical failures, or connectivity issues. You accept full responsibility for all trades executed by the bot.</p></div>
                <div className="terms-section"><h2>No Guarantee</h2><p>We do not guarantee profitability or specific trading outcomes. Historical performance is not indicative of future results. All trading decisions are your sole responsibility.</p></div>
                <div className="terms-section"><h2>Acknowledgement</h2><p>By using this platform, you confirm that you have read and understood this risk disclosure and accept full responsibility for all outcomes of your trading activities.</p></div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
