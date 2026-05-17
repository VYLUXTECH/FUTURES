from __future__ import annotations
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def analyze(df_1d: pd.DataFrame | None = None,
            df_1w: pd.DataFrame | None = None,
            df_1m: pd.DataFrame | None = None,
            df_4h: pd.DataFrame | None = None) -> dict:
    directional_bias = _analyze_directional_bias(df_1w, df_1m)
    daily_bias = _analyze_daily_bias(df_1d)
    h4_alignment = _analyze_h4_alignment(df_4h, daily_bias, directional_bias)

    direction = _resolve_bias(directional_bias, daily_bias, h4_alignment)
    strength = _compute_strength(directional_bias, daily_bias, h4_alignment)

    logger.debug("S6 | dir_bias=%s | day_bias=%s | h4=%s | final=%s | str=%d",
                 directional_bias["bias"], daily_bias["bias"],
                 h4_alignment["bias"], direction, strength)

    return {
        "htf_bias": direction,
        "strength": strength,
        "directional_bias": directional_bias,
        "daily_bias": daily_bias,
        "h4_alignment": h4_alignment,
    }


def _candle_bias(df: pd.DataFrame) -> str:
    if df is None or len(df) < 2:
        return "NEUTRAL"
    # Only look at last 5 candles
    c = df.iloc[-1]
    c_body = abs(c["close"] - c["open"])
    c_range = c["high"] - c["low"]
    if c_range == 0:
        return "NEUTRAL"
    body_pct = c_body / c_range
    bull = c["close"] > c["open"]
    bear = c["close"] < c["open"]

    if bull and body_pct > 0.4:
        return "BULLISH"
    elif bear and body_pct > 0.4:
        return "BEARISH"

    if bull:
        return "MILD_BULLISH"
    elif bear:
        return "MILD_BEARISH"
    return "NEUTRAL"


def _structure_bias(df: pd.DataFrame) -> str:
    if df is None or len(df) < 10:
        return "NEUTRAL"
    highs = df["high"].values
    lows = df["low"].values
    n = len(highs)

    # Only look at last 30 candles max for recent structure
    start = max(2, n - 30)
    swing_highs = []
    swing_lows = []
    for i in range(start, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(lows[i])

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1] > swing_highs[-2] and swing_lows[-1] > swing_lows[-2]:
            return "BULLISH"
        elif swing_highs[-1] < swing_highs[-2] and swing_lows[-1] < swing_lows[-2]:
            return "BEARISH"
    return "NEUTRAL"


def _analyze_directional_bias(df_1w, df_1m) -> dict:
    # Only last 5 weekly, 3 monthly candles
    df_1w = df_1w.iloc[-5:] if df_1w is not None and len(df_1w) > 5 else df_1w
    df_1m = df_1m.iloc[-3:] if df_1m is not None and len(df_1m) > 3 else df_1m
    bias_1w = _candle_bias(df_1w)
    bias_1m = _candle_bias(df_1m)
    struct_1w = _structure_bias(df_1w)
    struct_1m = _structure_bias(df_1m)

    bullish_score = 0
    bearish_score = 0

    for b in [bias_1w, bias_1m, struct_1w, struct_1m]:
        if b == "BULLISH":
            bullish_score += 2
        elif b == "MILD_BULLISH":
            bullish_score += 1
        elif b == "BEARISH":
            bearish_score += 2
        elif b == "MILD_BEARISH":
            bearish_score += 1

    if bullish_score > bearish_score and bullish_score >= 2:
        bias = "BULLISH"
        strength = int(min(90, 50 + bullish_score * 10))
    elif bearish_score > bullish_score and bearish_score >= 2:
        bias = "BEARISH"
        strength = int(min(90, 50 + bearish_score * 10))
    else:
        bias = "NEUTRAL"
        strength = 30

    return {"bias": bias, "strength": strength,
            "weekly_bias": bias_1w, "monthly_bias": bias_1m,
            "weekly_structure": struct_1w, "monthly_structure": struct_1m}


def _analyze_daily_bias(df_1d) -> dict:
    if df_1d is None or len(df_1d) < 5:
        return {"bias": "NEUTRAL", "strength": 30}
    df_1d = df_1d.iloc[-10:] if len(df_1d) > 10 else df_1d
    candle = _candle_bias(df_1d)
    struct = _structure_bias(df_1d)

    if candle in ("BULLISH",) and struct == "BULLISH":
        return {"bias": "BULLISH", "strength": 80}
    elif candle in ("BEARISH",) and struct == "BEARISH":
        return {"bias": "BEARISH", "strength": 80}
    elif candle in ("BULLISH", "MILD_BULLISH"):
        return {"bias": "BULLISH", "strength": 55}
    elif candle in ("BEARISH", "MILD_BEARISH"):
        return {"bias": "BEARISH", "strength": 55}
    return {"bias": "NEUTRAL", "strength": 30}


def _analyze_h4_alignment(df_4h, daily_bias, directional_bias) -> dict:
    if df_4h is None or len(df_4h) < 10:
        return {"bias": "NEUTRAL", "strength": 30}
    df_4h = df_4h.iloc[-40:] if len(df_4h) > 40 else df_4h
    candle = _candle_bias(df_4h)
    struct = _structure_bias(df_4h)
    closes = df_4h["close"]
    ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
    current = closes.iloc[-1]
    ema_trend = "BULLISH" if current > ema20 else "BEARISH"

    if candle in ("BULLISH",) and struct == "BULLISH":
        bias = "BULLISH"
        strength = 75
    elif candle in ("BEARISH",) and struct == "BEARISH":
        bias = "BEARISH"
        strength = 75
    elif candle in ("BULLISH", "MILD_BULLISH"):
        bias = "BULLISH"
        strength = 50
    elif candle in ("BEARISH", "MILD_BEARISH"):
        bias = "BEARISH"
        strength = 50
    else:
        bias = "NEUTRAL"
        strength = 30

    return {"bias": bias, "strength": strength, "ema_trend": ema_trend}


def _resolve_bias(directional, daily, h4) -> str:
    dir_b = directional["bias"]
    day_b = daily["bias"]
    h4_b = h4["bias"]

    # Directional bias (weekly/monthly) is primary
    if dir_b == "BULLISH" and day_b in ("BULLISH", "NEUTRAL") and h4_b in ("BULLISH", "NEUTRAL"):
        return "BULLISH"
    if dir_b == "BEARISH" and day_b in ("BEARISH", "NEUTRAL") and h4_b in ("BEARISH", "NEUTRAL"):
        return "BEARISH"

    # If directional bias is neutral, fall through to daily + 4H
    if day_b == "BULLISH" and h4_b in ("BULLISH", "NEUTRAL"):
        return "BULLISH"
    if day_b == "BEARISH" and h4_b in ("BEARISH", "NEUTRAL"):
        return "BEARISH"

    # If only 4H is aligned with directional bias
    if dir_b == "BULLISH" and h4_b == "BULLISH":
        return "BULLISH"
    if dir_b == "BEARISH" and h4_b == "BEARISH":
        return "BEARISH"

    return "NEUTRAL"


def _compute_strength(directional, daily, h4) -> int:
    score = 0
    if directional["bias"] == "BULLISH" or directional["bias"] == "BEARISH":
        score += 30
    if daily["bias"] == "BULLISH" or daily["bias"] == "BEARISH":
        score += 25
    if h4["bias"] == "BULLISH" or h4["bias"] == "BEARISH":
        score += 25
    if directional["bias"] == daily["bias"] == h4["bias"]:
        score += 20
    return int(min(100, score))
