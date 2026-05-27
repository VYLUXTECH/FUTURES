import { useState, useRef, useEffect } from 'react';
import { getSupabase } from '../services/supabase';
import type { NavigateFn } from '../App';

interface Props { navigate: NavigateFn; }

export default function Login({ navigate }: Props) {
  const emailRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

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
    if (!email.includes('@') || !email.includes('.')) {
      setError('Please enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      const sb = await getSupabase();
      if (!sb) {
        setError('Connecting... please retry.');
        setLoading(false);
        return;
      }
      const { error: authErr } = await sb.auth.signInWithPassword({ email, password });
      if (authErr) {
        setError(authErr.message);
        setLoading(false);
        return;
      }
      navigate('dashboard');
    } catch {
      setError('Network error. Check your connection and try again.');
      setLoading(false);
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
            <label htmlFor="loginEmail">Email Address</label>
            <input id="loginEmail" ref={emailRef} type="email" placeholder="trader@example.com"
              value={email} onChange={(e) => setEmail(e.target.value)} required
              className={error && !email ? 'input-error' : ''} />
          </div>
          <div className="field">
            <label htmlFor="loginPassword">Password</label>
            <div className="input-wrapper">
              <input id="loginPassword" type={showPassword ? 'text' : 'password'} placeholder="••••••••"
                value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}
                className={error && !password ? 'input-error' : ''} />
              <button type="button" className="toggle-password" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}>
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>
          <div className="forgot-link">
            <span style={{ cursor: 'pointer' }} onClick={() => navigate('forgot-password')}>Forgot password?</span>
          </div>
          <p className="error-text">{error}</p>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading && <span className="spinner" />}
            {loading ? 'Logging in...' : 'Login'}
          </button>
          <div className="auth-footer">
            Don't have an account?{' '}
            <span style={{ cursor: 'pointer', color: 'var(--text)', fontWeight: 600 }} onClick={() => navigate('signup')}>
              Create new account
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
