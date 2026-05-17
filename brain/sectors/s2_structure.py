from __future__ import annotations
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def analyze(df: pd.DataFrame, s1: dict | None = None) -> dict:
    if len(df) < 10:
        return {"structure": "UNKNOWN", "direction": "NEUTRAL",
                "last_high": 0.0, "last_low": 0.0, "strength": 0,
                "break_momentum": "NONE", "respect": False}

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    opens = df["open"].values
    n = len(closes)

    swing_highs = []
    swing_lows = []
    start = max(2, n - 200)
    for i in range(start, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append((i, highs[i]))
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append((i, lows[i]))

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"structure": "FORMING", "direction": "NEUTRAL",
                "last_high": float(highs[-1]), "last_low": float(lows[-1]),
                "strength": 30, "break_momentum": "NONE", "respect": False}

    last_sh = swing_highs[-1][1]
    prev_sh = swing_highs[-2][1]
    last_sl = swing_lows[-1][1]
    prev_sl = swing_lows[-2][1]
    current_close = closes[-1]
    current_low = lows[-1]
    current_high = highs[-1]
    avg_body = np.mean([abs(closes[i] - opens[i]) for i in range(-5, 0)])
    avg_body = max(avg_body, 0.0001)
    break_momentum = "NONE"
    respect = False

    # Detect BREAK: price breaks a prior swing high/low
    bullish_break = current_high > last_sh and current_close > last_sh
    bearish_break = current_low < last_sl and current_close < last_sl

    if bullish_break or bearish_break:
        break_size = abs(current_close - (last_sh if bullish_break else last_sl))
        break_momentum_label = "HIGH" if break_size > avg_body * 1.5 else "LOW"

        if bullish_break:
            direction = "BUY"
            structure = "BOS"
            strength = 85 if break_momentum_label == "HIGH" else 65
        else:
            direction = "SELL"
            structure = "BOS"
            strength = 85 if break_momentum_label == "HIGH" else 65

        return {
            "structure": structure,
            "direction": direction,
            "last_high": last_sh,
            "last_low": last_sl,
            "strength": strength,
            "break_momentum": break_momentum_label,
            "respect": False,
            "break_size": round(break_size, 5),
            "shift": False,
        }

    # Detect RESPECT: price approached a swing level but failed to break
    resistance_dist = abs(current_high - last_sh) / last_sh if last_sh > 0 else 1
    support_dist = abs(current_low - last_sl) / last_sl if last_sl > 0 else 1

    if resistance_dist < 0.001 and current_close < last_sh:
        respect = True
        direction = "SELL"
        structure = "RESPECT"
        strength = 75
    elif support_dist < 0.001 and current_close > last_sl:
        respect = True
        direction = "BUY"
        structure = "RESPECT"
        strength = 75
    else:
        direction = "BUY" if last_sh > prev_sh else "SELL"
        structure = "CONTINUATION"
        strength = 55

    # Detect SHIFT: break of multi-swing structure
    shift = False
    if len(swing_highs) >= 3 and current_high > swing_highs[-3][1] and current_close > swing_highs[-3][1]:
        if last_sh > prev_sh and current_high > swing_highs[-3][1]:
            shift = True
            strength = max(strength, 90)
    if len(swing_lows) >= 3 and current_low < swing_lows[-3][0]:
        if last_sl < prev_sl and current_low < swing_lows[-3][1]:
            shift = True
            strength = max(strength, 90)

    logger.debug("S2 | %s | dir=%s | break_mom=%s | respect=%s | shift=%s | str=%d",
                 structure, direction, break_momentum, respect, shift, strength)

    return {
        "structure": structure,
        "direction": direction,
        "last_high": last_sh,
        "last_low": last_sl,
        "strength": strength,
        "break_momentum": break_momentum,
        "respect": respect,
        "shift": shift,
    }
