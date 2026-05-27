import { useState, useEffect, useCallback } from 'react';
import { saveMt5Credentials, testMt5Connection, loadMt5Credentials } from '../services/api';
import type { Mt5ConnectResult, SavedCredentials } from '../types';
import type { NavigateFn } from '../App';

const SERVERS = ['HFM-Demo', 'HFM-Live', 'HFM-Demo2', 'HFM-Real', 'Exness-Real', 'Exness-Demo', 'ICMarkets-Demo', 'ICMarkets-Real', 'Other (Type manually)'];

interface Props { navigate: NavigateFn; }

export default function Mt5(_props: Props) {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [server, setServer] = useState('');
  const [customServer, setCustomServer] = useState('');
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

  const selectedServer = server === 'Other (Type manually)' ? customServer.trim() : server;

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!login || !password || !selectedServer) { showMsg('Please fill in all fields.', 'error'); return; }
    setLoading(true); setResult(null); setToast(null);
    try {
      const saveData = await saveMt5Credentials(login, password, selectedServer);
      if (saveData.error) { showMsg('Failed to save: ' + saveData.error, 'error'); setLoading(false); return; }
      const connectResult = await testMt5Connection(login, password, selectedServer);
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
            <select className="form-select" value={server} onChange={(e) => setServer(e.target.value)} required>
              <option value="" disabled>Select your broker server</option>
              {SERVERS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {server === 'Other (Type manually)' && (
              <input className="form-input" style={{ marginTop: '0.5rem' }} value={customServer}
                onChange={(e) => setCustomServer(e.target.value)} placeholder="Enter server name" autoFocus />
            )}
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
        <summary>ℹ️ How MT5 Connection Works</summary>
        <ol>
          <li>MT5 is installed on the server where the bot runs.</li>
          <li>Once you enter your credentials here, the bot reads them from the database, decrypts them, and auto-connects via <strong>mt5.initialize()</strong>.</li>
          <li>If MT5 isn't running, the bot launches it automatically from <strong>terminal64.exe</strong>.</li>
          <li>On the server, make sure <strong>Allow Algorithmic Trading</strong> is enabled in <strong>Tools → Options → Expert Advisors</strong>.</li>
          <li>The bot reconnects on each restart — no need to re-enter credentials.</li>
        </ol>
      </details>
    </div>
  );
}
