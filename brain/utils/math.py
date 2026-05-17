# ============================================================
# FuturesBrain v1.0 – Math Utilities
# ============================================================
from __future__ import annotations

from config.constants import PIP_SIZES


def pips_to_price(pair: str, pips: float) -> float:
    """Convert a pip count to a price distance."""
    return pips * PIP_SIZES[pair]


def price_to_pips(pair: str, price_distance: float) -> float:
    """Convert an absolute price distance to pips."""
    pip_size = PIP_SIZES.get(pair, 0.0001)
    if pip_size == 0:
        return 0.0
    return abs(price_distance) / pip_size


def calculate_rr(sl_pips: float, tp_pips: float) -> float:
    """Risk-reward ratio."""
    if sl_pips <= 0:
        return 0.0
    return tp_pips / sl_pips


def calculate_retracement(high: float, low: float, current: float) -> float:
    """Fib-style retracement percentage (0–100)."""
    total_move = high - low
    if total_move == 0:
        return 0.0
    return abs(current - low) / total_move * 100.0


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, value))
