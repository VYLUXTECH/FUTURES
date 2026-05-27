import { useState, useRef, useEffect } from 'react';
import { getSupabase } from '../services/supabase';
import type { NavigateFn } from '../App';

interface Props { navigate: NavigateFn; }

export default function Signup({ navigate }: Props) {
  const nameRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { nameRef.current?.focus(); }, []);

  useEffect(() => {
    getSupabase().then((sb) => {
      sb.auth.getSession().then((s) => {
        if (s.data.session) navigate('dashboard');
      });
    });
  }, [navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!name.trim()) { setError('Please enter a display name.'); return; }
    if (!email.includes('@') || !email.includes('.')) { setError('Please enter a valid email address.'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return; }
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    if (!agree) { setError('Please agree to the Terms & Conditions and Risk Disclosure.'); return; }
    setLoading(true);
    try {
      const sb = await getSupabase();
      if (!sb) { setError('Connecting... please retry.'); setLoading(false); return; }
      const result = await sb.auth.signUp({
        email, password,
        options: { data: { display_name: name } },
      });
      if (result.error) { setError(result.error.message); setLoading(false); return; }
      if (result.data?.user?.identities?.length === 0) {
        setError('An account with this email already exists.'); setLoading(false); return;
      }
      setSuccess('Account created! Check your email for confirmation.');
      setLoading(false);
      setTimeout(() => navigate('splash'), 2000);
    } catch {
      setError('Signup failed. Try again.'); setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <div className="auth-logo">
          <h1 style={{ cursor: 'pointer' }} onClick={() => navigate('splash')}>FUTURES</h1>
          <p>Price is the only Indicator</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Display Name</label>
            <input ref={nameRef} type="text" placeholder="Trader" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Email Address</label>
            <input type="email" placeholder="trader@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label>Password</label>
            <div className="input-wrapper">
              <input type={showPassword ? 'text' : 'password'} placeholder="Min. 6 characters"
                value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
              <button type="button" className="toggle-password" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}>
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>
          <div className="field">
            <label>Confirm Password</label>
            <div className="input-wrapper">
              <input type={showPassword ? 'text' : 'password'} placeholder="••••••••"
                value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={6} />
            </div>
          </div>
          <label className="agree-check">
            <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
            <span>I agree to the <span style={{ color: 'var(--text)', fontWeight: 600, cursor: 'pointer' }} onClick={() => navigate('legal', { tab: 'terms' })}>Terms & Conditions</span> and <span style={{ color: 'var(--text)', fontWeight: 600, cursor: 'pointer' }} onClick={() => navigate('legal', { tab: 'risk' })}>Risk Disclosure</span>.</span>
          </label>
          <p className="error-text">{error}</p>
          <p className="success-text">{success}</p>
          <button type="submit" className="btn-primary" disabled={loading || !agree}>
            {loading && <span className="spinner" />}
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
          <div className="auth-footer">
            Already have an account?{' '}
            <span style={{ cursor: 'pointer', color: 'var(--text)', fontWeight: 600 }} onClick={() => navigate('login')}>Sign in</span>
          </div>
        </form>
      </div>
    </div>
  );
}
