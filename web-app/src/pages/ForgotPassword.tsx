import { useState, useRef, useEffect, useCallback } from 'react';
import { getSupabase } from '../services/supabase';
import type { NavigateFn } from '../App';

interface Props { navigate: NavigateFn; }

type Step = 1 | 2 | 3;

export default function ForgotPassword({ navigate }: Props) {
  const emailRef = useRef<HTMLInputElement>(null);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
  const [step, setStep] = useState<Step>(1);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState<string[]>(Array(6).fill(''));
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [otpTimer, setOtpTimer] = useState(0);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);

  const showToast = useCallback((msg: string, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  useEffect(() => { emailRef.current?.focus(); }, []);

  // OTP timer
  useEffect(() => {
    if (otpTimer <= 0) return;
    const id = setInterval(() => {
      setOtpTimer((t) => {
        if (t <= 1) { clearInterval(id); return 0; }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [otpTimer]);

  function handleOtpChange(index: number, value: string) {
    const digit = value.replace(/[^0-9]/g, '').slice(0, 1);
    const newOtp = [...otp];
    newOtp[index] = digit;
    setOtp(newOtp);
    if (digit && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  }

  function handleOtpKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const newOtp = [...otp];
      newOtp[index - 1] = '';
      setOtp(newOtp);
      otpRefs.current[index - 1]?.focus();
    }
  }

  function handleOtpPaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const data = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6);
    if (!data) return;
    const newOtp = [...otp];
    data.split('').forEach((char, i) => { if (i < 6) newOtp[i] = char; });
    setOtp(newOtp);
    const focusIndex = Math.min(data.length, 5);
    otpRefs.current[focusIndex]?.focus();
  }

  function resetToStep1() {
    setStep(1);
    setEmail('');
    setOtp(Array(6).fill(''));
    setNewPassword('');
    setConfirmPassword('');
    setOtpTimer(0);
  }

  async function handleSendCode(e: React.FormEvent) {
    e.preventDefault();
    if (!email.includes('@')) { showToast('Please enter a valid email.', 'error'); return; }
    setLoading(true);
    try {
      const sb = await getSupabase();
      if (!sb) { showToast('Connecting... please retry.', 'error'); setLoading(false); return; }
      const { error } = await sb.auth.resetPasswordForEmail(email);
      if (error) { showToast('Failed to send: ' + error.message, 'error'); setLoading(false); return; }
      setStep(2);
      setOtpTimer(60);
      setTimeout(() => otpRefs.current[0]?.focus(), 100);
      showToast('Code sent to your email!');
    } catch { showToast('Network error. Try again.', 'error'); }
    finally { setLoading(false); }
  }

  async function handleResendCode() {
    if (!email) { showToast('No email to resend to.', 'error'); return; }
    setLoading(true);
    try {
      const sb = await getSupabase();
      if (!sb) return;
      const { error } = await sb.auth.resetPasswordForEmail(email);
      if (error) { showToast('Failed to resend: ' + error.message, 'error'); setLoading(false); return; }
      setOtpTimer(60);
      showToast('Code resent!');
    } catch { showToast('Network error.', 'error'); }
    finally { setLoading(false); }
  }

  async function handleVerifyCode() {
    const code = otp.join('');
    if (code.length !== 6) return;
    setLoading(true);
    try {
      const sb = await getSupabase();
      if (!sb) { showToast('Connecting... please retry.', 'error'); setLoading(false); return; }
      const { error } = await sb.auth.verifyOtp({ email, token: code, type: 'recovery' });
      if (error) {
        showToast('Invalid code. Try again.', 'error');
        setOtp(Array(6).fill(''));
        otpRefs.current[0]?.focus();
        setLoading(false);
        return;
      }
      setStep(3);
      showToast('Code verified!');
    } catch { showToast('Verification failed.', 'error'); }
    finally { setLoading(false); }
  }

  async function handleUpdatePassword(e: React.FormEvent) {
    e.preventDefault();
    if (!newPassword || newPassword.length < 6) { showToast('Password must be at least 6 chars.', 'error'); return; }
    if (newPassword !== confirmPassword) { showToast('Passwords do not match.', 'error'); return; }
    setLoading(true);
    try {
      const sb = await getSupabase();
      if (!sb) { showToast('Connecting... please retry.', 'error'); setLoading(false); return; }
      const { error } = await sb.auth.updateUser({ password: newPassword });
      if (error) { showToast('Failed to update: ' + error.message, 'error'); setLoading(false); return; }
      showToast('Password updated successfully!');
      setTimeout(() => navigate('login'), 1000);
    } catch { showToast('Update failed. Please try again.', 'error'); }
    finally { setLoading(false); }
  }

  return (
    <div className="auth-page">
      {toast && <div className={`toast-global visible ${toast.type}`}>{toast.msg}</div>}
      <div className="auth-card card">
        <div className="fp-header">
          <button className="back-btn" onClick={() => step === 1 ? navigate('login') : resetToStep1()}>← Back</button>
          <h1 className="page-title" style={{ fontSize: '1.1rem', fontWeight: 600 }}>Reset Password</h1>
        </div>

        {/* Step 1: Email */}
        <div className={step !== 1 ? 'hidden' : ''}>
          <div className="step-indicator">
            <div className="step-dot active" />
            <div className="step-dot" />
            <div className="step-dot" />
          </div>
          <p className="instruction-text">Enter your email address. We'll send you a 6-digit code to reset your password.</p>
          <form onSubmit={handleSendCode}>
            <div className="field">
              <label>Email Address</label>
              <input ref={emailRef} type="email" placeholder="trader@example.com"
                value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <p className="error-text">&nbsp;</p>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading && <span className="spinner" />}
              {loading ? 'Sending...' : 'Send Code'}
            </button>
          </form>
        </div>

        {/* Step 2: OTP */}
        <div className={step !== 2 ? 'hidden' : ''}>
          <div className="step-indicator">
            <div className="step-dot active" />
            <div className="step-dot active" />
            <div className="step-dot" />
          </div>
          <p className="instruction-text">
            We've sent a 6-digit code to <strong>{email}</strong>. Please check your inbox and spam folder.
          </p>
          <div className="otp-container" onPaste={handleOtpPaste}>
            {otp.map((digit, i) => (
              <input key={i} ref={(el) => { otpRefs.current[i] = el; }}
                type="text" className={`otp-input ${digit ? 'filled' : ''}`}
                maxLength={1} inputMode="numeric"
                value={digit} onChange={(e) => handleOtpChange(i, e.target.value)}
                onKeyDown={(e) => handleOtpKeyDown(i, e)} />
            ))}
          </div>
          <div className="resend-row">
            <button className="resend-link" disabled={otpTimer > 0 || loading} onClick={handleResendCode}>
              Resend Code {otpTimer > 0 && <span>({otpTimer}s)</span>}
            </button>
          </div>
          <button className="btn-primary" disabled={otp.join('').length !== 6 || loading} onClick={handleVerifyCode}>
            {loading && <span className="spinner" />}
            {loading ? 'Verifying...' : 'Verify Code'}
          </button>
        </div>

        {/* Step 3: New Password */}
        <div className={step !== 3 ? 'hidden' : ''}>
          <div className="step-indicator">
            <div className="step-dot active" />
            <div className="step-dot active" />
            <div className="step-dot active" />
          </div>
          <p className="instruction-text">Code verified. Enter your new password below.</p>
          <form onSubmit={handleUpdatePassword}>
            <div className="field">
              <label>New Password</label>
              <div className="input-wrapper">
                <input type={showPassword ? 'text' : 'password'} placeholder="Min. 6 characters"
                  value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6} />
                <button type="button" className="toggle-password" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}>
                  {showPassword ? '🙈' : '👁️'}
                </button>
              </div>
            </div>
            <div className="field">
              <label>Confirm New Password</label>
              <div className="input-wrapper">
                <input type={showPassword ? 'text' : 'password'} placeholder="••••••••"
                  value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} />
              </div>
            </div>
            <p className="error-text">&nbsp;</p>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading && <span className="spinner" />}
              {loading ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
