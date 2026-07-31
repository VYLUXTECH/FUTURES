# thedisciple/db/__init__.py
from .postgres_ops import (
    sync_trade, test_connection,
    get_recent_trades, get_open_trades,
    count_trades_today, count_losses_last_24h, get_todays_pnl,
    get_state, set_state, log_signal,
    get_user_max_daily_trades, upsert_user_setting,
    get_all_mt5_credentials,
    get_profile, update_profile,
    get_user_settings, upsert_user_settings_dict,
    get_mt5_accounts, get_mt5_credentials, get_mt5_connected,
    save_mt5_credentials, update_mt5_credentials, delete_mt5_credentials,
)

__all__ = [
    "sync_trade", "test_connection",
    "get_recent_trades", "get_open_trades",
    "count_trades_today", "count_losses_last_24h", "get_todays_pnl",
    "get_state", "set_state", "log_signal",
    "get_user_max_daily_trades", "upsert_user_setting",
    "get_all_mt5_credentials",
    "get_profile", "update_profile",
    "get_user_settings", "upsert_user_settings_dict",
    "get_mt5_accounts", "get_mt5_credentials", "get_mt5_connected",
    "save_mt5_credentials", "update_mt5_credentials", "delete_mt5_credentials",
]
