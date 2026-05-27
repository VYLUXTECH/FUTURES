export interface StatusData {
  account_balance?: number;
  equity?: number;
  daily_trades?: number;
  daily_pnl?: number;
  mt5_connected?: boolean;
  mt5_configured?: boolean;
  cooldown_active?: boolean;
  running?: boolean;
  display_name?: string;
  [key: string]: unknown;
}

export interface DashboardData {
  balance?: number;
  equity?: number;
  margin?: number;
  daily_pnl?: number;
  recent_trades?: Trade[];
  [key: string]: unknown;
}

export interface Trade {
  pair?: string;
  direction?: string;
  pnl?: number;
  closed_at?: string;
  opened_at?: string;
  [key: string]: unknown;
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
  terminal?: { name: string; build: string };
}

export interface SavedCredentials {
  login?: string;
  server?: string;
  connected?: boolean;
}
