from __future__ import annotations
import logging
import pandas as pd
import numpy as np

from brain.config.constants import IGNORE_PERIODS

logger = logging.getLogger(__name__)


def analyze(df: pd.DataFrame, tf: str = "1m") -> dict:
    if len(df) < 20:
        return {"key_levels": [], "nearest_sup": 0.0,
                "nearest_res": 0.0, "in_ignore": False, "strength": 0,
                "consolidation_zone": None, "open_break_levels": [],
                "flip_levels": [], "momentum_of_approach": "NEUTRAL"}

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    current_price = float(closes[-1])
    n = len(closes)

    # Collect swing levels (5-bar pivot)
    levels: list[float] = []
    flip_bar_idx: int | None = None
    flip_levels: list[float] = []

    start = max(5, n - 300)
    for i in range(start, n - 5):
        is_high = all(highs[i] >= highs[j] for j in range(i-5, i+6) if j != i)
        is_low = all(lows[i] <= lows[j] for j in range(i-5, i+6) if j != i)

        if is_high:
            levels.append(highs[i])
        if is_low:
            levels.append(lows[i])

        # FLIP detection: price crosses a previous swing level with close beyond
        for lv_idx, lv in enumerate(levels[:-1]):
            prev_close = closes[i-1]
            if (prev_close < lv < closes[i]) or (prev_close > lv > closes[i]):
                flip_bar_idx = i
                flip_levels.append(lv)

    mean_price = np.mean(closes[-50:]) if len(closes) >= 50 else np.mean(closes)
    dedup_pips = mean_price * 0.0002  # 2bp threshold, scales with pair price
    unique_levels: list[float] = []
    for lv in sorted(set(levels)):
        if not unique_levels or abs(lv - unique_levels[-1]) > dedup_pips:
            unique_levels.append(lv)

    supports = sorted([lv for lv in unique_levels if lv < current_price], reverse=True)
    resistances = sorted([lv for lv in unique_levels if lv > current_price])
    nearest_sup = supports[0] if supports else current_price * 0.9995
    nearest_res = resistances[0] if resistances else current_price * 1.0005

    # ── Consolidation Zone ──────────────────────────────────
    consolidation_zone = _detect_consolidation(df)

    # ── Open Break Levels ───────────────────────────────────
    open_break_levels = _detect_open_break_levels(df)

    # ── Momentum of Approach ────────────────────────────────
    mom_approach = _momentum_of_approach(df, nearest_sup, nearest_res)

    # ── Flips ───────────────────────────────────────────────
    active_flips = [lv for lv in flip_levels if abs(lv - current_price) / current_price < 0.01]

    ignore_candles = IGNORE_PERIODS.get(tf, 5)
    bars_since_flip = (n - 1 - flip_bar_idx) if flip_bar_idx is not None else 9999
    in_ignore = bars_since_flip < ignore_candles

    strength = 75 if len(unique_levels) >= 4 else 50
    if consolidation_zone:
        strength += 10
    if len(active_flips) > 0:
        strength += 10

    logger.debug("S3 | %d levels | sup=%.5f | res=%.5f | ignore=%s | consol=%s | flips=%d | mom_appr=%s",
                 len(unique_levels), nearest_sup, nearest_res, in_ignore,
                 consolidation_zone is not None, len(active_flips), mom_approach)

    return {
        "key_levels": unique_levels[:10],
        "nearest_sup": nearest_sup,
        "nearest_res": nearest_res,
        "in_ignore": in_ignore,
        "strength": int(strength),
        "consolidation_zone": consolidation_zone,
        "open_break_levels": open_break_levels[:5],
        "flip_levels": active_flips[:5],
        "momentum_of_approach": mom_approach,
    }


def _detect_consolidation(df: pd.DataFrame) -> dict | None:
    if len(df) < 10:
        return None
    highs = df["high"].values[-20:]
    lows = df["low"].values[-20:]

    zone_high = max(highs)
    zone_low = min(lows)
    zone_range = zone_high - zone_low
    if zone_range == 0:
        return None

    avg_range = np.mean([highs[i] - lows[i] for i in range(len(highs))])
    if avg_range == 0:
        return None

    # Consolidation = candles staying within a tight range (range/avg < 2x)
    range_ratio = zone_range / avg_range
    if range_ratio < 1.8 and range_ratio > 0.3:
        return {"zone_high": float(zone_high), "zone_low": float(zone_low),
                "range": float(zone_range)}
    return None


def _detect_open_break_levels(df: pd.DataFrame) -> list[float]:
    if len(df) < 3:
        return []
    levels = []
    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values

    for i in range(-10, 0):
        body = abs(closes[i] - opens[i])
        candle_range = highs[i] - lows[i]
        if candle_range == 0:
            continue
        body_pct = body / candle_range
        if body_pct > 0.85:
            wick_above = highs[i] - max(opens[i], closes[i])
            wick_below = min(opens[i], closes[i]) - lows[i]
            if wick_above < body * 0.15:
                levels.append(highs[i])
            if wick_below < body * 0.15:
                levels.append(lows[i])

    return levels


def _momentum_of_approach(df: pd.DataFrame, nearest_sup: float, nearest_res: float) -> str:
    if len(df) < 5:
        return "NEUTRAL"
    closes = df["close"].values
    lows = df["low"].values
    highs = df["high"].values

    # Check momentum toward nearest resistance
    dist_to_res = nearest_res - closes[-1] if nearest_res > closes[-1] else 0
    dist_to_sup = closes[-1] - nearest_sup if closes[-1] > nearest_sup else 0

    recent_range = max(highs[-5:]) - min(lows[-5:])
    avg_candle = np.mean([highs[i] - lows[i] for i in range(-5, 0)])
    speed = recent_range / (avg_candle * 5) if avg_candle > 0 else 1

    if dist_to_res < recent_range * 2 and speed > 1.2:
        return "HIGH_TO_RES"
    elif dist_to_sup < recent_range * 2 and speed > 1.2:
        return "HIGH_TO_SUP"
    elif dist_to_res < recent_range * 2:
        return "LOW_TO_RES"
    elif dist_to_sup < recent_range * 2:
        return "LOW_TO_SUP"

    return "NEUTRAL"
