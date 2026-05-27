import { useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchStatus, fetchDashboard, startBot, stopBot } from '../services/api';
import type { NavigateFn } from '../App';

type Mode = 'long' | 'short' | 'both';

interface Props { navigate: NavigateFn; }

export default function Dashboard({ navigate }: Props) {
  const [mode, setMode] = useState<Mode>('long');
  const [tradeCount, setTradeCount] = useState(1);
  const [riskPercent, setRiskPercent] = useState(5);
  const [botActive, setBotActive] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: string } | null>(null);
  const [showTip, setShowTip] = useState(false);

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['status'], queryFn: fetchStatus, refetchInterval: 15000,
  });
  const { data: dashboard, refetch: refetchDashboard } = useQuery({
    queryKey: ['dashboard'], queryFn: fetchDashboard, refetchInterval: 15000,
  });

  useEffect(() => { if (status) setBotActive(status.running ?? false); }, [status]);

  const showToast = useCallback((msg: string, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const configured = status?.mt5_configured ?? false;
  const connected = status?.mt5_connected ?? false;
  const cooldown = status?.cooldown_active ?? false;
  const dailyTrades = status?.daily_trades ?? 0;
  const maxDaily = 5;
  const balance = status?.account_balance ?? dashboard?.balance ?? 0;
  const equity = status?.equity ?? dashboard?.equity ?? 0;
  const margin = dashboard?.margin ?? 0;
  const dailyPnl = status?.daily_pnl ?? dashboard?.daily_pnl ?? 0;
  const trades = dashboard?.recent_trades ?? [];
  const canStart = dailyTrades < maxDaily && !botActive && !cooldown && configured;

  function getHealth(): { color: string; label: string; tip: string } {
    if (!configured) return { color: 'red', label: 'MT5 Not Configured', tip: 'Go to the MT5 page to configure your broker.' };
    if (!connected && !botActive) return { color: 'yellow', label: 'MT5 Ready', tip: 'Start the bot to connect MT5.' };
    if (cooldown) return { color: 'yellow', label: 'Cooldown Active', tip: 'Bot paused due to 3 consecutive losses.' };
    if (botActive) return { color: 'green', label: 'Bot Running', tip: 'All systems normal.' };
    return { color: 'green', label: 'Bot Active', tip: 'All systems normal.' };
  }

  const health = getHealth();

  function getBanner(): { type: string; text: string } | null {
    if (cooldown) return { type: 'cooldown', text: '⚠ Bot paused due to 3 consecutive losses (cooldown 24h).' };
    if (!configured) return { type: 'error', text: '⚠ MT5 not configured. ' };
    if (!connected && !botActive) return { type: 'error', text: '⚠ MT5 will connect when you start the bot.' };
    return null;
  }

  const banner = getBanner();

  async function handleStart() {
    if (!canStart) return;
    if (!configured) { showToast('Configure MT5 credentials first.', 'error'); return; }
    try {
      await startBot(mode, tradeCount, riskPercent);
      setBotActive(true); showToast('Bot started!');
      refetchStatus(); refetchDashboard();
    } catch (err: unknown) { showToast(err instanceof Error ? err.message : 'Failed', 'error'); }
  }

  async function handleStop() {
    if (!botActive) return;
    try {
      await stopBot();
      setBotActive(false); showToast('Bot stopped.');
      refetchStatus(); refetchDashboard();
    } catch (err: unknown) { showToast(err instanceof Error ? err.message : 'Failed', 'error'); }
  }

  return (
    <div className="page page-dashboard">
      {toast && <div className={`toast-global visible ${toast.type}`}>{toast.msg}</div>}

      {banner && (
        <div className={`warning-banner ${banner.type} visible`}>
          {banner.text}
          {!configured && <span style={{ cursor: 'pointer', textDecoration: 'underline', marginLeft: '0.5rem' }} onClick={() => navigate('mt5')}>Configure now</span>}
        </div>
      )}

      <div className="card">
        <div className="balance-display">${Number(balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
        <div className="sub-balance">
          <span>Equity: <strong>${Number(equity).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span>
          <span>Margin: <strong>${Number(margin).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span>
        </div>
        <div className="daily-limit">
          <div className="limit-label">
            <span>Daily used</span>
            <span>{dailyTrades} / {maxDaily}</span>
          </div>
          <div className="limit-bar-bg">
            <div className="limit-bar-fill" style={{ width: `${Math.min(100, (dailyTrades / maxDaily) * 100)}%` }} />
          </div>
        </div>
        <div className="health-row" onClick={() => setShowTip(!showTip)}>
          <span className={`health-dot ${health.color}`} />
          <span className="health-text">{health.label}</span>
        </div>
      </div>

      <div className="card">
        <div className="controls-row">
          <button className="btn-control btn-start" onClick={handleStart} disabled={!canStart}>▶ START BOT</button>
          <button className="btn-control btn-stop" onClick={handleStop} disabled={!botActive}>⏹ STOP BOT</button>
        </div>
        <div className="mode-selector">
          {(['long', 'short', 'both'] as Mode[]).map((m) => (
            <button key={m} className={`mode-btn ${mode === m ? 'active' : ''}`} onClick={() => setMode(m)} disabled={botActive}>
              {m === 'long' ? 'Long-term' : m === 'short' ? 'Short-term' : 'Both'}
            </button>
          ))}
        </div>
        {mode === 'long' && (
          <div className="stat-row">
            <span>Number of trades</span>
            <input type="number" className="param-input" min={1} max={5} value={tradeCount}
              onChange={(e) => setTradeCount(Math.max(1, Math.min(5, parseInt(e.target.value, 10) || 1)))}
              disabled={botActive} style={{ width: 60, padding: '0.4rem', background: 'var(--bg)', border: '1px solid var(--card-border)', borderRadius: 6, color: 'var(--text)', textAlign: 'center', fontFamily: 'Inter, sans-serif' }} />
          </div>
        )}
        {mode === 'short' && (
          <p style={{ background: 'var(--bg)', border: '1px solid var(--card-border)', borderRadius: 10, padding: '0.75rem', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
            One trade will be executed, then bot stops. Adjust risk as needed.
          </p>
        )}
        <div className="stat-row">
          <span>Risk %</span>
          <span>{riskPercent}%</span>
        </div>
        <input type="range" min={1} max={10} step={0.5} value={riskPercent}
          onChange={(e) => setRiskPercent(parseFloat(e.target.value))} disabled={botActive}
          style={{ width: '100%', marginTop: '0.5rem', accentColor: 'var(--primary)' }} />
      </div>

      <div className="card">
        <h2 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>📋 Recent Trades</h2>
        {trades.length === 0 ? (
          <p className="text-muted">No trades yet</p>
        ) : (
          <>
            <table className="trades-table">
              <thead><tr><th>Pair</th><th>Type</th><th>P&L</th><th>Time</th></tr></thead>
              <tbody>
                {trades.slice(0, 10).map((t, i) => {
                  const pnl = Number(t.pnl ?? 0);
                  const time = t.closed_at
                    ? new Date(t.closed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : t.opened_at
                      ? new Date(t.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : '';
                  return (
                    <tr key={i}>
                      <td>{t.pair ?? '-'}</td>
                      <td>{(t.direction ?? '').toUpperCase()}</td>
                      <td className={pnl >= 0 ? 'pnl-profit' : 'pnl-loss'}>{pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</td>
                      <td>{time}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <span className="see-all-link" onClick={() => navigate('accountability')}>See all →</span>
          </>
        )}
      </div>

      <div className="card">
        <div className="performance-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Today's P&L</span>
          <span className={dailyPnl >= 0 ? 'pnl-profit' : 'pnl-loss'} style={{ fontSize: '1.5rem', fontWeight: 700 }}>
            {dailyPnl >= 0 ? '+' : ''}${Number(dailyPnl).toFixed(2)}
          </span>
        </div>
        <div className="actions-grid">
          <button className="action-btn" onClick={() => navigate('copilot')}><span className="action-icon">💬</span>Chat</button>
          <button className="action-btn" onClick={() => navigate('accountability')}><span className="action-icon">📖</span>History</button>
          <button className="action-btn" onClick={() => navigate('settings')}><span className="action-icon">⚙️</span>Settings</button>
          <button className="action-btn" onClick={() => navigate('mt5')}><span className="action-icon">📡</span>MT5</button>
          <button className="action-btn" onClick={() => navigate('support')}><span className="action-icon">🆘</span>Support</button>
        </div>
      </div>
    </div>
  );
}
