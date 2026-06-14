# ============================================================
# FuturesBrain v1.0 – FastAPI Routes
# Endpoints aligned with frontend (dashboard, copilot, mt5, settings).
# NEVER executes trades directly – only reads state and proxies copilot.
# ============================================================
from __future__ import annotations

import asyncio
import logging
from typing import Any

import MetaTrader5 as mt5
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from brain.api.copilot import analyze_chart
from brain.db import get_open_trades, get_recent_trades, get_todays_pnl, count_trades_today
from brain.config.constants import SUPPORTED_PAIRS

try:
    from backend.api.middleware import require_auth
except ImportError:
    async def require_auth() -> dict:
        return {}

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Shared bot state reference (set by main.py) ───────────
# Populated by main.py after startup via set_bot_state_ref()
_bot_state: dict[str, Any] = {
    "running": False,
    "risk": None,
    "start_time": None,
}


def set_bot_state_ref(state: dict) -> None:
    """Called from main.py to inject live bot state reference."""
    global _bot_state
    _bot_state = state


# ── Request / Response Models ─────────────────────────────

class CopilotRequest(BaseModel):
    pair: str = Field(..., pattern="^(GBPUSD|GBPJPY|USDJPY)$")
    tf: str = Field(default="1m")
    chart_b64: str = Field(..., description="Full data-URI from capture_chart()")


class BotStatusResponse(BaseModel):
    running: bool
    connected: bool
    mt5_connected: bool
    mt5_configured: bool = False
    account_balance: float
    equity: float
    daily_trades: int
    daily_pnl: float
    cooldown_active: bool
    pairs: list[str]
    session_active: bool
    risk_percent: float | None = None


# ── Health / Status ───────────────────────────────────────

@router.get("/health")
async def health() -> dict:
    """Lightweight health check. Does NOT block trading loop."""
    from brain.db import test_connection
    from brain.config.settings import SUPABASE_DB_URI

    loop = asyncio.get_event_loop()
    terminal = await loop.run_in_executor(None, mt5.terminal_info)
    mt5_connected = terminal is not None and bool(terminal.connected)

    db_ok = False
    try:
        db_ok, _ = await loop.run_in_executor(None, test_connection, SUPABASE_DB_URI)
    except Exception:
        pass

    status = "ok"
    if not mt5_connected:
        status = "degraded"
    if not db_ok:
        status = "degraded"

    return {
        "status":      status,
        "mt5":         mt5_connected,
        "database":    db_ok,
        "version":     "1.0.0",
    }


@router.get("/api/status", response_model=BotStatusResponse)
async def bot_status(user: dict = Depends(require_auth)) -> BotStatusResponse:
    """Full bot status for dashboard header."""
    from datetime import datetime, timezone
    from brain.config.constants import SESSION_START_UTC, SESSION_END_UTC

    loop = asyncio.get_event_loop()
    account = await loop.run_in_executor(None, mt5.account_info)

    balance: float = getattr(account, "balance", 0.0) if account else 0.0
    equity: float  = getattr(account, "equity",  0.0) if account else 0.0

    terminal  = await loop.run_in_executor(None, mt5.terminal_info)
    connected = terminal is not None and bool(terminal.connected)

    risk = _bot_state.get("risk")
    cooldown = bool(risk and risk.in_cooldown) if risk else False

    user_id = user.get("sub")
    daily_trades = count_trades_today(user_id=user_id)
    daily_pnl    = get_todays_pnl(user_id=user_id)

    hour_utc = datetime.now(timezone.utc).hour
    session_active = SESSION_START_UTC <= hour_utc < SESSION_END_UTC

    mt5_configured = False
    if user_id:
        try:
            import os
            from brain.config.settings import SUPABASE_DB_URI
            uri = SUPABASE_DB_URI or os.getenv("SUPABASE_DB_URI")
            if uri:
                from brain.db.supabase import _get_conn
                conn = _get_conn(uri)
                with conn, conn.cursor() as cur:
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM mt5_credentials WHERE user_id = %s AND connected = TRUE)",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        mt5_configured = True
                conn.close()
        except Exception as exc:
            logger.warning("Failed to check MT5 credentials: %s", exc)

    return BotStatusResponse(
        running=bool(_bot_state.get("running")),
        connected=connected,
        mt5_connected=connected,
        mt5_configured=mt5_configured,
        account_balance=balance,
        equity=equity,
        daily_trades=daily_trades,
        daily_pnl=daily_pnl,
        cooldown_active=cooldown,
        pairs=SUPPORTED_PAIRS,
        session_active=session_active,
        risk_percent=_bot_state.get("risk_percent"),
    )


# ── Dashboard ─────────────────────────────────────────────

@router.get("/api/dashboard")
async def dashboard(user: dict = Depends(require_auth)) -> dict:
    """Aggregate data for the dashboard page."""
    user_id = user.get("sub")
    open_trades = get_open_trades(user_id=user_id)
    recent_trades = get_recent_trades(limit=10, user_id=user_id)
    daily_pnl = get_todays_pnl(user_id=user_id)

    loop = asyncio.get_event_loop()
    account = await loop.run_in_executor(None, mt5.account_info)
    balance = getattr(account, "balance", 0.0) if account else 0.0
    equity  = getattr(account, "equity",  0.0) if account else 0.0
    margin  = getattr(account, "margin",  0.0) if account else 0.0

    return {
        "balance":       balance,
        "equity":        equity,
        "margin":        margin,
        "daily_pnl":     daily_pnl,
        "open_trades":   open_trades,
        "recent_trades": recent_trades,
    }


# ── Trade History ─────────────────────────────────────────

@router.get("/api/trades")
async def get_trades(limit: int = 50, user: dict = Depends(require_auth)) -> dict:
    """Trade history for accountability page."""
    user_id = user.get("sub")
    trades = get_recent_trades(limit=min(limit, 200), user_id=user_id)
    return {"trades": trades, "count": len(trades)}


# ── Bot Start / Stop (state only – trading loop in main.py) ─

class StartBotRequest(BaseModel):
    mode: str | None = "short"
    trade_count: int | None = 1
    risk_percent: float | None = None


@router.post("/api/user/start")
async def start_bot(req: StartBotRequest | None = None, request: Request = None, user: dict = Depends(require_auth)) -> dict:
    """Signal the trading loop to (re)start. Accepts risk config.
    Modes: 'short' (single trade, default), 'long' (continuous trading with auto-compounding).
    If the trading thread isn't running yet, starts it with
    MT5 credentials from Supabase mt5_credentials table.
    Requires broker_verified profile to trade."""
    # ── Check broker verification ────────────────────────────
    jwt_payload = _decode_jwt(request)
    user_id = jwt_payload.get("sub")
    if user_id:
        import os
        from brain.config.settings import SUPABASE_DB_URI
        uri = SUPABASE_DB_URI or os.getenv("SUPABASE_DB_URI")
        if uri:
            try:
                from brain.db.supabase import _get_conn
                conn = _get_conn(uri)
                with conn, conn.cursor() as cur:
                    cur.execute(
                        "SELECT broker_verified, broker_name FROM profiles WHERE id = %s",
                        (user_id,),
                    )
                    row = cur.fetchone()
                conn.close()
                if row and not row[0]:
                    raise HTTPException(
                        status_code=403,
                        detail="Account not verified. Please sign up through our partner broker to use the trading bot."
                    )
                if row:
                    logger.info("Bot start | user=%s | broker_verified=%s | broker=%s", user_id, row[0], row[1])
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning("Broker verification check failed: %s", exc)

    if req:
        risk_pct = req.risk_percent
        if risk_pct is not None:
            from brain.config.constants import MIN_RISK_PERCENT, MAX_RISK_PERCENT
            risk_pct = max(MIN_RISK_PERCENT, min(MAX_RISK_PERCENT, risk_pct))
            _bot_state["risk_percent"] = risk_pct
        mode = req.mode or "short"
        _bot_state["trading_mode"] = mode
        _bot_state["trade_count"] = req.trade_count or 1

    trading_thread = _bot_state.get("trading_thread")
    if trading_thread and trading_thread.is_alive():
        _bot_state["running"] = True
        return {"status": "already_running"}

    init_mt5_fn = _bot_state.get("_init_mt5")
    if init_mt5_fn:
        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, init_mt5_fn)
        if not ok:
            raise HTTPException(status_code=502, detail="MT5 connection failed — check credentials in /mt5")

    start_fn = _bot_state.get("_start_trading")
    if start_fn and _bot_state.get("trading_thread") is None:
        start_fn()

    _bot_state["active_user_id"] = user.get("sub")
    _bot_state["running"] = True
    logger.info("Bot start requested via API | user=%s | risk_percent=%s", user.get("sub"), _bot_state.get("risk_percent"))
    return {"status": "started"}


@router.post("/api/user/stop")
async def stop_bot(user: dict = Depends(require_auth)) -> dict:
    """Gracefully halt the trading loop."""
    _bot_state["running"] = False
    _bot_state.pop("active_user_id", None)
    logger.info("Bot stop requested via API")
    return {"status": "stopped"}


# ── Copilot ───────────────────────────────────────────────

@router.post("/api/copilot/analyze")
async def copilot_analyze(req: CopilotRequest, request: Request, user: dict = Depends(require_auth)) -> dict:
    """
    AI chart analysis via OpenRouter Claude Vision.
    Rate-limited to 15/hr per IP. Never executes trades.
    """
    client_ip = request.client.host if request.client else "unknown"

    result = await analyze_chart(
        chart_data_uri=req.chart_b64,
        pair=req.pair,
        tf=req.tf,
        client_ip=client_ip,
    )

    if "error" in result:
        if result["error"] == "rate_limit_exceeded":
            raise HTTPException(status_code=429, detail="Rate limit: 15 req/hr")
        raise HTTPException(status_code=502, detail=result["error"])

    return result


# ── MT5 Credentials (Connect / Save) ──────────────────────

class MT5ConnectRequest(BaseModel):
    login: str
    password: str
    server: str
    account_name: str | None = None


@router.post("/api/mt5/connect")
async def mt5_connect(req: MT5ConnectRequest, user: dict = Depends(require_auth)) -> dict:
    """
    Test MT5 connection and update status in Supabase.
    Credentials are saved by the frontend directly — this endpoint
    only tests connectivity and persists the connection result.
    Supports multiple accounts via account_name field.
    """
    import os
    from brain.config.settings import SUPABASE_DB_URI

    result: dict = {
        "status": "credentials_saved",
        "connected": False,
        "automated_trading_enabled": False,
        "account": None,
        "error": None,
    }

    uri = SUPABASE_DB_URI or os.getenv("SUPABASE_DB_URI")

    # ── Resolve password from Supabase if not provided ──
    login_to_use = req.login
    password_to_use = req.password
    server_to_use = req.server
    if not password_to_use and uri:
        try:
            from brain.db.supabase import _get_conn
            from utils.crypto import decrypt_password
            conn = _get_conn(uri)
            with conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT password, server FROM mt5_credentials WHERE login = %s ORDER BY updated_at DESC LIMIT 1",
                    (req.login,),
                )
                row = cur.fetchone()
            conn.close()
            if row:
                try:
                    password_to_use = decrypt_password(row[0])
                except Exception:
                    password_to_use = row[0]
                if not server_to_use and row[1]:
                    server_to_use = row[1]
        except Exception as exc:
            logger.warning("Failed to lookup password from Supabase: %s", exc)

    # Skip test if no server configured yet
    if not server_to_use:
        result["status"] = "credentials_saved"
        logger.info("No server configured yet — skipping connection test")
        return result

    # ── Test MT5 Connection (only if trading loop is NOT running) ──
    if _bot_state.get("running"):
        result["warning"] = "Trading loop is active — restart to apply new credentials"
        return result

    loop = asyncio.get_event_loop()

    def _test_connection() -> dict:
        mt5.shutdown()
        try:
            ok = mt5.initialize(
                login=int(login_to_use),
                password=password_to_use,
                server=server_to_use,
            )
            if not ok:
                err = mt5.last_error()
                mt5.shutdown()
                return {"connected": False, "error": str(err)}

            terminal = mt5.terminal_info()
            account  = mt5.account_info()

            trade_allowed = bool(getattr(terminal, "trade_allowed", False))
            account_trade = bool(getattr(account, "trade_allowed", False))

            mt5.shutdown()

            return {
                "connected": True,
                "automated_trading_enabled": trade_allowed and account_trade,
                "account": {
                    "login":    int(getattr(account, "login", 0)),
                    "server":   getattr(account, "server", ""),
                    "balance":  float(getattr(account, "balance", 0.0)),
                    "equity":   float(getattr(account, "equity", 0.0)),
                    "currency": getattr(account, "currency", "USD"),
                    "leverage": int(getattr(account, "leverage", 0)),
                    "trade_allowed": account_trade,
                } if account else None,
                "terminal": {
                    "connected":  bool(getattr(terminal, "connected", False)),
                    "build":      int(getattr(terminal, "build", 0)),
                    "name":       getattr(terminal, "name", ""),
                    "trade_allowed": trade_allowed,
                } if terminal else None,
                "error": None,
            }
        except Exception as exc:
            mt5.shutdown()
            return {"connected": False, "error": str(exc)}

    test_result = await loop.run_in_executor(None, _test_connection)
    result.update(test_result)

    # ── Persist connection result back to Supabase (match by login + server) ──
    if uri:
        try:
            from brain.db.supabase import _get_conn
            conn = _get_conn(uri)
            with conn, conn.cursor() as cur:
                cur.execute("""
                    UPDATE mt5_credentials SET
                        connected = %s,
                        automated_trading_enabled = %s,
                        last_error = %s,
                        last_connected_at = CASE WHEN %s THEN NOW() ELSE last_connected_at END,
                        updated_at = NOW()
                    WHERE login = %s AND server = %s
                """, (
                    result["connected"],
                    result["automated_trading_enabled"],
                    result.get("error"),
                    result["connected"],
                    req.login, req.server,
                ))
            conn.close()
        except Exception as exc:
            logger.warning("Failed to persist MT5 test result to Supabase: %s", exc)

    if result.get("error"):
        result["status"] = "connection_failed"
    elif result["connected"] and not result["automated_trading_enabled"]:
        result["status"] = "connected_no_ea"
    elif result["connected"] and result["automated_trading_enabled"]:
        result["status"] = "connected_ea_ready"

    logger.info(
        "MT5 connect test | status=%s | login=%s | ea=%s",
        result["status"], req.login, result["automated_trading_enabled"],
    )
    return result


# ── MT5 Connection Info ───────────────────────────────────

@router.get("/api/mt5/info")
async def mt5_info(user: dict = Depends(require_auth)) -> dict:
    """Return MT5 terminal and account information."""
    loop = asyncio.get_event_loop()
    terminal = await loop.run_in_executor(None, mt5.terminal_info)
    account  = await loop.run_in_executor(None, mt5.account_info)

    return {
        "terminal": {
            "connected":   getattr(terminal, "connected", False),
            "build":       getattr(terminal, "build", 0),
            "name":        getattr(terminal, "name", ""),
        } if terminal else None,
        "account": {
            "login":    getattr(account, "login", 0),
            "server":   getattr(account, "server", ""),
            "balance":  getattr(account, "balance", 0.0),
            "equity":   getattr(account, "equity",  0.0),
            "margin":   getattr(account, "margin",  0.0),
            "currency": getattr(account, "currency", "USD"),
            "leverage": getattr(account, "leverage", 0),
        } if account else None,
    }


@router.get("/api/mt5/accounts")
async def list_mt5_accounts(user: dict = Depends(require_auth)) -> dict:
    """List all saved MT5 accounts for the authenticated user."""
    import os
    from brain.config.settings import SUPABASE_DB_URI

    uri = SUPABASE_DB_URI or os.getenv("SUPABASE_DB_URI")
    if not uri:
        return {"accounts": []}

    user_id = user.get("sub")
    if not user_id:
        return {"accounts": []}

    try:
        from brain.db.supabase import _get_conn
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT login, server, connected, account_name, updated_at FROM mt5_credentials WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
        conn.close()
        accounts = []
        for row in rows:
            accounts.append({
                "login": row[0],
                "server": row[1],
                "connected": bool(row[2]),
                "account_name": row[3] or f"Account {row[0]}",
                "updated_at": row[4].isoformat() if row[4] else None,
            })
        return {"accounts": accounts}
    except Exception as exc:
        logger.warning("Failed to list MT5 accounts: %s", exc)

    return {"accounts": []}


class SwitchAccountRequest(BaseModel):
    login: str
    server: str


@router.post("/api/mt5/switch")
async def switch_mt5_account(req: SwitchAccountRequest, user: dict = Depends(require_auth)) -> dict:
    """Switch the active MT5 account. Requires bot to be stopped."""
    if _bot_state.get("running"):
        raise HTTPException(status_code=400, detail="Stop the bot before switching accounts")

    import os
    from brain.config.settings import SUPABASE_DB_URI

    uri = SUPABASE_DB_URI or os.getenv("SUPABASE_DB_URI")
    if not uri:
        return {"status": "error", "detail": "Database not configured"}

    try:
        from brain.db.supabase import _get_conn
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT password FROM mt5_credentials WHERE login = %s AND server = %s ORDER BY updated_at DESC LIMIT 1",
                (req.login, req.server),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        _bot_state["pending_mt5_login"] = int(req.login)
        _bot_state["pending_mt5_server"] = req.server
        return {"status": "switched", "login": req.login, "server": req.server}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to switch MT5 account: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Telegram helper (keeps bot token out of handler body) ─
def _send_telegram(bot_token: str, text: str, *admin_ids: str | None) -> None:
    """Send a message via Telegram Bot API. Token is never logged or exposed."""
    import requests
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for aid in filter(None, admin_ids):
        try:
            requests.post(url, json={"chat_id": int(aid), "text": text}, timeout=10)
        except Exception as exc:
            logger.warning("Telegram notification failed for admin %s: %s", aid, exc)


# ── Support Ticket ────────────────────────────────────────

class SupportTicketRequest(BaseModel):
    title: str
    description: str


def _decode_jwt(request: Request) -> dict:
    import base64
    import json
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {}
    token = auth.split(" ", 1)[1]
    try:
        from backend.api.middleware import decode_jwt_payload
        return decode_jwt_payload(token)
    except ImportError:
        pass
    try:
        payload_b64 = token.split(".")[1]
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return payload
    except Exception:
        return {}


@router.post("/api/support/ticket")
async def create_support_ticket(req: SupportTicketRequest, request: Request, user: dict = Depends(require_auth)) -> dict:
    """Submit a support ticket. Stores in Supabase + forwards to Telegram admin.
    The user never knows about the Telegram forwarding — it stays in the backend."""
    import os
    from brain.config.settings import SUPABASE_DB_URI

    uri = SUPABASE_DB_URI or os.getenv("SUPABASE_DB_URI")
    jwt_payload = _decode_jwt(request)
    user_id = jwt_payload.get("sub")
    email = jwt_payload.get("email", "unknown@email")

    if not uri:
        return {"status": "error", "detail": "Database not configured"}

    ticket_id = None
    display_name = f"User: {email}"
    try:
        from brain.db.supabase import _get_conn
        conn = _get_conn(uri)
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO support_tickets (user_id, email, subject, message)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id""",
                (user_id, email, req.title, req.description),
            )
            row = cur.fetchone()
            ticket_id = row[0] if row else None

            if user_id:
                cur.execute(
                    "SELECT display_name FROM profiles WHERE id = %s",
                    (user_id,),
                )
                profile = cur.fetchone()
                if profile and profile[0]:
                    display_name = f"{profile[0]} ({email})"
        conn.close()
    except Exception as exc:
        logger.warning("Failed to save support ticket: %s", exc)
        return {"status": "error", "detail": "Failed to save ticket"}

    # ── Forward to Telegram admin (completely invisible to the user) ──
    bot_token = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
    admin_id_1 = os.getenv("TELEGRAM_ADMIN_ID_1")
    admin_id_2 = os.getenv("TELEGRAM_ADMIN_ID_2")
    if bot_token and (admin_id_1 or admin_id_2):
        text = (
            f"🚨 New Support Ticket\n"
            f"─────────────────────\n"
            f"{display_name}\n"
            f"Title: {req.title}\n"
            f"Description: {req.description}"
        )
        _send_telegram(bot_token, text, admin_id_1, admin_id_2)

    logger.info("Support ticket created | id=%s | user=%s", ticket_id, email)
    return {"status": "ok", "ticket_id": ticket_id}


# ── Open Positions ────────────────────────────────────────

@router.get("/api/positions")
async def open_positions(user: dict = Depends(require_auth)) -> dict:
    """Live open positions from MT5."""
    loop = asyncio.get_event_loop()
    positions = await loop.run_in_executor(None, mt5.positions_get)

    if positions is None:
        return {"positions": []}

    return {
        "positions": [
            {
                "ticket":      int(p.ticket),
                "symbol":      p.symbol,
                "type":        "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume":      p.volume,
                "price_open":  p.price_open,
                "sl":          p.sl,
                "tp":          p.tp,
                "profit":      p.profit,
                "comment":     p.comment,
            }
            for p in positions
        ]
    }
