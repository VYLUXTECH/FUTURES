from __future__ import annotations

import signal
import threading
import time
import logging
from datetime import datetime, timezone

import os
import MetaTrader5 as mt5

from brain.config.constants import SUPPORTED_PAIRS, PIP_SIZES, SESSION_START_UTC, SESSION_END_UTC, MAX_DAILY_TRADES
from brain.config.settings import SUPABASE_DB_URI, validate_required
from brain.core.pipeline import run as pipeline_run
from brain.core.executor import place_order, modify_sl_to_break_even
from brain.core.risk import RiskEngine
from brain.data.feed import get_candles
from brain.db import get_open_trades, get_user_max_daily_trades
from brain.api.routes import set_bot_state_ref
from brain.db.supabase import set_state
from brain.utils.mt5_helper import reconnect_mt5, is_connected
from brain.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger("futuresbrain.main")

_stop_event = threading.Event()
_bot_state: dict = {
    "running": False,
    "start_time": None,
    "trading_thread": None,
    "_start_trading": None,
}

CANDLE_TF = "15m"
SCAN_INTERVAL_SECS = 60
MONITOR_INTERVAL_SECS = 15


def _select_symbols() -> None:
    for pair in SUPPORTED_PAIRS:
        try:
            mt5.symbol_select(pair, True)
        except Exception:
            pass


def connect_user_account(login: int, password: str, server: str) -> bool:
    ok = reconnect_mt5(login, password, server, max_retries=3)
    if ok:
        _select_symbols()
        account = mt5.account_info()
        if account and not getattr(account, "trade_allowed", True):
            logger.warning("Automated trading DISABLED for account %s", login)
    return ok


def fetch_multi_tf(pair: str) -> dict:
    df15 = get_candles(pair, "15m", 500)
    if df15 is None or len(df15) < 20:
        return {}
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    data = {"15m": df15}
    data["1H"] = df15.resample("1h").agg(agg).dropna()
    data["4H"] = df15.resample("4h").agg(agg).dropna()
    try:
        df1d = get_candles(pair, "1D", 200)
        if df1d is not None and len(df1d) > 5:
            data["1D"] = df1d
            data["1W"] = df1d.resample("W").agg(agg).dropna()
            data["1M"] = df1d.resample("ME").agg(agg).dropna()
    except Exception:
        pass
    return data


def has_open_position() -> bool:
    try:
        positions = mt5.positions_get()
        if positions is None:
            return False
        for p in positions:
            if p.symbol in SUPPORTED_PAIRS:
                return True
    except Exception:
        return bool(get_open_trades())
    return False


def count_open_positions() -> int:
    try:
        positions = mt5.positions_get()
        if positions is None:
            return 0
        return sum(1 for p in positions if p.symbol in SUPPORTED_PAIRS)
    except Exception:
        return len(get_open_trades())


def monitor_positions(risk: RiskEngine, user_id: str | None = None) -> None:
    open_trades = get_open_trades(user_id=user_id)
    if not open_trades:
        return
    for trade in open_trades:
        ticket = trade["ticket"]
        pair = trade["pair"]
        direction = trade["direction"]
        entry = trade["entry_price"] or 0.0
        sectors_json = trade.get("sectors_json")
        if not sectors_json:
            continue
        import json
        try:
            sectors = json.loads(sectors_json)
        except (json.JSONDecodeError, TypeError):
            continue
        s8 = sectors.get("s8_bias", {})
        be_price = s8.get("be_trigger", 0.0)
        pip_size = PIP_SIZES.get(pair, 0.0001)

        tick = mt5.symbol_info_tick(pair)
        if tick is None:
            continue
        current_price = tick.bid if direction == "BUY" else tick.ask

        if be_price > 0:
            modify_sl_to_break_even(
                ticket=ticket, pair=pair,
                entry_price=entry, current_price=current_price,
                direction=direction, be_trigger_price=be_price, pip_size=pip_size,
            )


def pick_best_signal(signals: list[dict]) -> dict | None:
    if not signals:
        return None
    signals.sort(key=lambda s: s.get("confidence", 0), reverse=True)
    return signals[0]


def _run_user_cycle(user: dict) -> None:
    user_id = user["user_id"]
    login = user["login"]
    password = user["password"]
    server = user["server"]

    if not connect_user_account(login, password, server):
        logger.warning("Failed to connect MT5 for user %s", user_id)
        _bot_state.setdefault(f"acct:{user_id}", {"balance": 0, "equity": 0})
        return

    account_info = mt5.account_info()
    balance = getattr(account_info, "balance", 0.0) if account_info else 0.0
    equity = getattr(account_info, "equity", 0.0) if account_info else 0.0
    _bot_state[f"acct:{user_id}"] = {"balance": balance, "equity": equity}
    set_state(f"balance:{user_id}", {"balance": balance, "equity": equity})

    try:
        from brain.core.news_volatility import MT5NewsFilter
        MT5NewsFilter().refresh(hours_ahead=8, force=False)
    except Exception:
        pass

    risk = RiskEngine(user_id=user_id)
    risk.max_daily_trades = get_user_max_daily_trades(user_id=user_id)

    monitor_positions(risk, user_id=user_id)

    account_balance = balance

    risk_percent = None
    trading_mode = "short"
    auto_compound = False
    try:
        from brain.db.supabase import _get_conn
        conn = _get_conn(SUPABASE_DB_URI)
        with conn, conn.cursor() as cur:
            cur.execute("SELECT risk_percent, trading_mode, auto_compounding FROM profiles WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                risk_percent = float(row[0]) if row[0] is not None else None
                trading_mode = row[1] or "short"
                auto_compound = bool(row[2]) if row[2] is not None else False
        conn.close()
    except Exception:
        pass

    signals = []
    for pair in SUPPORTED_PAIRS:
        if _stop_event.is_set():
            break
        try:
            data = fetch_multi_tf(pair)
            if not data:
                continue
            df = data.get("15m")
            if df is None or len(df) < 20:
                continue
            signal = pipeline_run(pair, CANDLE_TF, df, risk=risk, risk_percent=risk_percent, data=data)
            if signal is None:
                continue
            decision = risk.allow_trade(pair, current_atr=risk.baseline_atr.get(pair, 0), account_balance=account_balance)
            if not decision.allowed:
                logger.info("Risk gate blocked %s %s for user %s: %s", signal["direction"], pair, user_id, decision.reason)
                continue
            signal["_pair"] = pair
            signals.append(signal)
        except Exception as exc:
            logger.error("Pipeline error for %s user %s: %s", pair, user_id, exc, exc_info=True)
            continue

    if trading_mode == "long":
        max_concurrent = 3
        open_positions = mt5.positions_get()
        open_count = sum(1 for p in open_positions if p.symbol in SUPPORTED_PAIRS) if open_positions else 0
        signals = signals[:max_concurrent - open_count]
        signals.sort(key=lambda s: s.get("confidence", 0), reverse=True)
    else:
        if mt5.positions_get():
            return
        best = pick_best_signal(signals)
        signals = [best] if best else []

    if not signals:
        return

    for signal in signals:
        if _stop_event.is_set():
            break
        pair = signal["_pair"]
        sl_pips = signal["sl_pips"]
        lots = risk.calculate_lot(pair, account_balance, sl_pips, risk_percent, auto_compound=auto_compound)
        logger.info("Executing user=%s: %s %s | conf=%d | lots=%.2f", user_id, signal["direction"], pair, signal["confidence"], lots)

        try:
            result = place_order(
                pair=pair,
                direction=signal["direction"],
                lots=lots,
                entry_price=signal["entry_price"],
                sl_price=signal["stop_loss"],
                tp_price=signal["take_profit"],
                confidence=signal["confidence"],
                sectors=signal["sectors"],
                supabase_uri=SUPABASE_DB_URI,
                user_id=user_id,
            )
            if result:
                logger.info("Trade executed user=%s | ticket=%s | %s %s | conf=%d%% | lots=%.2f",
                            user_id, result["ticket"], signal["direction"], pair, signal["confidence"], lots)
            else:
                logger.warning("Order placement returned None for %s user %s", pair, user_id)
        except Exception as exc:
            logger.error("Execution error for %s user %s: %s", pair, user_id, exc, exc_info=True)

        if trading_mode == "short":
            break


def _refresh_account_info(user: dict) -> None:
    """Quick connect, read balance/equity, cache news. Does NOT trade."""
    user_id = user["user_id"]
    login = user["login"]
    password = user["password"]
    server = user["server"]
    if connect_user_account(login, password, server):
        info = mt5.account_info()
        balance = getattr(info, "balance", 0.0) if info else 0.0
        equity = getattr(info, "equity", 0.0) if info else 0.0
        _bot_state[f"acct:{user_id}"] = {"balance": balance, "equity": equity}
        set_state(f"balance:{user_id}", {"balance": balance, "equity": equity})
        try:
            from brain.core.news_volatility import MT5NewsFilter
            MT5NewsFilter().refresh(hours_ahead=8, force=False)
        except Exception:
            pass
    elif f"acct:{user_id}" not in _bot_state:
        _bot_state[f"acct:{user_id}"] = {"balance": 0, "equity": 0}
        set_state(f"balance:{user_id}", {"balance": 0, "equity": 0})
    mt5.shutdown()


def trading_loop() -> None:
    logger.info("Multi-user trading thread started")
    _bot_state["running"] = True
    _bot_state["start_time"] = datetime.now(timezone.utc).isoformat()
    logger.info("Trading loop active | pairs=%s | tf=%s | mode=multi-user", SUPPORTED_PAIRS, CANDLE_TF)

    while not _stop_event.is_set():
        if not _bot_state.get("running"):
            _stop_event.wait(timeout=1)
            continue

        users = get_all_mt5_credentials(SUPABASE_DB_URI)
        if not users:
            logger.debug("No MT5 credentials found — waiting for users to register")
            _stop_event.wait(timeout=30)
            continue

        utc_now = datetime.now(timezone.utc)
        can_trade = utc_now.weekday() < 5 and SESSION_START_UTC <= utc_now.hour < SESSION_END_UTC

        for user in users:
            if _stop_event.is_set() or not _bot_state.get("running"):
                break
            if can_trade:
                try:
                    _run_user_cycle(user)
                except Exception as exc:
                    logger.error("User cycle error for %s: %s", user.get("user_id"), exc, exc_info=True)
                finally:
                    mt5.shutdown()
            else:
                _refresh_account_info(user)

        _stop_event.wait(timeout=SCAN_INTERVAL_SECS)

    logger.info("Trading loop stopped cleanly")
    _bot_state["running"] = False
    mt5.shutdown()


def _handle_signal(sig, frame) -> None:
    logger.info("Shutdown signal received (%s) – stopping bot…", sig)
    _stop_event.set()
    _bot_state["running"] = False


def _start_trading_thread() -> None:
    thread = threading.Thread(
        target=trading_loop,
        name="trading_loop",
        daemon=False,
    )
    thread.start()
    _bot_state["trading_thread"] = thread


_bot_state["_start_trading"] = _start_trading_thread


def create_app() -> FastAPI:
    """Build and return the standalone FuturesBrain FastAPI app."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from brain.api.routes import router

    ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8081").split(",") if o.strip()]

    app = FastAPI(
        title="FuturesBrain API",
        version="2.0.0",
        description="Price Action S/R Scalping Bot — 1:3 RR",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(router)
    set_bot_state_ref(_bot_state)

    @app.on_event("startup")
    async def startup_event() -> None:
        missing = validate_required()
        if missing:
            logger.warning("Missing required env vars: %s — API running without trading loop", missing)

        _start_trading_thread()
        logger.info("FuturesBrain v2.0 multi-user API started")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        _stop_event.set()
        logger.info("FastAPI shutdown – stop event set")

    return app


if __name__ == "__main__":
    import uvicorn
    from brain.config.constants import API_HOST, API_PORT

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    app = create_app()
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_config=None,
        reload=False,
        workers=1,
    )
