# ============================================================
# TheDisciple v2.0 – PostgreSQL Trade & State Persistence
# Direct psycopg2 access via SUPABASE_DB_URI (plain Postgres host).
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
    psycopg2.extras.register_default_jsonb(loads=json.loads)
except ImportError:
    _PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not installed — PostgreSQL persistence disabled")


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
        logger.warning("PostgreSQL query error: %s", exc)
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
    Upsert a single trade to PostgreSQL. Runs in a background thread.
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
            logger.warning("PostgreSQL sync error for ticket %s: %s", ticket, exc)

    threading.Thread(target=_task, daemon=True, name="pg_sync").start()


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
            logger.warning("PostgreSQL state sync error: %s", exc)

    threading.Thread(target=_task, daemon=True, name="pg_state").start()


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
            logger.warning("PostgreSQL signal log error: %s", exc)

    threading.Thread(target=_task, daemon=True, name="pg_signal").start()


# ── User Settings (per-user config) ────────────────────────

def get_user_max_daily_trades(user_id: str | None = None, uri: str | None = None) -> int:
    """Fetch max_daily_trades for a user from PostgreSQL. Falls back to default."""
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
            logger.warning("PostgreSQL user_settings upsert error: %s", exc)

    threading.Thread(target=_task, daemon=True, name="pg_user_settings").start()


# ── Multi-User: Fetch all MT5 credentials ───────────────────

def get_all_mt5_credentials(uri: str | None = None) -> list[dict]:
    """Fetch every user's MT5 credentials with decrypted passwords."""
    from brain.utils.crypto import decrypt_password
    rows = _exec_query(
        "SELECT DISTINCT ON (user_id) user_id, login, password, server "
        "FROM mt5_credentials ORDER BY user_id, updated_at DESC",
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


# ── Profiles (per-user settings) ───────────────────────────

def _ensure_profile(user_id: str, uri: str) -> None:
    """Ensure a profile row exists so child FKs can reference it."""
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO profiles (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (user_id,),
            )
        conn.close()
    except Exception as exc:
        logger.warning("ensure_profile error: %s", exc)


def get_profile(user_id: str, uri: str | None = None) -> dict | None:
    """Fetch a user's profile row from PostgreSQL."""
    rows = _exec_query(
        "SELECT * FROM profiles WHERE id = %s",
        (user_id,), uri=uri, fetch=True,
    )
    return rows[0] if rows else None


def update_profile(user_id: str, updates: dict, uri: str | None = None) -> bool:
    """Upsert a user's profile row (only allowlisted columns)."""
    uri = _resolve_uri(uri)
    if not uri:
        return False
    ALLOWED = {
        "risk_percent", "be_policy", "dry_run", "auto_compounding",
        "display_name", "notifications", "broker_verified",
    }
    fields = {k: v for k, v in updates.items() if k in ALLOWED}
    if not fields:
        return False
    _ensure_profile(user_id, uri)
    sets = ", ".join(f"{col} = %s" for col in fields)
    cols = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    params = []
    for col, val in fields.items():
        params.append(json.dumps(val) if col == "notifications" and val is not None else val)
    sql = f"""
        INSERT INTO profiles (id, {cols}, updated_at)
        VALUES (%s, {placeholders}, NOW())
        ON CONFLICT (id) DO UPDATE SET
            {sets},
            updated_at = NOW()
    """
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(sql, [user_id, *params])
        conn.close()
        return True
    except Exception as exc:
        logger.warning("update_profile error: %s", exc)
        return False


# ── User Settings ──────────────────────────────────────────

def get_user_settings(user_id: str, uri: str | None = None) -> dict | None:
    """Fetch a user's settings row from PostgreSQL."""
    rows = _exec_query(
        "SELECT * FROM user_settings WHERE user_id = %s",
        (user_id,), uri=uri, fetch=True,
    )
    return rows[0] if rows else None


def upsert_user_settings_dict(user_id: str, updates: dict, uri: str | None = None) -> bool:
    """Upsert multiple user_settings columns (only allowlisted columns)."""
    uri = _resolve_uri(uri)
    if not uri:
        return False
    ALLOWED = {"max_daily_trades", "risk_percent", "trading_mode", "trade_count"}
    fields = {k: v for k, v in updates.items() if k in ALLOWED}
    if not fields:
        return False
    _ensure_profile(user_id, uri)
    sets = ", ".join(f"{col} = EXCLUDED.{col}" for col in fields)
    cols = ", ".join(fields)
    placeholders = ", ".join(["%s"] * len(fields))
    sql = f"""
        INSERT INTO user_settings (user_id, {cols}, updated_at)
        VALUES (%s, {placeholders}, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            {sets},
            updated_at = NOW()
    """
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(sql, [user_id, *fields.values()])
        conn.close()
        return True
    except Exception as exc:
        logger.warning("upsert_user_settings_dict error: %s", exc)
        return False


# ── MT5 Credentials ────────────────────────────────────────

def get_mt5_accounts(user_id: str, uri: str | None = None) -> list[dict]:
    """Fetch a user's MT5 accounts (login + server only)."""
    rows = _exec_query(
        "SELECT login, server FROM mt5_credentials WHERE user_id = %s",
        (user_id,), uri=uri, fetch=True,
    )
    return rows or []


def get_mt5_credentials(user_id: str, uri: str | None = None) -> list[dict]:
    """Fetch a user's MT5 account details (no password)."""
    rows = _exec_query(
        """SELECT login, server, connected, automated_trading_enabled,
                  last_error, last_connected_at
           FROM mt5_credentials WHERE user_id = %s ORDER BY updated_at DESC""",
        (user_id,), uri=uri, fetch=True,
    )
    return rows or []


def get_mt5_connected(user_id: str, uri: str | None = None) -> bool:
    """True if any of the user's MT5 accounts is connected."""
    rows = _exec_query(
        "SELECT connected FROM mt5_credentials WHERE user_id = %s",
        (user_id,), uri=uri, fetch=True,
    )
    return bool(rows) and any(bool(r.get("connected")) for r in rows)


def save_mt5_credentials(data: dict, uri: str | None = None) -> bool:
    """Upsert MT5 credentials keyed by (user_id, login, server)."""
    uri = _resolve_uri(uri)
    if not uri:
        return False
    _ensure_profile(data.get("user_id", ""), uri)
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO mt5_credentials (user_id, login, password, server, updated_at)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (user_id, login, server) DO UPDATE SET
                       password  = EXCLUDED.password,
                       updated_at = NOW()""",
                (data.get("user_id"), data.get("login"),
                 data.get("password"), data.get("server")),
            )
        conn.close()
        return True
    except Exception as exc:
        logger.warning("save_mt5_credentials error: %s", exc)
        return False


def update_mt5_credentials(user_id: str, updates: dict, uri: str | None = None) -> bool:
    """Update MT5 credential columns for a user (only allowlisted columns)."""
    uri = _resolve_uri(uri)
    if not uri:
        return False
    ALLOWED = {"server", "connected", "automated_trading_enabled",
               "last_error", "last_connected_at"}
    fields = {k: v for k, v in updates.items() if k in ALLOWED}
    if not fields:
        return False
    sets = ", ".join(f"{col} = %s" for col in fields)
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                f"""UPDATE mt5_credentials SET {sets}, updated_at = NOW()
                    WHERE user_id = %s""",
                [*fields.values(), user_id],
            )
        conn.close()
        return True
    except Exception as exc:
        logger.warning("update_mt5_credentials error: %s", exc)
        return False


def delete_mt5_credentials(user_id: str, login: str, server: str, uri: str | None = None) -> bool:
    """Delete an MT5 credential by login and server."""
    uri = _resolve_uri(uri)
    if not uri:
        return False
    try:
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM mt5_credentials WHERE user_id = %s AND login = %s AND server = %s",
                (user_id, login, server),
            )
        conn.close()
        return True
    except Exception as exc:
        logger.warning("delete_mt5_credentials error: %s", exc)
        return False


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
