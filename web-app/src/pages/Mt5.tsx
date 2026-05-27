import { useState, useEffect, useCallback } from 'react';
import { saveMt5Credentials, testMt5Connection, loadMt5Credentials } from '../services/api';
import type { Mt5ConnectResult, SavedCredentials } from '../types';
import type { NavigateFn } from '../App';

interface Props { navigate: NavigateFn; }

export default function Mt5(_props: Props) {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [server, setServer] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Mt5ConnectResult | null>(null);
  const [saved, setSaved] = useState<SavedCredentials | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);

  useEffect(() => { loadMt5Credentials().then(setSaved); }, []);

  const showMsg = useCallback((text: string, type: string) => {
    setToast({ msg: text, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!login || !password || !server.trim()) { showMsg('Please fill in all fields.', 'error'); return; }
    setLoading(true); setResult(null); setToast(null);
    try {
      const saveData = await saveMt5Credentials(login, password, server.trim());
      if (saveData.error) { showMsg('Failed to save: ' + saveData.error, 'error'); setLoading(false); return; }
      const connectResult = await testMt5Connection(login, password, server.trim());
      setResult(connectResult);
      if (connectResult.connected) {
        showMsg('Connected! Auto trading: ' + (connectResult.automated_trading_enabled ? 'Enabled' : 'Disabled'), connectResult.automated_trading_enabled ? 'success' : 'info');
      } else if (connectResult.error) {
        showMsg('Failed: ' + connectResult.error, 'error');
      } else {
        showMsg('Credentials saved.', 'info');
      }
      const creds = await loadMt5Credentials();
      setSaved(creds);
    } catch { showMsg('Network error.', 'error'); } finally { setLoading(false); }
  }

  return (
    <div className="page page-mt5">
      {toast && <div className={`toast-global visible ${toast.type}`}>{toast.msg}</div>}

      <div className="card">
        <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>
          MT5 Connection
        </h2>
        <form onSubmit={handleConnect}>
          <div className="form-group">
            <label>MT5 Login ID</label>
            <input className="form-input" value={login} onChange={(e) => setLogin(e.target.value.replace(/[^0-9]/g, ''))}
              placeholder="e.g. 12345678" inputMode="numeric" required />
          </div>
          <div className="form-group">
            <label>MT5 Password</label>
            <div className="input-wrapper">
              <input type={showPassword ? 'text' : 'password'} className="form-input"
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••" required />
              <button type="button" className="toggle-password" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}>
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>
          <div className="form-group">
            <label>MT5 Server</label>
            <input className="form-input" value={server} onChange={(e) => setServer(e.target.value)}
              placeholder="e.g. Exness-Real, HFM-Demo" required />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading && <span className="spinner" />}
            {loading ? 'Connecting...' : 'Connect & Test'}
          </button>
        </form>
      </div>

      {result && (
        <div className="card">
          <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>
            Connection Result
          </h2>
          <div className="result-row">
            <span className="result-label">Status</span>
            <span className={`connection-badge ${result.connected ? 'connected' : 'disconnected'}`}>
              {result.connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          {result.account && (
            <>
              <div className="result-row"><span className="result-label">Account</span><span className="result-value">{result.account.login}</span></div>
              <div className="result-row"><span className="result-label">Server</span><span className="result-value">{result.account.server ?? '-'}</span></div>
              <div className="result-row"><span className="result-label">Balance</span><span className="result-value">${(result.account.balance ?? 0).toFixed(2)}</span></div>
              <div className="result-row"><span className="result-label">Equity</span><span className="result-value">${(result.account.equity ?? 0).toFixed(2)}</span></div>
              <div className="result-row"><span className="result-label">Leverage</span><span className="result-value">1:{result.account.leverage ?? 0}</span></div>
              <div className="result-row"><span className="result-label">Currency</span><span className="result-value">{result.account.currency ?? 'USD'}</span></div>
            </>
          )}
          <div className="result-row">
            <span className="result-label">Auto Trading</span>
            <span className={`connection-badge ${result.automated_trading_enabled ? 'connected' : 'disconnected'}`}>
              {result.automated_trading_enabled ? 'Yes' : 'No'}
            </span>
          </div>
        </div>
      )}

      {saved && (
        <div className="card">
          <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>
            Saved Account
          </h2>
          <div className="saved-info">
            <div className="saved-row"><span className="saved-label">Login</span><span className="saved-value">{saved.login ?? '-'}</span></div>
            <div className="saved-row"><span className="saved-label">Server</span><span className="saved-value">{saved.server ?? '-'}</span></div>
            <div className="saved-row">
              <span className="saved-label">Status</span>
              <span className={`connection-badge ${saved.connected ? 'connected' : 'disconnected'}`}>
                {saved.connected ? 'Connected' : 'Not connected'}
              </span>
            </div>
          </div>
        </div>
      )}

      <details className="card">
        <summary>ℹ️ How It Works</summary>
        <ol>
          <li>Enter your MT5 login, password, and server below.</li>
          <li>Your password is encrypted before storage — never stored in plaintext.</li>
          <li>The bot decrypts and uses your credentials to connect automatically.</li>
          <li>Credentials are saved — no need to re-enter on restart.</li>
        </ol>
      </details>
    </div>
  );
}
