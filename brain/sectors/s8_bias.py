from __future__ import annotations
import logging
from brain.config.constants import PIP_SIZES, MIN_SL_PIPS, ENABLE_SELL_TRADES

logger = logging.getLogger(__name__)

SELL_MIN_CONFIDENCE = 60
BUY_MIN_CONFIDENCE = 45
SELL_SL_BUFFER_PIPS = 3.0
BUY_SL_BUFFER_PIPS = 2.0
SELL_MIN_WICK_RATIO = 0.55
BUY_MIN_WICK_RATIO = 0.45


def synthesize(
    pair: str,
    s1: dict,
    s2: dict,
    s3: dict,
    s4: dict,
    s5: dict,
    s6: dict,
    s7: dict,
    tick_ask: float,
    tick_bid: float,
) -> dict:
    pip_size = PIP_SIZES.get(pair, 0.0001)

    if not s4.get("rejection", False):
        return _neutral_result()
    s4_dir = s4.get("direction", "NEUTRAL")
    s1_dir = s1.get("direction", "NEUTRAL")
    if s4_dir != s1_dir or s1_dir == "NEUTRAL":
        return _neutral_result()
    direction = s1_dir

    if not ENABLE_SELL_TRADES and direction == "SELL":
        return _neutral_result()

    if direction == "SELL":
        wick_ratio = s4.get("wick_ratio", 0.0)
        if wick_ratio < SELL_MIN_WICK_RATIO:
            return _neutral_result()
    else:
        wick_ratio = s4.get("wick_ratio", 0.0)
        if wick_ratio < BUY_MIN_WICK_RATIO:
            return _neutral_result()

    htf_bias = s6.get("htf_bias", "NEUTRAL")
    if direction == "BUY" and htf_bias == "BEARISH":
        return _neutral_result()
    if direction == "SELL" and htf_bias != "BEARISH":
        return _neutral_result()

    weekly = s6.get("directional_bias", {}).get("weekly_bias", "NEUTRAL")
    monthly = s6.get("directional_bias", {}).get("monthly_bias", "NEUTRAL")
    if direction == "SELL":
        if weekly in ("BULLISH", "MILD_BULLISH") or monthly in ("BULLISH", "MILD_BULLISH"):
            return _neutral_result()
        if weekly == "NEUTRAL" and monthly == "NEUTRAL":
            return _neutral_result()

    mom = s3.get("momentum_of_approach", "NEUTRAL")
    if direction == "BUY" and mom == "HIGH_TO_SUP":
        return _neutral_result()
    if direction == "SELL" and mom == "HIGH_TO_RES":
        return _neutral_result()

    if direction == "SELL":
        s2_dir = s2.get("direction", "NEUTRAL")
        s2_struct = s2.get("structure", "UNKNOWN")
        if s2_dir != "SELL":
            return _neutral_result()
        if s2_struct not in ("BOS", "RESPECT"):
            return _neutral_result()

    confirmations = _count_confirmations(direction, s2, s5, s7)
    if direction == "SELL":
        if confirmations < 2:
            return _neutral_result()
    else:
        if confirmations < 1:
            return _neutral_result()

    alignment = s7.get("alignment", "NEUTRAL")
    if direction == "SELL" and alignment != "SAFE":
        return _neutral_result()

    entry_price = s4.get("level", tick_ask if direction == "BUY" else tick_bid)

    rejection_level = s4.get("level", 0.0)
    if direction == "BUY":
        candle_ref = s1.get("candle_low", entry_price)
        sl_raw = min(rejection_level, candle_ref) - BUY_SL_BUFFER_PIPS * pip_size
    else:
        candle_ref = s1.get("candle_high", entry_price)
        sl_raw = max(rejection_level, candle_ref) + SELL_SL_BUFFER_PIPS * pip_size

    stop_loss = entry_price + abs(sl_raw - entry_price) if direction == "SELL" else entry_price - abs(entry_price - sl_raw)

    sl_pips = abs(entry_price - stop_loss) / pip_size
    if sl_pips < MIN_SL_PIPS:
        sl_pips = MIN_SL_PIPS
        stop_loss = entry_price - sl_pips * pip_size if direction == "BUY" else entry_price + sl_pips * pip_size

    tp_distance = sl_pips * 3.0
    take_profit = entry_price + tp_distance * pip_size if direction == "BUY" else entry_price - tp_distance * pip_size

    be_trigger = _find_be_level(direction, entry_price, take_profit, s3)

    confidence = _calc_confidence(direction, confirmations, s1, s2, s3, s4, s5, s6, s7)
    min_conf = SELL_MIN_CONFIDENCE if direction == "SELL" else BUY_MIN_CONFIDENCE
    if confidence < min_conf:
        return _neutral_result()

    logger.info(
        "SIGNAL | %s %s | conf=%d | entry=%.5f sl=%.5f tp=%.5f | sl=%.1fp tp=%.1fp 1:3RR | confirm=%d",
        direction, pair, confidence, entry_price, stop_loss, take_profit,
        sl_pips, tp_distance, confirmations,
    )

    return {
        "direction": direction,
        "confidence": confidence,
        "alignment": s7.get("alignment", "NEUTRAL"),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_pips": round(sl_pips, 1),
        "be_trigger": round(be_trigger, 5),
        "sectors": {
            "s1_candle": s1, "s2_structure": s2, "s3_levels": s3,
            "s4_rejections": s4, "s5_imbalances": s5,
            "s6_htf": s6, "s7_correlation": s7,
        },
    }


def _count_confirmations(direction: str, s2: dict, s5: dict, s7: dict) -> int:
    count = 1
    if s2.get("direction") == direction:
        count += 1
    if s5.get("fvg_found") and s5.get("direction") == direction:
        count += 1
    if s7.get("alignment") in ("SAFE", "COMPLEX"):
        count += 1
    if s7.get("direction_consensus") == direction:
        count += 1
    return count


def _find_be_level(direction: str, entry: float, tp: float, s3: dict) -> float:
    if direction == "BUY":
        levels = [lv for lv in s3.get("key_levels", []) if entry < lv < tp]
        if levels:
            return min(levels)
        return entry + (tp - entry) * 0.40
    else:
        levels = [lv for lv in s3.get("key_levels", []) if tp < lv < entry]
        if levels:
            return max(levels)
        return entry - (entry - tp) * 0.40


def _calc_confidence(direction: str, confirmations: int,
                     s1: dict, s2: dict, s3: dict, s4: dict,
                     s5: dict, s6: dict, s7: dict) -> int:
    base = 55
    if confirmations >= 4:
        base += 15
    elif confirmations >= 3:
        base += 10

    s1_mom = s1.get("momentum", "MEDIUM")
    s1_press = s1.get("pressure", "MEDIUM")

    if s1_mom in ("HIGH", "MEDIUM") and s1_press == "HIGH":
        base += 10

    s4_quality = int(s4.get("wick_ratio", 0) * 30)
    fvg_bonus = 8 if s5.get("fvg_found") and s5.get("direction") == direction else 0
    align_penalty = -8 if s7.get("alignment") != "SAFE" else 5
    mom_bonus = 8 if "LOW_TO" in s3.get("momentum_of_approach", "") else 0
    shift_bonus = 10 if s2.get("shift") else 0

    htf_strength = s6.get("strength", 0)
    if htf_strength >= 70:
        base += 5

    total = (base + s4_quality + fvg_bonus
             + align_penalty + mom_bonus + shift_bonus)
    return int(min(100, max(0, total)))


def _neutral_result() -> dict:
    return {"direction": "NEUTRAL", "confidence": 0, "entry_price": 0.0,
            "stop_loss": 0.0, "take_profit": 0.0, "sl_pips": 0.0,
            "be_trigger": 0.0, "sectors": {}}
