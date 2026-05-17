# ============================================================
# FuturesBrain v1.0 – MT5 Helper Utilities
# All functions are SYNCHRONOUS – call from the MT5 thread only.
# ============================================================
from __future__ import annotations

import logging
import os
import time
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

# Common MT5 install paths on Windows
_MT5_PATHS = [
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
    r"C:\Program Files\HFM MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\HFM MetaTrader 5\terminal64.exe",
    r"C:\Program Files\HFMT5\terminal64.exe",
]


def _find_mt5_path() -> str | None:
    """Find the MT5 terminal executable on the system."""
    env_path = os.getenv("MT5_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    for path in _MT5_PATHS:
        if os.path.exists(path):
            return path
    return None


def reconnect_mt5(
    login: int,
    password: str,
    server: str,
    max_retries: int = 5,
    delay: float = 3.0,
) -> bool:
    """
    Attempt to (re)initialise MT5 with exponential backoff.
    Must be called from the dedicated MT5 thread.
    """
    mt5.shutdown()  # clean slate
    mt5_path = _find_mt5_path()
    init_kwargs = {"login": login, "password": password, "server": server}
    if mt5_path:
        init_kwargs["path"] = mt5_path
        logger.info("Using MT5 path: %s", mt5_path)

    for attempt in range(1, max_retries + 1):
        try:
            ok = mt5.initialize(**init_kwargs)
            if ok:
                info = mt5.terminal_info()
                account = mt5.account_info()
                acc_type = "DEMO" if account and getattr(account, "trade_mode", 0) == 0 else "LIVE"
                logger.info(
                    "✅ MT5 connected on attempt %d | login=%d | server=%s | type=%s | build=%s",
                    attempt, login, server, acc_type, getattr(info, "build", "?"),
                )
                return True
            err = mt5.last_error()
            logger.warning(
                "MT5 init attempt %d/%d failed: retcode=%s detail=%s",
                attempt, max_retries, err[0], err[1],
            )
        except Exception as exc:
            logger.warning("MT5 init attempt %d raised: %s", attempt, exc)
        time.sleep(delay * attempt)

    logger.error("❌ MT5 connection failed after %d attempts", max_retries)
    return False


def is_connected() -> bool:
    """Return True only when MT5 terminal is reachable."""
    info = mt5.terminal_info()
    return info is not None and bool(info.connected)


def is_market_open(pair: str) -> bool:
    """
    Return True if the symbol is tradeable right now.
    Uses trade_mode (not just `visible`) so we correctly detect
    markets that are visible but in read-only / close-only state.
    """
    info = mt5.symbol_info(pair)
    if info is None:
        return False
    # SYMBOL_TRADE_MODE_FULL == 4  (full trade permitted)
    return info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL


def ensure_symbol(pair: str) -> bool:
    """
    Select symbol in Market Watch (required before any data/tick call).
    Returns True on success.
    """
    if mt5.symbol_info(pair) is None:
        return False
    if not mt5.symbol_select(pair, True):
        logger.warning("symbol_select(%s) failed: %s", pair, mt5.last_error())
        return False
    return True
