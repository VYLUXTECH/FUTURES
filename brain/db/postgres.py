from __future__ import annotations

import json
import logging

from brain.config.settings import SUPABASE_DB_URI

logger = logging.getLogger(__name__)

try:
    import psycopg2
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False


def _get_conn(uri: str):
    if not _PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not available")
    return psycopg2.connect(uri, connect_timeout=10, options="-c statement_timeout=8000")


def init_db(uri: str | None = None) -> None:
    uri = uri or SUPABASE_DB_URI
    if not uri:
        logger.warning("SUPABASE_DB_URI not configured — skipping init_db")
        return
    if not _PSYCOPG2_AVAILABLE:
        logger.warning("psycopg2 not installed — skipping init_db")
        return
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    ticket       BIGINT PRIMARY KEY,
                    user_id      UUID,
                    pair         TEXT NOT NULL,
                    direction    TEXT NOT NULL,
                    lots         REAL NOT NULL,
                    entry_price  REAL NOT NULL,
                    sl_price     REAL,
                    tp_price     REAL,
                    close_price  REAL,
                    pnl          REAL,
                    status       TEXT NOT NULL DEFAULT 'OPEN',
                    opened_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    closed_at    TIMESTAMPTZ,
                    confidence   INTEGER DEFAULT 0,
                    sectors_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_state (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id            BIGSERIAL PRIMARY KEY,
                    pair          TEXT NOT NULL,
                    direction     TEXT NOT NULL,
                    confidence    INTEGER DEFAULT 0,
                    alignment     TEXT,
                    sectors_json  TEXT,
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email         VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    display_name  VARCHAR(255) DEFAULT '',
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id               UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    risk_percent     NUMERIC(4,1) DEFAULT 5.0,
                    be_policy        TEXT DEFAULT 'auto',
                    dry_run          BOOLEAN DEFAULT FALSE,
                    auto_compounding BOOLEAN DEFAULT FALSE,
                    display_name     VARCHAR(100) DEFAULT 'Trader',
                    notifications    JSONB DEFAULT '{}'::jsonb,
                    bot_active       BOOLEAN DEFAULT FALSE,
                    expo_push_token  TEXT,
                    broker_verified  BOOLEAN DEFAULT FALSE,
                    broker_name      TEXT,
                    created_at       TIMESTAMPTZ DEFAULT NOW(),
                    updated_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id          UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    max_daily_trades INTEGER DEFAULT 5,
                    risk_percent     REAL DEFAULT 5.0,
                    trading_mode     TEXT DEFAULT 'short',
                    trade_count      INTEGER DEFAULT 1,
                    updated_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mt5_credentials (
                    user_id                   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    login                     VARCHAR(50) NOT NULL,
                    password                  VARCHAR(500) NOT NULL,
                    server                    VARCHAR(100) NOT NULL,
                    account_name              VARCHAR(100),
                    connected                 BOOLEAN DEFAULT FALSE,
                    automated_trading_enabled BOOLEAN DEFAULT FALSE,
                    last_error                TEXT,
                    last_connected_at         TIMESTAMPTZ,
                    updated_at                TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (user_id, login, server)
                )
            """)
            cur.execute("""
                DO $$
                BEGIN
                    IF to_regclass('auth.users') IS NOT NULL THEN
                        EXECUTE (
                            SELECT string_agg(
                                format('ALTER TABLE %s DROP CONSTRAINT %I',
                                       conrelid::regclass, conname),
                                '; ')
                            FROM pg_constraint
                            WHERE contype = 'f' AND confrelid = 'auth.users'::regclass
                        );
                    END IF;
                END $$;
            """)
            cur.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS risk_percent REAL DEFAULT 5.0")
            cur.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS trade_count INTEGER DEFAULT 1")
            cur.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS trading_mode TEXT DEFAULT 'short'")
            cur.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS max_daily_trades INTEGER DEFAULT 5")
            conn.commit()
            logger.info("Database tables initialised")
    except Exception as exc:
        logger.warning("init_db error: %s", exc)


from .postgres_ops import (
    sync_trade, test_connection,
    get_recent_trades, get_open_trades,
    count_trades_today, count_losses_last_24h, get_todays_pnl,
    get_state, set_state, log_signal,
    get_all_mt5_credentials,
    get_profile, update_profile,
    get_user_settings, upsert_user_settings_dict,
    get_mt5_accounts, get_mt5_credentials, get_mt5_connected,
    save_mt5_credentials, update_mt5_credentials, delete_mt5_credentials,
)

__all__ = [
    "init_db", "sync_trade", "test_connection",
    "get_recent_trades", "get_open_trades",
    "count_trades_today", "count_losses_last_24h", "get_todays_pnl",
    "get_state", "set_state", "log_signal",
    "get_all_mt5_credentials",
    "get_profile", "update_profile",
    "get_user_settings", "upsert_user_settings_dict",
    "get_mt5_accounts", "get_mt5_credentials", "get_mt5_connected",
    "save_mt5_credentials", "update_mt5_credentials", "delete_mt5_credentials",
]
