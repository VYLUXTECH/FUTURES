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
from brain.utils.mt5_helper import reconnect_mt5, is_connected
from brain.utils.logger import setup_logging

setup_logging()
logger = logging.getLogger("futuresbrain.main")

_stop_event = threading.Event()
_bot_state: dict = {
    "running": False,
    "risk": None,
    "risk_percent": None,
    "start_time": None,
    "trading_thread": None,
    "_init_mt5": None,
    "_start_trading": None,
}

CANDLE_TF = "15m"
SCAN_INTERVAL_SECS = 60
MONITOR_INTERVAL_SECS = 15


def _fetch_mt5_creds_from_supabase() -> tuple[int, str, str] | None:
    if not SUPABASE_DB_URI:
        return None
    try:
        from brain.db.supabase import _get_conn
        from brain.utils.crypto import decrypt_password
        conn = _get_conn(SUPABASE_DB_URI)
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT login, password, server FROM mt5_credentials ORDER BY updated_at DESC LIMIT 1"
            )
            row = cur.fetchone()
        conn.close()
        if row:
            login = int(row[0])
            password = row[1]
            try:
                password = decrypt_password(password)
            except Exception:
                pass
            return (login, password, row[2])
    except Exception as exc:
        logger.warning("Failed to fetch MT5 creds from Supabase: %s", exc)
    return None


def get_mt5_creds() -> tuple[int, str, str]:
    supabase_creds = _fetch_mt5_creds_from_supabase()
    if supabase_creds:
        return supabase_creds
    return (0, "", "")


def init_mt5(
    login: int | None = None,
    password: str | None = None,
    server: str | None = None,
) -> bool:
    if login and password and server:
        ok = reconnect_mt5(login, password, server, max_retries=5)
    else:
        _login, _password, _server = get_mt5_creds()
        if not _login:
            logger.error("No MT5 credentials available (env or Supabase)")
            return False
        ok = reconnect_mt5(_login, _password, _server, max_retries=5)
    if ok:
        for pair in SUPPORTED_PAIRS:
            mt5.symbol_select(pair, True)
        account = mt5.account_info()
        if account and not getattr(account, "trade_allowed", True):
            logger.warning("Automated trading is DISABLED in MT5 — bot will not trade")
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


def monitor_positions(risk: RiskEngine) -> None:
    open_trades = get_open_trades()
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


def trading_loop() -> None:
    logger.info("Trading thread started")
    if not init_mt5():
        logger.error("MT5 init failed — trading thread exiting")
        _bot_state["running"] = False
        return

    risk = RiskEngine()
    max_daily = _bot_state.get("max_daily_trades") or get_user_max_daily_trades()
    risk.max_daily_trades = max_daily
    _bot_state["risk"] = risk
    _bot_state["running"] = True
    _bot_state["start_time"] = datetime.now(timezone.utc).isoformat()

    last_monitor_ts = 0.0
    reconnect_attempts = 0
    MAX_RECONNECT = 10

    logger.info("Trading loop active | pairs=%s | tf=%s", SUPPORTED_PAIRS, CANDLE_TF)

    while not _stop_event.is_set():
        cycle_start = time.monotonic()

        if not is_connected():
            reconnect_attempts += 1
            logger.warning("MT5 disconnected — reconnect %d/%d", reconnect_attempts, MAX_RECONNECT)
            if reconnect_attempts >= MAX_RECONNECT:
                logger.error("Max reconnects reached — shutting down")
                _bot_state["running"] = False
                break
            time.sleep(5)
            init_mt5()
            continue
        reconnect_attempts = 0

        now_ts = time.monotonic()
        if now_ts - last_monitor_ts >= MONITOR_INTERVAL_SECS:
            try:
                monitor_positions(risk)
            except Exception as exc:
                logger.warning("Position monitor error: %s", exc)
            last_monitor_ts = now_ts

        if not _bot_state.get("running"):
            _stop_event.wait(timeout=1)
            continue

        utc_now = datetime.now(timezone.utc)
        if utc_now.weekday() >= 5:
            _stop_event.wait(timeout=60)
            continue
        if utc_now.hour < SESSION_START_UTC or utc_now.hour >= SESSION_END_UTC:
            _stop_event.wait(timeout=60)
            continue

        trading_mode = _bot_state.get("trading_mode", "short")
        if trading_mode == "short":
            if has_open_position():
                elapsed = time.monotonic() - cycle_start
                sleep_for = max(0.0, SCAN_INTERVAL_SECS - elapsed)
                _stop_event.wait(timeout=sleep_for)
                continue

        risk_percent = _bot_state.get("risk_percent")
        account_info = mt5.account_info()
        account_balance = getattr(account_info, "balance", 10000.0) if account_info else 10000.0

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
                    logger.info("Risk gate blocked %s %s: %s", signal["direction"], pair, decision.reason)
                    continue
                signal["_pair"] = pair
                signals.append(signal)
            except Exception as exc:
                logger.error("Pipeline error for %s: %s", pair, exc, exc_info=True)
                continue

        if trading_mode == "long":
            open_count = count_open_positions()
            max_concurrent = _bot_state.get("max_concurrent", 3)
            signals = signals[:max_concurrent - open_count]
            signals.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        else:
            best = pick_best_signal(signals)
            signals = [best] if best else []

        if not signals:
            elapsed = time.monotonic() - cycle_start
            sleep_for = max(0.0, SCAN_INTERVAL_SECS - elapsed)
            _stop_event.wait(timeout=sleep_for)
            continue

        for signal in signals:
            if _stop_event.is_set():
                break
            pair = signal["_pair"]
            sl_pips = signal["sl_pips"]
            auto_compound = _bot_state.get("auto_compounding", False) and trading_mode == "long"
            lots = risk.calculate_lot(pair, account_balance, sl_pips, risk_percent, auto_compound=auto_compound)
            logger.info("Executing: %s %s | conf=%d | lots=%.2f", signal["direction"], pair, signal["confidence"], lots)

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
                )
                if result:
                    logger.info("Trade executed | ticket=%s | %s %s | conf=%d%% | lots=%.2f",
                                result["ticket"], signal["direction"], pair, signal["confidence"], lots)
                else:
                    logger.warning("Order placement returned None for %s", pair)
            except Exception as exc:
                logger.error("Execution error for %s: %s", pair, exc, exc_info=True)

            if trading_mode == "short":
                break

        elapsed = time.monotonic() - cycle_start
        sleep_for = max(0.0, SCAN_INTERVAL_SECS - elapsed)
        _stop_event.wait(timeout=sleep_for)

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


_bot_state["_init_mt5"] = init_mt5
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

        login, password, server = get_mt5_creds()
        if login and server:
            _start_trading_thread()
            logger.info("FuturesBrain v2.0 started with Supabase credentials")
        else:
            logger.info("FuturesBrain v2.0 API started — waiting for MT5 credentials from Supabase")

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
