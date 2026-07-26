from __future__ import annotations

import os
import sys
import threading
import logging
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# ── Ensure brain/ flat imports resolve ──────────────────
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── FuturesBrain imports ───────────────────────────────
from brain.utils.logger import setup_logging
from brain.config.settings import (
    SUPABASE_DB_URI, validate_required,
)
from brain.db.postgres import init_db

from brain.api.routes import router as fb_router, set_bot_state_ref
import brain.main as brain_main
from brain.main import (
    trading_loop,
    connect_user_account,
    monitor_positions,
    fetch_multi_tf,
    pick_best_signal,
)

from backend.api.auth import router as auth_router
from backend.api.copilot import router as copilot_router, set_copilot_engine
from backend.api.settings import router as settings_router, set_bot_state_ref as set_settings_state_ref
from backend.api.public import router as public_router
from backend.ai import CopilotEngine, MarketSummaryEngine, ChartGenerator
from backend.db.supabase import get_client

setup_logging()
logger = logging.getLogger("futures.app")

# ── Globals ──────────────────────────────────────────────
_stop_event = threading.Event()
_bot_state: dict = {
    "running": False,
    "risk": None,
    "start_time": None,
}
_trading_thread: threading.Thread | None = None


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

    # ── Share bot state / stop event with brain.main ────
    brain_main._bot_state = _bot_state
    brain_main._stop_event = _stop_event

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
        logger.info("THE DISCIPLE trading engine started")

    yield

    _stop_event.set()
    _bot_state["running"] = False
    if _trading_thread and _trading_thread.is_alive():
        logger.info("Waiting for trading thread to finish...")
        _trading_thread.join(timeout=30)
        if _trading_thread.is_alive():
            logger.warning("Trading thread did not stop within 30s")

    if _bot_state.get("restart_requested"):
        logger.info("Restart requested — starting new trading thread...")
        _stop_event.clear()
        _bot_state["restart_requested"] = False
        _trading_thread = threading.Thread(
            target=trading_loop,
            name="trading_loop",
            daemon=False,
        )
        _trading_thread.start()
        logger.info("Trading engine restarted")
        return  # keep the bot running; lifespan continues until actual shutdown

    logger.info("THE DISCIPLE shutting down...")


# ── FastAPI App ──────────────────────────────────────────
app = FastAPI(
    title="THE DISCIPLE",
    version="1.0.0",
    description="AI-Powered Futures/Forex Trading Bot by Richie Rich",
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


# ── Restart helper ────────────────────────────────────────
def _restart_engine():
    global _trading_thread
    logger.info("Restarting trading engine...")
    _stop_event.set()
    _bot_state["running"] = False
    if _trading_thread and _trading_thread.is_alive():
        _trading_thread.join(timeout=30)
    _stop_event.clear()
    _bot_state["restart_requested"] = False
    _trading_thread = threading.Thread(target=trading_loop, name="trading_loop", daemon=False)
    _trading_thread.start()
    logger.info("Trading engine restarted")


_bot_state["_restart_fn"] = _restart_engine


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
