import { useState, useEffect } from 'react';
import { saveMt5Credentials, testMt5Connection, loadMt5Credentials } from '../services/api';
import type { Mt5ConnectResult, SavedCredentials } from '../types';
import type { NavigateFn } from '../App';

const SERVERS = ['HFM-Demo', 'HFM-Live', 'HFM-Demo2', 'HFM-Real', 'Exness-Real', 'Exness-Demo', 'ICMarkets-Demo', 'ICMarkets-Real'];

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
  const [msg, setMsg] = useState<{ text: string; type: string } | null>(null);

  useEffect(() => { loadMt5Credentials().then(setSaved); }, []);

  function showMsg(text: string, type: string) {
    setMsg({ text, type });
    if (type === 'error') setTimeout(() => setMsg(null), 6000);
  }

  const selectedServer = server === 'custom' ? customServer.trim() : server;

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!login || !password || !selectedServer) { showMsg('Please fill in all fields.', 'error'); return; }
    setLoading(true); setResult(null); setMsg(null);
    try {
      const saveData = await saveMt5Credentials(login, password, selectedServer);
      if (saveData.error) { showMsg('Failed to save: ' + saveData.error, 'error'); setLoading(false); return; }
      const connectResult = await testMt5Connection(login, password, selectedServer);
      setResult(connectResult);
      if (connectResult.connected) showMsg('Connected! Auto trading: ' + (connectResult.automated_trading_enabled ? 'Enabled' : 'Disabled'), 'success');
      else if (connectResult.error) showMsg('Failed: ' + connectResult.error, 'error');
      else showMsg('Credentials saved.', 'info');
      const creds = await loadMt5Credentials();
      setSaved(creds);
    } catch { showMsg('Network error.', 'error'); } finally { setLoading(false); }
  }

  return (
    <div className="page page-mt5">
      {msg && <div className={`message-box ${msg.type}`} style={{ display: 'flex' }}>{msg.text}</div>}
      <div className="card">
        <h2>MT5 Connection</h2>
        <form onSubmit={handleConnect}>
          <div className="form-group">
            <label>MT5 Login</label>
            <input className="form-input" value={login} onChange={(e) => setLogin(e.target.value)} placeholder="e.g. 12345678" required />
          </div>
          <div className="form-group">
            <label>MT5 Password</label>
            <div className="input-wrapper">
              <input type={showPassword ? 'text' : 'password'} className="form-input" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
              <button type="button" className="toggle-password" onClick={() => setShowPassword(!showPassword)}>{showPassword ? '🙈' : '👁️'}</button>
            </div>
          </div>
          <div className="form-group">
            <label>MT5 Server</label>
            <select className="form-select" value={server} onChange={(e) => setServer(e.target.value)} required>
              <option value="" disabled>Select your broker server</option>
              {SERVERS.map((s) => <option key={s} value={s}>{s}</option>)}
              <option value="custom">Other (Type manually)</option>
            </select>
            {server === 'custom' && (
              <input className="form-input" style={{ marginTop: '0.5rem' }} value={customServer} onChange={(e) => setCustomServer(e.target.value)} placeholder="Enter server name" />
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
          <h2>Connection Result</h2>
          <div className="result-row"><span>Status</span><span className={result.connected ? 'green' : 'red'}>{result.connected ? 'Connected' : 'Disconnected'}</span></div>
          {result.account && (
            <>
              <div className="result-row"><span>Account</span><span>{result.account.login}</span></div>
              <div className="result-row"><span>Server</span><span>{result.account.server ?? '-'}</span></div>
              <div className="result-row"><span>Balance</span><span>${(result.account.balance ?? 0).toFixed(2)}</span></div>
              <div className="result-row"><span>Equity</span><span>${(result.account.equity ?? 0).toFixed(2)}</span></div>
              <div className="result-row"><span>Leverage</span><span>1:{result.account.leverage ?? 0}</span></div>
              <div className="result-row"><span>Currency</span><span>{result.account.currency ?? 'USD'}</span></div>
            </>
          )}
          <div className="result-row"><span>Auto Trading</span><span className={result.automated_trading_enabled ? 'green' : 'red'}>{result.automated_trading_enabled ? 'Yes' : 'No'}</span></div>
        </div>
      )}
      {saved && (
        <div className="card">
          <h2>Saved Account</h2>
          <div className="saved-info">
            <div className="saved-row"><span>Login</span><span>{saved.login ?? '-'}</span></div>
            <div className="saved-row"><span>Server</span><span>{saved.server ?? '-'}</span></div>
            <div className={`saved-row ${saved.connected ? 'connected' : 'disconnected'}`}><span>Status</span><span>{saved.connected ? 'Connected' : 'Not connected'}</span></div>
          </div>
        </div>
      )}
      <div className="card">
        <details>
          <summary>⚠ Automated Trading Must Be Enabled</summary>
          <ol>
            <li>Open <strong>MetaTrader 5</strong>.</li>
            <li>Go to <strong>Tools → Options → Expert Advisors</strong>.</li>
            <li>Check: <strong>Allow Automated Trading</strong>.</li>
            <li>Check: <strong>Allow WebRequest</strong> for listed URLs.</li>
            <li>Click OK and reconnect.</li>
          </ol>
        </details>
      </div>
    </div>
  );
}
