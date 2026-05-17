from __future__ import annotations
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def analyze(df: pd.DataFrame) -> dict:
    if len(df) < 15:
        return {"pattern": "INSUFFICIENT_DATA", "direction": "NEUTRAL",
                "momentum": "NEUTRAL", "pressure": "NEUTRAL", "strength": 0}

    c = df.iloc[-1]
    body = abs(c["close"] - c["open"])
    candle_range = c["high"] - c["low"]
    if candle_range == 0:
        return {"pattern": "FLAT", "direction": "NEUTRAL", "momentum": "NEUTRAL",
                "pressure": "NEUTRAL", "strength": 0,
                "candle_high": float(c["high"]), "candle_low": float(c["low"])}

    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]
    body_pct = body / candle_range
    upper_wick_pct = upper_wick / candle_range
    lower_wick_pct = lower_wick / candle_range

    bull = c["close"] > c["open"]
    bear = c["close"] < c["open"]

    avg_body_12 = np.mean([abs(df.iloc[i]["close"] - df.iloc[i]["open"])
                           for i in range(-13, -1)])
    avg_body_12 = max(avg_body_12, 0.00001)

    # Momentum: body vs avg of last 12
    body_ratio = body / avg_body_12
    if body_ratio >= 1.5:
        momentum = "HIGH"
    elif body_ratio <= 0.5:
        momentum = "LOW"
    else:
        momentum = "MEDIUM"

    # Pressure: wick % of candle range
    if bull:
        pressure_pct = upper_wick_pct
        pressure_side = "SELL"
    else:
        pressure_pct = lower_wick_pct
        pressure_side = "BUY"

    if pressure_pct > 0.60:
        pressure = "HIGH"
    elif pressure_pct < 0.30:
        pressure = "LOW"
    else:
        pressure = "MEDIUM"

    pattern, direction, strength = _detect_pattern(c, bull, bear, body_pct, body_ratio)

    logger.debug("S1 | %s | dir=%s | mom=%s(%.1fx) | press=%s(%s,%.0f%%) | str=%d",
                 pattern, direction, momentum, body_ratio, pressure,
                 pressure_side, pressure_pct * 100, strength)

    return {
        "pattern": pattern,
        "direction": direction,
        "strength": strength,
        "momentum": momentum,
        "momentum_ratio": round(body_ratio, 1),
        "pressure": pressure,
        "pressure_pct": round(pressure_pct * 100),
        "pressure_side": pressure_side,
        "candle_high": float(c["high"]),
        "candle_low": float(c["low"]),
        "body": float(body),
        "upper_wick": float(upper_wick),
        "lower_wick": float(lower_wick),
    }


def _detect_pattern(c, bull, bear, body_pct, body_ratio):
    if body_pct < 0.05:
        return "DOJI", "NEUTRAL", 40
    if bull and body_pct > 0.90 and body_ratio >= 1.5:
        return "MARUBOZU_BULL", "BUY", 70
    if bear and body_pct > 0.90 and body_ratio >= 1.5:
        return "MARUBOZU_BEAR", "SELL", 70
    direction = "BUY" if bull else ("SELL" if bear else "NEUTRAL")
    strength = 40 if direction != "NEUTRAL" else 20
    return "NONE", direction, strength
