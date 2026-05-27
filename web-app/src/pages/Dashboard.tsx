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
        <div className="health-row">
          <span className={`health-dot ${health.color}`} />
          <span>{health.label}</span>
        </div>
      </div>
      <div className="card">
        <h2>Account</h2>
        <div className="stat-row"><span>Balance</span><span>${Number(balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
        <div className="stat-row"><span>Equity</span><span>${Number(equity).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
        <div className="stat-row"><span>Margin</span><span>${Number(margin).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
        <div className="stat-row"><span>Today's P&L</span><span className={dailyPnl >= 0 ? 'pnl-profit' : 'pnl-loss'}>{dailyPnl >= 0 ? '+' : ''}${Number(dailyPnl).toFixed(2)}</span></div>
      </div>
      <div className="card">
        <h2>Daily Trades</h2>
        <p>{dailyTrades} / {maxDaily}</p>
        <div className="progress-bar"><div className="progress-fill" style={{ width: `${Math.min(100, (dailyTrades / maxDaily) * 100)}%` }} /></div>
      </div>
      <div className="card">
        <h2>Bot Control</h2>
        <div className="mode-selector">
          {(['long', 'short', 'both'] as Mode[]).map((m) => (
            <button key={m} className={`mode-btn ${mode === m ? 'active' : ''}`} onClick={() => setMode(m)} disabled={botActive}>
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
        {mode === 'long' && (
          <div className="form-group">
            <label>Trades per cycle</label>
            <input type="number" min={1} max={5} value={tradeCount}
              onChange={(e) => setTradeCount(Math.max(1, Math.min(5, parseInt(e.target.value, 10) || 1)))}
              disabled={botActive} />
          </div>
        )}
        {mode !== 'long' && <p className="text-muted">Short/both modes trade once per cycle</p>}
        <div className="form-group">
          <label>Risk per trade: {riskPercent}%</label>
          <input type="range" min={1} max={10} value={riskPercent} onChange={(e) => setRiskPercent(parseInt(e.target.value, 10))} disabled={botActive} />
        </div>
        <div className="btn-row">
          <button className="btn-primary" onClick={handleStart} disabled={!canStart}>▶ START BOT</button>
          <button className="btn-danger" onClick={handleStop} disabled={!botActive}>⏹ STOP BOT</button>
        </div>
      </div>
      <div className="card">
        <h2>Recent Trades</h2>
        {trades.length === 0 ? (
          <p className="text-muted">No trades yet</p>
        ) : (
          <table className="trades-table">
            <thead><tr><th>Pair</th><th>Dir</th><th>P&L</th><th>Time</th></tr></thead>
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
        )}
      </div>
    </div>
  );
}
