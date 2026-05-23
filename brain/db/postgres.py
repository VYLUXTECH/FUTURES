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
            conn.commit()
        logger.info("Database tables initialised")
    except Exception as exc:
        logger.warning("init_db error: %s", exc)


from .supabase import (
    sync_trade, test_connection,
    get_recent_trades, get_open_trades,
    count_trades_today, count_losses_last_24h, get_todays_pnl,
    get_state, set_state, log_signal,
)

__all__ = [
    "init_db", "sync_trade", "test_connection",
    "get_recent_trades", "get_open_trades",
    "count_trades_today", "count_losses_last_24h", "get_todays_pnl",
    "get_state", "set_state", "log_signal",
]
