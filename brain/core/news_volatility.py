# ============================================================
# FuturesBrain v1.0 – News & Volatility Filter
# BUG FIXES:
#   • mt5.calendar_get_events() → mt5.calendar_history_get()
#   • NamedTuple attribute access (e.id not e["id"])
#   • MT5NewsFilter() was re-instantiated per allow_trade() call
#     (now created once in RiskEngine.__init__)
#   • Added country→currency mapping for all three pairs
#   • SQLite news cache uses thread-safe context manager
# ============================================================
from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Generator

import MetaTrader5 as mt5

from config.constants import (
    COUNTRY_CURRENCY_MAP,
    NEWS_IMPORTANCE_HIGH,
    NEWS_WINDOW_MINUTES,
    SQLITE_NEWS_DB,
)

logger = logging.getLogger(__name__)

# Currencies we care about, derived from SUPPORTED_PAIRS
_WATCHED_CURRENCIES: frozenset[str] = frozenset({"GBP", "JPY", "USD"})

# Write lock for news SQLite
_NEWS_LOCK = threading.Lock()


@contextmanager
def _news_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(SQLITE_NEWS_DB, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()


class MT5NewsFilter:
    """
    Fetches high-impact economic events via the MT5 native calendar API
    and caches them locally in a SQLite DB.

    Instantiate ONCE (in RiskEngine.__init__) – not per trade check.
    """

    def __init__(self) -> None:
        self._init_db()

    # ── Internal DB ───────────────────────────────────────────

    def _init_db(self) -> None:
        with _NEWS_LOCK, _news_conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                       id         TEXT PRIMARY KEY,
                       event_time TEXT NOT NULL,
                       currency   TEXT NOT NULL,
                       event_name TEXT
                   )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_time ON events (event_time)"
            )
            conn.commit()

    # ── MT5 Calendar Refresh ───────────────────────────────────

    def refresh(self, hours_ahead: int = 4) -> int:
        """
        Pull upcoming high-impact events from MT5 native calendar.
        Returns number of events cached.

        MT5 calendar_history_get() returns CalendarValue NamedTuples.
        We use getattr() with fallbacks because field names vary across
        MT5 Python library versions.
        """
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)

        try:
            # ── FIX: correct API function name ─────────────────
            events = mt5.calendar_history_get(now, end)
        except Exception as exc:
            logger.warning("MT5 calendar unavailable: %s", exc)
            return 0

        if not events:
            return 0

        count = 0
        with _NEWS_LOCK, _news_conn() as conn:
            for e in events:
                # ── FIX: NamedTuple → attribute access, not dict ────
                importance = getattr(e, "importance", getattr(e, "importance_type", 0))
                if int(importance) < NEWS_IMPORTANCE_HIGH:
                    continue

                country: str = str(getattr(e, "country", "") or "")
                currency = COUNTRY_CURRENCY_MAP.get(country.upper(), country.upper())
                if currency not in _WATCHED_CURRENCIES:
                    continue

                evt_time: datetime | None = getattr(e, "time", None)
                if not evt_time:
                    continue

                # Make timezone-aware if naive
                if evt_time.tzinfo is None:
                    evt_time = evt_time.replace(tzinfo=timezone.utc)

                evt_id = str(
                    getattr(e, "id", None)
                    or getattr(e, "event_id", None)
                    or f"{country}_{int(evt_time.timestamp())}"
                )
                evt_name = str(getattr(e, "name", getattr(e, "event_name", "")))

                conn.execute(
                    "INSERT OR REPLACE INTO events VALUES (?,?,?,?)",
                    (evt_id, evt_time.isoformat(), currency, evt_name),
                )
                count += 1

            conn.commit()

        logger.debug("MT5 calendar: cached %d high-impact events", count)
        return count

    # ── News Check ────────────────────────────────────────────

    def is_news_window(self, pair: str) -> bool:
        """
        Return True if any high-impact event for this pair's currencies
        falls within ±NEWS_WINDOW_MINUTES of now.
        """
        currencies = _pair_to_currencies(pair)
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(minutes=NEWS_WINDOW_MINUTES)).isoformat()
        window_end = (now + timedelta(minutes=NEWS_WINDOW_MINUTES)).isoformat()

        placeholders = ",".join("?" * len(currencies))
        with _news_conn() as conn:
            row = conn.execute(
                f"""SELECT COUNT(*) FROM events
                    WHERE currency IN ({placeholders})
                    AND event_time BETWEEN ? AND ?""",
                (*currencies, window_start, window_end),
            ).fetchone()

        result = bool(row and row[0] > 0)
        if result:
            logger.info("📰 News window active for %s – skipping trade", pair)
        return result


def _pair_to_currencies(pair: str) -> list[str]:
    """Split e.g. 'GBPUSD' → ['GBP', 'USD']."""
    if len(pair) >= 6:
        return [pair[:3].upper(), pair[3:6].upper()]
    return [pair.upper()]


# ── ATR Volatility Tripwire ────────────────────────────────

def calculate_atr(highs, lows, closes, period: int = 14) -> float:
    """
    Vectorised ATR calculation (no TA-Lib dependency).
    Uses Wilder's smoothing (EWM with adjust=False).
    Returns the most recent ATR value or 0.0 on failure.
    """
    import pandas as pd
    import numpy as np

    try:
        highs = pd.Series(highs, dtype=float)
        lows = pd.Series(lows, dtype=float)
        closes = pd.Series(closes, dtype=float)

        prev_close = closes.shift(1)
        tr = pd.concat(
            [
                highs - lows,
                (highs - prev_close).abs(),
                (lows - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        val = float(atr.iloc[-1])
        return 0.0 if np.isnan(val) else val
    except Exception as exc:
        logger.warning("ATR calculation error: %s", exc)
        return 0.0
