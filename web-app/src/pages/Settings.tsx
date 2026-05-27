import { useState, useEffect } from 'react';
import { loadSettings, saveSettings, getSupabase } from '../services/api';
import type { NavigateFn } from '../App';

interface Props { navigate: NavigateFn; }

const NOTIF_LABELS: Record<string, string> = {
  trade_execution: 'Trade execution', trade_closed: 'Trade closed',
  daily_summary: 'Daily summary', loss_cooldown: '3-loss cooldown',
  maintenance: 'Maintenance', email_trade: 'Email trade notifications',
};

export default function Settings(_props: Props) {
  const [displayName, setDisplayName] = useState('Trader');
  const [riskPercent, setRiskPercent] = useState(5);
  const [bePolicy, setBePolicy] = useState('auto');
  const [autoCompounding, setAutoCompounding] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [notifications, setNotifications] = useState<Record<string, boolean>>({
    trade_execution: true, trade_closed: true, daily_summary: true,
    loss_cooldown: true, maintenance: true, email_trade: false,
  });
  const [email, setEmail] = useState('');
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);
  const [debounceTimer, setDebounceTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string, type = 'success') => {
    setToast({ msg, type }); setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    loadSettings().then((data) => {
      if (!data) return;
      setDisplayName((data.display_name as string) || 'Trader');
      setRiskPercent((data.risk_percent as number) || 5);
      setBePolicy((data.be_policy as string) || 'auto');
      setAutoCompounding(!!data.auto_compounding);
      setDryRun(!!data.dry_run);
      if (data.notifications) setNotifications(data.notifications as Record<string, boolean>);
    });
    getSupabase().then((sb) => {
      sb.auth.getSession().then((s) => {
        const u = s.data.session?.user?.email;
        if (u) setEmail(u);
      });
    });
  }, []);

  function handleSaveName() {
    if (!displayName.trim()) return;
    saveSettings({ display_name: displayName.trim() }).then((ok) => {
      if (ok) showToast('Saved'); else showToast('Failed to save', 'error');
    });
  }

  function handleRiskChange(val: number) {
    setRiskPercent(val);
    if (debounceTimer) clearTimeout(debounceTimer);
    setDebounceTimer(setTimeout(() => saveSettings({ risk_percent: val }), 500));
  }

  function toggleNotif(key: string) {
    const updated = { ...notifications, [key]: !notifications[key] };
    setNotifications(updated);
    saveSettings({ notifications: updated });
  }

  return (
    <div className="page page-settings">
      {toast && <div className={`toast-global visible ${toast.type}`}>{toast.msg}</div>}
      <div className="card">
        <h2>Account</h2>
        <div className="setting-row"><span>Email</span><span>{email || 'Loading...'}</span></div>
        <div className="setting-row">
          <span>Display Name</span>
          <div className="input-row">
            <input className="form-input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            <button className="btn-sm" onClick={handleSaveName}>Save</button>
          </div>
        </div>
      </div>
      <div className="card">
        <h2>Trading Preferences</h2>
        <div className="form-group">
          <label>Risk per trade: {riskPercent}%</label>
          <input type="range" min={1} max={10} value={riskPercent} onChange={(e) => handleRiskChange(parseInt(e.target.value, 10))} />
        </div>
        <div className="form-group">
          <label>Breakeven Policy</label>
          <div className="radio-group">
            {['auto', 'manual', 'off'].map((p) => (
              <button key={p} className={`radio-option ${bePolicy === p ? 'active' : ''}`}
                onClick={() => { setBePolicy(p); saveSettings({ be_policy: p }); }}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="setting-row">
          <span>Auto-Compounding</span>
          <label className="toggle-switch">
            <input type="checkbox" checked={autoCompounding}
              onChange={(e) => { setAutoCompounding(e.target.checked); saveSettings({ auto_compounding: e.target.checked }); }} />
            <span className="toggle-slider" />
          </label>
        </div>
        {autoCompounding && <p className="warning-text">⚠ Reinvests profits — higher risk</p>}
        <div className="setting-row">
          <span>Dry Run Mode</span>
          <label className="toggle-switch">
            <input type="checkbox" checked={dryRun}
              onChange={(e) => { setDryRun(e.target.checked); saveSettings({ dry_run: e.target.checked }); }} />
            <span className="toggle-slider" />
          </label>
        </div>
      </div>
      <div className="card">
        <h2>Notifications</h2>
        {Object.entries(notifications).map(([key, val]) => (
          <div key={key} className="setting-row" style={{ border: 'none' }}>
            <span>{NOTIF_LABELS[key] || key}</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={val} onChange={() => toggleNotif(key)} />
              <span className="toggle-slider" />
            </label>
          </div>
        ))}
      </div>
      <div className="card">
        <h2>Data</h2>
        <div className="btn-row">
          <button className="btn-secondary" onClick={() => saveSettings({}).then(() => showToast('Cache cleared'))}>Clear Chat Cache</button>
        </div>
      </div>
    </div>
  );
}
