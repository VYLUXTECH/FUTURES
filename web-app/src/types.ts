export interface StatusData {
  running?: boolean;
  mt5_configured?: boolean;
  mt5_connected?: boolean;
  cooldown_active?: boolean;
  daily_trades?: number;
  account_balance?: number;
  equity?: number;
  daily_pnl?: number;
}

export interface DashboardData {
  balance?: number;
  equity?: number;
  margin?: number;
  daily_pnl?: number;
  recent_trades?: Trade[];
}

export interface Trade {
  ticket?: number;
  pair?: string;
  direction?: string;
  lots?: number;
  entry_price?: number;
  close_price?: number;
  sl_price?: number;
  tp_price?: number;
  pnl?: number;
  status?: string;
  opened_at?: string;
  closed_at?: string;
  confidence?: number;
  volume?: number;
  commission?: number;
  swap?: number;
}

export interface Mt5ConnectResult {
  connected: boolean;
  error?: string;
  automated_trading_enabled?: boolean;
  account?: {
    login: string;
    server: string;
    balance: number;
    equity: number;
    leverage: number;
    currency: string;
  };
  terminal?: {
    name: string;
    build: string;
  };
}

export interface SavedCredentials {
  login?: string;
  server?: string;
  connected?: boolean;
}
