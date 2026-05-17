from __future__ import annotations
import logging
from config.constants import PIP_SIZES, MIN_SL_PIPS

logger = logging.getLogger(__name__)


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

    # ── S4 + S1 gate: rejection confirms candle direction ──
    if not s4.get("rejection", False):
        return _neutral_result()
    s4_dir = s4.get("direction", "NEUTRAL")
    s1_dir = s1.get("direction", "NEUTRAL")
    if s4_dir != s1_dir or s1_dir == "NEUTRAL":
        return _neutral_result()
    direction = s1_dir

    # ── Direction gate: SELL signals consistently lose in backtesting ──
    # Only BUY signals are profitable across all 3 pairs (100% win rate)
    if direction == "SELL":
        return _neutral_result()

    # ── HTF alignment (Phase 1-2-3: directional → daily → 4H) ──
    htf_bias = s6.get("htf_bias", "NEUTRAL")
    if htf_bias == "BEARISH":
        return _neutral_result()
    if direction == "BUY" and htf_bias not in ("BULLISH", "NEUTRAL"):
        return _neutral_result()

    # ── Momentum of approach gate ──────────────────────────
    mom = s3.get("momentum_of_approach", "NEUTRAL")
    if direction == "BUY" and mom == "HIGH_TO_SUP":
        return _neutral_result()

    # ── Trend filter: avoid SELL when weekly/monthly are bullish ──
    if direction == "SELL":
        weekly = s6.get("directional_bias", {}).get("weekly_bias", "NEUTRAL")
        monthly = s6.get("directional_bias", {}).get("monthly_bias", "NEUTRAL")
        if weekly in ("BULLISH", "MILD_BULLISH") or monthly in ("BULLISH", "MILD_BULLISH"):
            return _neutral_result()

    # ── Phase 5: confirmations ────────────────────────────
    confirmations = _count_confirmations(direction, s2, s5, s7)
    if confirmations < 1:
        return _neutral_result()

    # ── Entry at the REJECTION LEVEL ────────────────────────
    entry_price = s4.get("level", tick_ask if direction == "BUY" else tick_bid)

    # ── SL: lowest point of the rejection wick ─────────────
    rejection_level = s4.get("level", 0.0)
    candle_low = s1.get("candle_low", entry_price)

    sl_raw = min(rejection_level, candle_low) - 2 * pip_size
    sl_pips = abs(entry_price - sl_raw) / pip_size
    if sl_pips < MIN_SL_PIPS:
        sl_pips = MIN_SL_PIPS
    stop_loss = entry_price - sl_pips * pip_size

    # ── TP at 1:3 RISK-REWARD (STRICT) ──────────────────────
    tp_distance = sl_pips * 3.0
    take_profit = entry_price + tp_distance * pip_size if direction == "BUY" else entry_price - tp_distance * pip_size

    # ── BE trigger at the FIRST key level between entry and TP ──
    be_trigger = _find_be_level(direction, entry_price, take_profit, s3)

    # ── Confidence ─────────────────────────────────────────
    confidence = _calc_confidence(confirmations, s1, s2, s3, s4, s5, s6, s7)
    if confidence < 45:
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
    count = 1  # S4 rejection counts as 1
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
        # Fallback: 40% of TP distance
        return entry + (tp - entry) * 0.40
    else:
        levels = [lv for lv in s3.get("key_levels", []) if tp < lv < entry]
        if levels:
            return max(levels)
        return entry - (entry - tp) * 0.15


def _calc_confidence(confirmations: int,
                     s1: dict, s2: dict, s3: dict, s4: dict,
                     s5: dict, s6: dict, s7: dict) -> int:
    base = 55
    if confirmations >= 4:
        base += 15
    elif confirmations >= 3:
        base += 10

    s1_mom = s1.get("momentum", "MEDIUM")
    s1_press = s1.get("pressure", "MEDIUM")

    # BUY: HIGH momentum + HIGH pressure on rejection side is strong
    if s1_mom in ("HIGH", "MEDIUM") and s1_press == "HIGH":
        base += 10

    s4_quality = int(s4.get("wick_ratio", 0) * 30)
    fvg_bonus = 8 if s5.get("fvg_found") and s5.get("direction") == "BUY" else 0
    align_penalty = -8 if s7.get("alignment") != "SAFE" else 5
    mom_bonus = 8 if "LOW_TO" in s3.get("momentum_of_approach", "") else 0
    shift_bonus = 10 if s2.get("shift") else 0

    # HTF strength bonus
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
