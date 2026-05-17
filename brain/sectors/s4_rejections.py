from __future__ import annotations
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def analyze(df: pd.DataFrame, key_levels: list[float] | None = None,
            momentum_of_approach: str = "NEUTRAL") -> dict:
    if len(df) < 5 or not key_levels:
        return {"rejection": False, "direction": "NEUTRAL",
                "level": 0.0, "strength": 0, "wick_ratio": 0.0}

    c = df.iloc[-1]
    c_high = float(c["high"])
    c_low = float(c["low"])
    c_close = float(c["close"])
    c_open = float(c["open"])
    candle_range = c_high - c_low
    if candle_range == 0:
        return {"rejection": False, "direction": "NEUTRAL",
                "level": 0.0, "strength": 0, "wick_ratio": 0.0}

    upper_wick = c_high - max(c_open, c_close)
    lower_wick = min(c_open, c_close) - c_low
    upper_wick_pct = upper_wick / candle_range
    lower_wick_pct = lower_wick / candle_range

    # Volume check: current volume > avg of last 3
    volumes = df["volume"].values if "volume" in df.columns else None
    volume_ok = True
    if volumes is not None and len(volumes) >= 4:
        vol_current = volumes[-1]
        vol_avg_3 = np.mean(volumes[-4:-1])
        if vol_avg_3 > 0 and vol_current < vol_avg_3:
            volume_ok = False

    proximity_pct = 0.0030
    best = {"rejection": False, "direction": "NEUTRAL",
            "level": 0.0, "strength": 0, "wick_ratio": 0.0}
    best_wr = 0.0

    for level in key_levels:
        # Bearish rejection at resistance
        if abs(c_high - level) / level < proximity_pct:
            wr = upper_wick_pct
            if wr >= 0.45:
                strength = 85
                if "HIGH" in momentum_of_approach:
                    strength -= 20
                if volume_ok:
                    strength += 5
                if wr > best_wr:
                    best_wr = wr
                    best = {"rejection": True, "direction": "SELL",
                            "level": level, "strength": min(strength, 90),
                            "wick_ratio": round(wr, 2)}

        # Bullish rejection at support
        if abs(c_low - level) / level < proximity_pct:
            wr = lower_wick_pct
            if wr >= 0.45:
                strength = 85
                if "HIGH" in momentum_of_approach:
                    strength -= 20
                if volume_ok:
                    strength += 5
                if wr > best_wr:
                    best_wr = wr
                    best = {"rejection": True, "direction": "BUY",
                            "level": level, "strength": min(strength, 90),
                            "wick_ratio": round(wr, 2)}

    if best["rejection"]:
        wr_val: float = best["wick_ratio"]  # type: ignore[assignment]
        logger.debug("S4 | rejection dir=%s level=%.5f wick=%.0f%% str=%d vol_ok=%s",
                     best["direction"], best["level"], wr_val * 100,
                     best["strength"], volume_ok)

    return best
