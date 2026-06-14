# ============================================================
# FuturesBrain v2.0 – Supabase Trade & State Persistence
# Uses Transaction Pooler (port 6543, IPv4-compatible).
# All operations are fire-and-forget from background threads.
# ============================================================
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from brain.config.settings import SUPABASE_DB_URI

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not installed — Supabase disabled")


def _get_conn(uri: str):
    if not _PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not available")
    return psycopg2.connect(
        uri,
        connect_timeout=10,
        options="-c statement_timeout=8000",
    )


def _resolve_uri(uri: str | None) -> str | None:
    return uri or SUPABASE_DB_URI


def _exec_query(sql: str, params: tuple = (), uri: str | None = None, fetch: bool = False) -> list[dict] | None:
    uri = _resolve_uri(uri)
    if not uri:
        return [] if fetch else None
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if fetch:
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            conn.commit()
            return None
    except Exception as exc:
        logger.warning("Supabase query error: %s", exc)
        return [] if fetch else None


# ── Trade Sync (insert / update) ────────────────────────────

def sync_trade(
    ticket: int,
    pair: str,
    direction: str,
    lots: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    pnl: float | None,
    status: str,
    opened_at: str,
    closed_at: str | None,
    confidence: int,
    sectors_json: str | None = None,
    user_id: str | None = None,
    uri: str | None = None,
) -> None:
    """
    Upsert a single trade to Supabase. Runs in a background thread.
    Silently swallows errors so trading loop is never blocked.
    """
    uri = _resolve_uri(uri)
    if not uri:
        return

    def _task() -> None:
        try:
            conn = _get_conn(uri)
            close_price = tp_price if status == "CLOSED" else None
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trades
                        (ticket, user_id, pair, direction, lots, entry_price, sl_price,
                         tp_price, close_price, pnl, status, opened_at, closed_at,
                         confidence, sectors_json)
                    VALUES
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ticket) DO UPDATE SET
                        pnl          = EXCLUDED.pnl,
                        status       = EXCLUDED.status,
                        close_price  = EXCLUDED.close_price,
                        closed_at    = EXCLUDED.closed_at
                    """,
                    (ticket, user_id, pair, direction, lots, entry_price, sl_price,
                     tp_price, close_price, pnl, status, opened_at, closed_at,
                     confidence, sectors_json),
                )
            conn.close()
        except Exception as exc:
            logger.warning("Supabase sync error for ticket %s: %s", ticket, exc)

    threading.Thread(target=_task, daemon=True, name="supabase_sync").start()


# ── Trade Reads ─────────────────────────────────────────────

def get_recent_trades(limit: int = 50, uri: str | None = None, user_id: str | None = None) -> list[dict]:
    if user_id:
        rows = _exec_query(
            "SELECT * FROM trades WHERE user_id = %s ORDER BY opened_at DESC LIMIT %s",
            (user_id, limit), uri=uri, fetch=True,
        )
    else:
        rows = _exec_query(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT %s",
            (limit,), uri=uri, fetch=True,
        )
    return rows or []


def get_open_trades(uri: str | None = None, user_id: str | None = None) -> list[dict]:
    if user_id:
        rows = _exec_query(
            "SELECT * FROM trades WHERE user_id = %s AND status='OPEN' ORDER BY opened_at DESC",
            (user_id,), uri=uri, fetch=True,
        )
    else:
        rows = _exec_query(
            "SELECT * FROM trades WHERE status='OPEN' ORDER BY opened_at DESC",
            uri=uri, fetch=True,
        )
    return rows or []


def count_trades_today(uri: str | None = None, user_id: str | None = None) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user_id:
        rows = _exec_query(
            "SELECT COUNT(*) AS cnt FROM trades WHERE user_id = %s AND opened_at::date = %s",
            (user_id, today), uri=uri, fetch=True,
        )
    else:
        rows = _exec_query(
            "SELECT COUNT(*) AS cnt FROM trades WHERE opened_at::date = %s",
            (today,), uri=uri, fetch=True,
        )
    return rows[0]["cnt"] if rows else 0


def count_losses_last_24h(uri: str | None = None, user_id: str | None = None) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    if user_id:
        rows = _exec_query(
            """SELECT COUNT(*) AS cnt FROM trades
               WHERE user_id = %s AND status='CLOSED' AND pnl < 0 AND closed_at >= %s""",
            (user_id, cutoff), uri=uri, fetch=True,
        )
    else:
        rows = _exec_query(
            """SELECT COUNT(*) AS cnt FROM trades
               WHERE status='CLOSED' AND pnl < 0 AND closed_at >= %s""",
            (cutoff,), uri=uri, fetch=True,
        )
    return rows[0]["cnt"] if rows else 0


def get_todays_pnl(uri: str | None = None, user_id: str | None = None) -> float:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user_id:
        rows = _exec_query(
            """SELECT COALESCE(SUM(pnl), 0) AS total FROM trades
               WHERE user_id = %s AND status='CLOSED' AND closed_at::date = %s""",
            (user_id, today), uri=uri, fetch=True,
        )
    else:
        rows = _exec_query(
            """SELECT COALESCE(SUM(pnl), 0) AS total FROM trades
               WHERE status='CLOSED' AND closed_at::date = %s""",
            (today,), uri=uri, fetch=True,
        )
    return float(rows[0]["total"]) if rows else 0.0


# ── Bot State (key-value for cooldown, etc.) ────────────────

def get_state(key: str, default: Any = None, uri: str | None = None) -> Any:
    rows = _exec_query(
        "SELECT value FROM bot_state WHERE key = %s",
        (key,), uri=uri, fetch=True,
    )
    if not rows:
        return default
    try:
        return json.loads(rows[0]["value"])
    except (json.JSONDecodeError, TypeError):
        return rows[0]["value"]


def set_state(key: str, value: Any, uri: str | None = None) -> None:
    uri = _resolve_uri(uri)
    if not uri:
        return

    def _task() -> None:
        try:
            conn = _get_conn(uri)
            with conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO bot_state (key, value)
                       VALUES (%s, %s)
                       ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                    (key, json.dumps(value)),
                )
            conn.close()
        except Exception as exc:
            logger.warning("Supabase state sync error: %s", exc)

    threading.Thread(target=_task, daemon=True, name="supabase_state").start()


# ── Signal Logging ──────────────────────────────────────────

def log_signal(
    pair: str,
    direction: str,
    confidence: int,
    alignment: str,
    sectors: dict | None = None,
    uri: str | None = None,
) -> None:
    uri = _resolve_uri(uri)
    if not uri:
        return

    def _task() -> None:
        try:
            conn = _get_conn(uri)
            with conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO signals (pair, direction, confidence, alignment, sectors_json)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (pair, direction, confidence, alignment,
                     json.dumps(sectors) if sectors else None),
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Supabase signal log error: %s", exc)

    threading.Thread(target=_task, daemon=True, name="supabase_signal").start()


# ── User Settings (per-user config) ────────────────────────

def get_user_max_daily_trades(user_id: str | None = None, uri: str | None = None) -> int:
    """Fetch max_daily_trades for a user from Supabase. Falls back to default."""
    from brain.config.constants import MAX_DAILY_TRADES
    if not user_id:
        return MAX_DAILY_TRADES
    rows = _exec_query(
        "SELECT max_daily_trades FROM user_settings WHERE user_id = %s",
        (user_id,), uri=uri, fetch=True,
    )
    if rows and rows[0].get("max_daily_trades") is not None:
        return int(rows[0]["max_daily_trades"])
    return MAX_DAILY_TRADES


def upsert_user_setting(
    user_id: str,
    field: str,
    value: int | float,
    uri: str | None = None,
) -> None:
    """Upsert a single user setting field. Runs in a background thread."""
    uri = _resolve_uri(uri)
    if not uri:
        return

    ALLOWED_FIELDS = {"max_daily_trades", "risk_percent", "trading_mode"}
    if field not in ALLOWED_FIELDS:
        logger.warning("Rejected upsert_user_setting for disallowed field: %s", field)
        return

    def _task() -> None:
        try:
            conn = _get_conn(uri)
            with conn, conn.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO user_settings (user_id, {field}, updated_at)
                       VALUES (%s, %s, NOW())
                       ON CONFLICT (user_id) DO UPDATE SET
                           {field} = EXCLUDED.{field},
                           updated_at = NOW()""",
                    (user_id, value),
                )
            conn.close()
        except Exception as exc:
            logger.warning("Supabase user_settings upsert error: %s", exc)

    threading.Thread(target=_task, daemon=True, name="supabase_user_settings").start()


# ── Multi-User: Fetch all MT5 credentials ───────────────────

def get_all_mt5_credentials(uri: str | None = None) -> list[dict]:
    """Fetch every user's MT5 credentials with decrypted passwords."""
    from brain.utils.crypto import decrypt_password
    rows = _exec_query(
        "SELECT user_id, login, password, server FROM mt5_credentials ORDER BY updated_at DESC",
        uri=uri, fetch=True,
    )
    if not rows:
        return []
    for row in rows:
        try:
            row["password"] = decrypt_password(row["password"])
        except Exception:
            pass
        row["login"] = int(row["login"])
    return rows


# ── Connection Test ─────────────────────────────────────────

def test_connection(uri: str | None = None) -> tuple[bool, str]:
    uri = _resolve_uri(uri)
    if not uri:
        return False, "SUPABASE_DB_URI not configured"
    if not _PSYCOPG2_AVAILABLE:
        return False, "psycopg2 not installed"
    try:
        conn = _get_conn(uri)
        conn.cursor().execute("SELECT 1")
        conn.close()
        return True, "OK"
    except Exception as exc:
        return False, str(exc)
