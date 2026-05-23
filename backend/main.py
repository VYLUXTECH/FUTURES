from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

# ── Ensure brain/ flat imports resolve ──────────────────
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── FuturesBrain imports ───────────────────────────────
import MetaTrader5 as mt5

from brain.utils.logger import setup_logging
from brain.config.settings import (
    SUPABASE_DB_URI, validate_required,
)
from brain.config.constants import SUPPORTED_PAIRS, PIP_SIZES, SESSION_START_UTC, SESSION_END_UTC
from brain.core.pipeline import run as pipeline_run
from brain.core.executor import place_order, update_trailing_stop, modify_sl_to_break_even
from brain.core.risk import RiskEngine
from brain.data.feed import get_candles
from brain.db.postgres import init_db, get_open_trades
from brain.api.routes import router as fb_router, set_bot_state_ref
from brain.main import get_mt5_creds
from brain.utils.mt5_helper import reconnect_mt5, is_connected

from backend.api.auth import router as auth_router
from backend.api.copilot import router as copilot_router, set_copilot_engine
from backend.api.settings import router as settings_router, set_bot_state_ref as set_settings_state_ref
from backend.api.public import router as public_router
from backend.ai import CopilotEngine, MarketSummaryEngine, ChartGenerator
from backend.db.supabase import get_client
from backend.telegram_bot import TelegramAdminBot, create_admin_bot

setup_logging()
logger = logging.getLogger("futures.app")

# ── Globals ──────────────────────────────────────────────
_stop_event = threading.Event()
_bot_state: dict = {
    "running": False,
    "risk": None,
    "start_time": None,
}
_telegram_bot: TelegramAdminBot | None = None
_trading_thread: threading.Thread | None = None

CANDLE_TF = "15m"
LOOP_INTERVAL_SECS = 60
MONITOR_INTERVAL_SECS = 15


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


def pick_best_signal(signals: list[dict]) -> dict | None:
    if not signals:
        return None
    signals.sort(key=lambda s: s.get("confidence", 0), reverse=True)
    return signals[0]

# ── Lifespan ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Init AI Copilot ──────────────────────────────
    market_engine = MarketSummaryEngine()
    chart_gen = ChartGenerator()
    copilot = CopilotEngine(market_engine, chart_gen)
    copilot.set_bot_state(_bot_state)
    set_copilot_engine(copilot)
    market_engine.start()
    logger.info("AI Copilot engine initialized")

    missing = validate_required()
    if missing:
        logger.error("Missing required env vars: %s", missing)
    else:
        init_db()
        global _trading_thread
        _trading_thread = threading.Thread(
            target=trading_loop,
            name="trading_loop",
            daemon=False,
        )
        _trading_thread.start()
        logger.info("FUTURES trading engine started")

    # ── Start Telegram admin bot ─────────────────────
    global _telegram_bot
    try:
        _telegram_bot = create_admin_bot(_bot_state)
        await _telegram_bot.start()
    except RuntimeError as exc:
        logger.warning("Telegram admin bot not started: %s", exc)
    except Exception as exc:
        logger.error("Failed to start Telegram admin bot: %s", exc)

    yield

    _stop_event.set()
    _bot_state["running"] = False
    if _trading_thread and _trading_thread.is_alive():
        logger.info("Waiting for trading thread to finish...")
        _trading_thread.join(timeout=30)
        if _trading_thread.is_alive():
            logger.warning("Trading thread did not stop within 30s")
    if _telegram_bot:
        await _telegram_bot.stop()
    logger.info("FUTURES shutting down...")


# ── FastAPI App ──────────────────────────────────────────
app = FastAPI(
    title="FUTURES",
    version="1.0.0",
    description="AI-Powered Futures/Forex Trading Bot",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,https://bot.futuretraders.net").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Routes ───────────────────────────────────────────────
app.include_router(public_router)
app.include_router(fb_router)
app.include_router(auth_router)
app.include_router(copilot_router)
app.include_router(settings_router)

set_bot_state_ref(_bot_state)
set_settings_state_ref(_bot_state)

# ── Serve web frontend ──────────────────────────────────
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
else:
    logger.warning("web/ directory not found at %s", WEB_DIR)


# ── MT5 Init ─────────────────────────────────────────────
def init_mt5() -> bool:
    login, password, server = get_mt5_creds()
    pending_login = _bot_state.get("pending_mt5_login")
    pending_server = _bot_state.get("pending_mt5_server")
    if pending_login and pending_server:
        login = pending_login
        server = pending_server
        from brain.db.supabase import _get_conn
        from brain.utils.crypto import decrypt_password
        try:
            conn = _get_conn(SUPABASE_DB_URI)
            with conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT password FROM mt5_credentials WHERE login = %s AND server = %s ORDER BY updated_at DESC LIMIT 1",
                    (login, server),
                )
                row = cur.fetchone()
            conn.close()
            if row:
                try:
                    password = decrypt_password(row[0])
                except Exception:
                    password = row[0]
        except Exception as exc:
            logger.warning("Failed to fetch pending account password: %s", exc)
        _bot_state.pop("pending_mt5_login", None)
        _bot_state.pop("pending_mt5_server", None)
        logger.info("Switched MT5 account: login=%s | server=%s", login, server)
    if not login or not server:
        logger.error("No MT5 credentials found in Supabase")
        return False
    ok = reconnect_mt5(login, password, server, max_retries=5)
    if ok:
        for pair in SUPPORTED_PAIRS:
            mt5.symbol_select(pair, True)
    return ok


# ── Position Monitor ─────────────────────────────────────
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


# ── Trading Loop ─────────────────────────────────────────
def trading_loop() -> None:
    logger.info("Trading thread started")
    if not init_mt5():
        logger.error("MT5 init failed")
        _bot_state["running"] = False
        return
    risk = RiskEngine()
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
            logger.warning("MT5 disconnected – attempt %d/%d", reconnect_attempts, MAX_RECONNECT)
            if reconnect_attempts >= MAX_RECONNECT:
                logger.error("Max reconnects reached")
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
                sleep_for = max(0.0, LOOP_INTERVAL_SECS - elapsed)
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
            sleep_for = max(0.0, LOOP_INTERVAL_SECS - elapsed)
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
                    pair=pair, direction=signal["direction"],
                    lots=lots, entry_price=signal["entry_price"],
                    sl_price=signal["stop_loss"], tp_price=signal["take_profit"],
                    confidence=signal["confidence"], sectors=signal["sectors"],
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
        sleep_for = max(0.0, LOOP_INTERVAL_SECS - elapsed)
        _stop_event.wait(timeout=sleep_for)
    logger.info("Trading loop stopped")
    _bot_state["running"] = False
    mt5.shutdown()


# ── Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host=API_HOST,
        port=API_PORT,
        log_config=None,
        reload=False,
        workers=1,
    )
