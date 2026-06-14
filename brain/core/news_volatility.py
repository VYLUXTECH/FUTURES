from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Generator

import MetaTrader5 as mt5

from brain.config.constants import (
    COUNTRY_CURRENCY_MAP,
    NEWS_IMPORTANCE_HIGH,
    NEWS_WINDOW_MINUTES,
    SQLITE_NEWS_DB,
    POST_NEWS_COOLDOWN_MINUTES,
)

logger = logging.getLogger(__name__)

_WATCHED_CURRENCIES: frozenset[str] = frozenset({"GBP", "JPY", "USD", "EUR", "CAD", "AUD", "NZD", "CHF"})

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

    def __init__(self) -> None:
        self._init_db()
        self._last_refresh: datetime | None = None
        self._refresh_interval = timedelta(minutes=15)
        self._post_news_until: datetime | None = None

    def _init_db(self) -> None:
        with _NEWS_LOCK, _news_conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                       id         TEXT PRIMARY KEY,
                       event_time TEXT NOT NULL,
                       currency   TEXT NOT NULL,
                       event_name TEXT,
                       importance INTEGER DEFAULT 3
                   )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_time ON events (event_time)"
            )
            try:
                conn.execute("ALTER TABLE events ADD COLUMN importance INTEGER DEFAULT 3")
            except Exception:
                pass
            conn.commit()

    def refresh(self, hours_ahead: int = 4, force: bool = False) -> int:
        now = datetime.now(timezone.utc)
        if not force and self._last_refresh and (now - self._last_refresh) < self._refresh_interval:
            return self._count_cached(now)

        end = now + timedelta(hours=hours_ahead)

        try:
            events = mt5.calendar_history_get(now, end)
        except Exception as exc:
            logger.warning("MT5 calendar unavailable: %s", exc)
            cached = self._count_cached(now)
            if cached > 0:
                self._last_refresh = now
                return cached
            return 0

        if not events:
            self._last_refresh = now
            cached = self._count_cached(now)
            return cached if cached > 0 else 0

        count = 0
        with _NEWS_LOCK, _news_conn() as conn:
            conn.execute("DELETE FROM events WHERE event_time < ?", (now.isoformat(),))
            for e in events:
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

                if evt_time.tzinfo is None:
                    evt_time = evt_time.replace(tzinfo=timezone.utc)

                evt_id = str(
                    getattr(e, "id", None)
                    or getattr(e, "event_id", None)
                    or f"{country}_{int(evt_time.timestamp())}"
                )
                evt_name = str(getattr(e, "name", getattr(e, "event_name", "")))
                importance_val = int(importance)

                conn.execute(
                    "INSERT OR REPLACE INTO events (id, event_time, currency, event_name, importance) VALUES (?,?,?,?,?)",
                    (evt_id, evt_time.isoformat(), currency, evt_name, importance_val),
                )
                count += 1

            conn.commit()

        self._last_refresh = now
        logger.debug("MT5 calendar: cached %d high-impact events", count)
        return count

    def _count_cached(self, now: datetime) -> int:
        window_start = (now - timedelta(minutes=NEWS_WINDOW_MINUTES)).isoformat()
        window_end = (now + timedelta(minutes=NEWS_WINDOW_MINUTES)).isoformat()
        placeholders = ",".join("?" * len(_WATCHED_CURRENCIES))
        with _news_conn() as conn:
            row = conn.execute(
                f"""SELECT COUNT(*) FROM events
                    WHERE currency IN ({placeholders})
                    AND event_time BETWEEN ? AND ?""",
                (*_WATCHED_CURRENCIES, window_start, window_end),
            ).fetchone()
        return row[0] if row else 0

    def is_news_window(self, pair: str) -> bool:
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
            logger.info("News window active for %s – skipping trade", pair)
            return True

        if self._post_news_until and now < self._post_news_until:
            remaining = int((self._post_news_until - now).total_seconds() / 60)
            logger.info("Post-news cooldown for %s (%dm remaining) – skipping", pair, remaining)
            return True

        return False

    def get_upcoming_events(self, hours_ahead: int = 4) -> list[dict]:
        now = datetime.now(timezone.utc)
        end = (now + timedelta(hours=hours_ahead)).isoformat()
        with _news_conn() as conn:
            rows = conn.execute(
                """SELECT event_time, currency, description, importance
                   FROM events WHERE event_time BETWEEN ? AND ?
                   ORDER BY event_time ASC LIMIT 20""",
                (now.isoformat(), end),
            ).fetchall()
        return [
            {"time": r[0], "currency": r[1], "description": r[2], "importance": r[3]}
            for r in rows
        ]

    def record_event_passed(self) -> None:
        now = datetime.now(timezone.utc)
        self._post_news_until = now + timedelta(minutes=POST_NEWS_COOLDOWN_MINUTES)
        logger.info("Post-news cooldown set until %s", self._post_news_until.isoformat())


def _pair_to_currencies(pair: str) -> list[str]:
    if len(pair) >= 6:
        return [pair[:3].upper(), pair[3:6].upper()]
    return [pair.upper()]


def calculate_atr(highs, lows, closes, period: int = 14) -> float:
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
