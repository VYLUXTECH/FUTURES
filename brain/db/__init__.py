# futuresbrain/db/__init__.py
from .supabase import (
    sync_trade, test_connection,
    get_recent_trades, get_open_trades,
    count_trades_today, count_losses_last_24h, get_todays_pnl,
    get_state, set_state, log_signal,
    get_user_max_daily_trades, upsert_user_setting,
)

__all__ = [
    "sync_trade", "test_connection",
    "get_recent_trades", "get_open_trades",
    "count_trades_today", "count_losses_last_24h", "get_todays_pnl",
    "get_state", "set_state", "log_signal",
    "get_user_max_daily_trades", "upsert_user_setting",
]
