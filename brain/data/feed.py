# ============================================================
# FuturesBrain v1.0 – Market Data Feed
# All functions are SYNCHRONOUS – call from the MT5 thread only.
# BUG FIXES:
#   • DataFrame index construction was broken (pd.Series(rates)['time'])
#   • chart_open() returns chart_id which must be stored and used
#   • base64 encoding now returns proper data-URI prefix
# ============================================================
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from config.constants import SUPPORTED_PAIRS
from utils.mt5_helper import ensure_symbol

logger = logging.getLogger(__name__)

# ── Timeframe string → MT5 constant (resolved at import time) ─
TF_MAP: dict[str, int] = {
    "1m":  mt5.TIMEFRAME_M1,
    "3m":  mt5.TIMEFRAME_M3,
    "5m":  mt5.TIMEFRAME_M5,
    "15m": mt5.TIMEFRAME_M15,
    "30m": mt5.TIMEFRAME_M30,
    "1H":  mt5.TIMEFRAME_H1,
    "4H":  mt5.TIMEFRAME_H4,
    "1D":  mt5.TIMEFRAME_D1,
    "1W":  mt5.TIMEFRAME_W1,
    "1M":  mt5.TIMEFRAME_MN1,
}

_REQUIRED_COLS = ["open", "high", "low", "close", "tick_volume"]


def get_candles(pair: str, tf: str, count: int = 500) -> pd.DataFrame:
    """
    Fetch OHLCV candles from MT5.

    Returns DataFrame indexed by UTC datetime with columns:
        open, high, low, close, volume

    Raises ValueError on any failure so the caller can handle gracefully.
    """
    if pair not in SUPPORTED_PAIRS:
        raise ValueError(f"Unsupported pair: {pair}")
    if tf not in TF_MAP:
        raise ValueError(f"Unknown timeframe: {tf}")
    if not ensure_symbol(pair):
        raise ValueError(f"Symbol {pair} unavailable in MT5")

    rates = mt5.copy_rates_from_pos(pair, TF_MAP[tf], 0, count)
    if rates is None or len(rates) == 0:
        raise ValueError(
            f"No data returned for {pair}/{tf}: {mt5.last_error()}"
        )

    # ── FIX: correct DataFrame construction ───────────────────
    df = pd.DataFrame(rates)                          # columns: time, open, high, low, close, tick_volume, spread, real_volume
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    df = df[["open", "high", "low", "close", "tick_volume"]].copy()
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    df.sort_index(inplace=True)
    return df


def get_resampled(pair: str, tf: str) -> pd.DataFrame:
    """
    Return resampled OHLCV for higher timeframes not natively in MT5
    (3M, 6M, 12M calendars).
    """
    df = get_candles(pair, "1D", 3650)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    resample_map = {"3M": "QS", "6M": "6MS", "12M": "YS"}
    rule = resample_map.get(tf)
    if rule:
        return df.resample(rule).agg(agg).dropna()
    return df


def capture_chart(pair: str, tf: str, width: int = 1200, height: int = 800) -> str:
    """
    Screenshot the MT5 chart for AI vision analysis.
    Returns a base64-encoded PNG as a proper data-URI string.

    BUG FIX: chart_open() returns a chart_id (int) which must be
    passed to subsequent chart functions — not used as a bool.
    """
    charts_dir = Path("charts")
    charts_dir.mkdir(exist_ok=True)
    path = str(charts_dir / f"{pair}_{tf}.png")

    # ── FIX: store chart_id returned by chart_open ─────────────
    chart_id = mt5.chart_open(pair, TF_MAP.get(tf, mt5.TIMEFRAME_M1))
    if chart_id == 0:
        raise RuntimeError(f"chart_open failed for {pair}/{tf}: {mt5.last_error()}")

    mt5.chart_set_integer(chart_id, mt5.CHART_SHOW_GRID, 0)
    mt5.chart_set_integer(chart_id, mt5.CHART_MODE, mt5.CHART_CANDLES)
    mt5.chart_redraw(chart_id)

    if not mt5.chart_screenshot(chart_id, path, width, height):
        mt5.chart_close(chart_id)
        raise RuntimeError(f"chart_screenshot failed: {mt5.last_error()}")

    mt5.chart_close(chart_id)

    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")

    try:
        os.remove(path)
    except OSError:
        pass

    # ── FIX: include required "data:" URI scheme prefix ─────────
    return f"data:image/png;base64,{b64}"
