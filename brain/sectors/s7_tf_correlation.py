from __future__ import annotations
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def analyze(
    m15_df: pd.DataFrame,
    h1_df: pd.DataFrame,
    h4_df: pd.DataFrame,
    entry_bias: str,
    d1_df: pd.DataFrame | None = None,
    w1_df: pd.DataFrame | None = None,
) -> dict:
    # Analyze each timeframe
    m15_dir = _tf_direction(m15_df)
    h1_dir = _tf_direction(h1_df)
    h4_dir = _tf_direction(h4_df)
    d1_dir = _tf_direction(d1_df) if d1_df is not None else "NEUTRAL"
    w1_dir = _tf_direction(w1_df) if w1_df is not None else "NEUTRAL"

    individual = {
        "m15": m15_dir,
        "h1": h1_dir,
        "h4": h4_dir,
        "d1": d1_dir,
        "w1": w1_dir,
    }

    alignment_quality = _compute_alignment(individual, entry_bias)
    direction_consensus = _direction_consensus(individual)
    timeframe_aligned = _check_alignment(individual, entry_bias)

    logger.debug("S7 | entry=%s | m15=%s h1=%s h4=%s d1=%s w1=%s | align=%s score=%d",
                 entry_bias, m15_dir, h1_dir, h4_dir, d1_dir, w1_dir,
                 alignment_quality["alignment"], alignment_quality["score"])

    return {
        "alignment": alignment_quality["alignment"],
        "score": alignment_quality["score"],
        "strength": alignment_quality["strength"],
        "individual": individual,
        "direction_consensus": direction_consensus,
        "timeframe_aligned": timeframe_aligned,
    }


def _tf_direction(df: pd.DataFrame) -> str:
    if df is None or len(df) < 10:
        return "NEUTRAL"
    closes = df["close"]

    ema = closes.ewm(span=20, adjust=False).mean()
    ema_slope = float(ema.iloc[-1]) - float(ema.iloc[-5]) if len(ema) >= 5 else 0

    current = float(closes.iloc[-1])

    if ema_slope > 0 and current > ema.iloc[-1]:
        return "BUY"
    elif ema_slope < 0 and current < ema.iloc[-1]:
        return "SELL"
    elif current > ema.iloc[-1]:
        return "MILD_BUY"
    elif current < ema.iloc[-1]:
        return "MILD_SELL"
    return "NEUTRAL"


def _compute_alignment(individual: dict, entry_bias: str) -> dict:
    score = 0.0
    weights = {"m15": 15, "h1": 20, "h4": 25, "d1": 25, "w1": 15}

    for tf, direction in individual.items():
        w = weights.get(tf, 10)
        if direction == entry_bias:
            score += w
        elif direction == f"MILD_{entry_bias}":
            score += w * 0.5

    if score >= 60:
        alignment = "SAFE"
        strength = 90
    elif score >= 35:
        alignment = "COMPLEX"
        strength = 55
    elif score >= 25:
        alignment = "UNCERTAIN"
        strength = 30
    else:
        alignment = "NEUTRAL"
        strength = 15

    return {"alignment": alignment, "score": score, "strength": strength}


def _direction_consensus(individual: dict) -> str:
    buys = sum(1 for d in individual.values() if d in ("BUY", "MILD_BUY"))
    sells = sum(1 for d in individual.values() if d in ("SELL", "MILD_SELL"))
    if buys > sells:
        return "BUY"
    elif sells > buys:
        return "SELL"
    return "NEUTRAL"


def _check_alignment(individual: dict, entry_bias: str) -> bool:
    aligned_tfs = [
        tf for tf, direction in individual.items()
        if direction == entry_bias
    ]
    return len(aligned_tfs) >= 2
