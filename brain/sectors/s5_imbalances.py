from __future__ import annotations
import logging
import pandas as pd

logger = logging.getLogger(__name__)

MIN_GAP_RATIO = 0.30


def analyze(df_15m: pd.DataFrame, df_1h: pd.DataFrame | None = None,
            df_4h: pd.DataFrame | None = None,
            df_1d: pd.DataFrame | None = None,
            df_1w: pd.DataFrame | None = None,
            df_1m: pd.DataFrame | None = None) -> dict:
    imbalances = []
    direction = "NEUTRAL"
    best_strength = 0

    dfs_to_check = [
        ("15m", df_15m),
        ("1H", df_1h),
        ("4H", df_4h),
        ("1D", df_1d),
        ("1W", df_1w),
        ("1M", df_1m),
    ]

    for tf_name, tf_df in dfs_to_check:
        if tf_df is None or len(tf_df) < 3:
            continue
        result = _find_fvg(tf_df, tf_name)
        if result and result["fvg_found"]:
            imbalances.append(result)
            if result["strength"] > best_strength:
                best_strength = result["strength"]
                direction = result["direction"]

    if not imbalances:
        return {"fvg_found": False, "direction": "NEUTRAL",
                "fvg_high": 0.0, "fvg_low": 0.0, "strength": 35,
                "imbalances": []}

    # Higher TF imbalances get more weight
    tf_weight = {"15m": 1, "1H": 2, "4H": 3, "1D": 4, "1W": 5, "1M": 6}
    buy_w = sum(tf_weight.get(imb["timeframe"], 1) for imb in imbalances if imb["direction"] == "BUY")
    sell_w = sum(tf_weight.get(imb["timeframe"], 1) for imb in imbalances if imb["direction"] == "SELL")

    if buy_w > sell_w:
        direction = "BUY"
        strength = int(min(90, 50 + buy_w * 8))
    elif sell_w > buy_w:
        direction = "SELL"
        strength = int(min(90, 50 + sell_w * 8))
    elif imbalances:
        direction = imbalances[0]["direction"]
        strength = imbalances[0]["strength"]
    else:
        direction = "NEUTRAL"
        strength = 35

    fvg_high = max(imb["fvg_high"] for imb in imbalances) if imbalances else 0.0
    fvg_low = min(imb["fvg_low"] for imb in imbalances) if imbalances else 0.0

    logger.debug("S5 | %d imbalances found | dir=%s | str=%d | tf=%s",
                 len(imbalances), direction, strength,
                 [i["timeframe"] for i in imbalances])

    return {
        "fvg_found": len(imbalances) > 0,
        "direction": direction,
        "fvg_high": fvg_high,
        "fvg_low": fvg_low,
        "strength": strength,
        "imbalances": imbalances,
    }


def _find_fvg(df: pd.DataFrame, tf_name: str) -> dict | None:
    if len(df) < 3:
        return None

    c0 = df.iloc[-3]
    c1 = df.iloc[-2]
    c2 = df.iloc[-1]

    c1_range = c1["high"] - c1["low"]

    # Bullish FVG
    if c2["low"] > c0["high"]:
        gap = c2["low"] - c0["high"]
        if c1_range > 0 and (gap / c1_range) >= MIN_GAP_RATIO:
            return {
                "fvg_found": True,
                "direction": "BUY",
                "fvg_high": float(c2["low"]),
                "fvg_low": float(c0["high"]),
                "strength": 75,
                "timeframe": tf_name,
                "gap_ratio": round(gap / c1_range, 2),
            }

    # Bearish FVG
    if c2["high"] < c0["low"]:
        gap = c0["low"] - c2["high"]
        if c1_range > 0 and (gap / c1_range) >= MIN_GAP_RATIO:
            return {
                "fvg_found": True,
                "direction": "SELL",
                "fvg_high": float(c0["low"]),
                "fvg_low": float(c2["high"]),
                "strength": 75,
                "timeframe": tf_name,
                "gap_ratio": round(gap / c1_range, 2),
            }

    return None
