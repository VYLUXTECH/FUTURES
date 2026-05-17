from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
import pandas as pd

from brain.config.constants import SUPPORTED_PAIRS, PIP_SIZES
from brain.data.feed import get_candles
from brain.core.news_volatility import calculate_atr

logger = logging.getLogger(__name__)


class MarketSummaryEngine:
    """
    Pre-computes a lightweight market summary for each traded pair every ~60s.
    The AI Copilot reads from this cache rather than querying MT5 directly.
    Thread-safe: writes happen on a background thread, reads via the main thread.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="market_summary", daemon=True)
        self._thread.start()
        logger.info("Market summary engine started")

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            try:
                self._refresh_all()
            except Exception as exc:
                logger.warning("Market summary refresh error: %s", exc)
            time.sleep(60)

    def _refresh_all(self) -> None:
        for pair in SUPPORTED_PAIRS:
            summary = self._build_summary(pair)
            if summary:
                with self._lock:
                    self._cache[pair] = summary

    def _build_summary(self, pair: str) -> dict | None:
        try:
            df = get_candles(pair, "1m", 100)
            if df is None or df.empty or len(df) < 20:
                return None
        except Exception:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        pip_size = PIP_SIZES.get(pair, 0.0001)

        current_price = float(last["close"])
        high_20 = float(df["high"].tail(20).max())
        low_20 = float(df["low"].tail(20).min())

        atr = calculate_atr(df["high"].values, df["low"].values, df["close"].values)
        atr = max(atr, 0.0001)

        # Nearest support/resistance (simple: recent swing low/high)
        support = low_20
        resistance = high_20
        dist_to_support = (current_price - support) / pip_size if support > 0 else 999
        dist_to_resistance = (resistance - current_price) / pip_size if resistance > 0 else 999

        # Rejection detection (long wick)
        body = abs(float(last["close"]) - float(last["open"]))
        upper_wick = float(last["high"]) - max(float(last["close"]), float(last["open"]))
        lower_wick = min(float(last["close"]), float(last["open"])) - float(last["low"])
        rejection = None
        if body > 0 and (upper_wick > body * 1.5 or lower_wick > body * 1.5):
            if lower_wick > upper_wick:
                rejection = "bullish (long lower wick)"
            else:
                rejection = "bearish (long upper wick)"

        # Short-term bias
        sma5 = float(df["close"].tail(5).mean())
        sma20 = float(df["close"].tail(20).mean())
        bias = "bullish" if sma5 > sma20 else "bearish"

        return {
            "pair": pair,
            "price": round(current_price, 5),
            "support": round(support, 5),
            "resistance": round(resistance, 5),
            "dist_to_support_pips": round(dist_to_support, 1),
            "dist_to_resistance_pips": round(dist_to_resistance, 1),
            "bias": bias,
            "atr": round(atr, 5),
            "rejection": rejection,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_summary(self, pair: str) -> dict | None:
        with self._lock:
            return self._cache.get(pair)

    def get_all_summaries(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._cache)
