from __future__ import annotations
import logging
from typing import TYPE_CHECKING

import pandas as pd

from config.constants import CONFIDENCE_THRESHOLD, VALID_ALIGNMENTS, PIP_SIZES
from db import log_signal
from sectors import (
    s1_candle,
    s2_structure,
    s3_levels,
    s4_rejections,
    s5_imbalances,
    s6_htf_structure,
    s7_tf_correlation,
    s8_bias,
)

if TYPE_CHECKING:
    from core.risk import RiskEngine

logger = logging.getLogger(__name__)


def run(
    pair: str,
    tf: str,
    df: pd.DataFrame,
    risk: "RiskEngine" | None = None,
    risk_percent: float | None = None,
    data: dict | None = None,
) -> dict | None:
    if len(df) < 20:
        return None

    if data is None:
        data = {}

    df_15m = data.get("15m", df)
    df_1h = data.get("1H", df)
    df_4h = data.get("4H", df)
    df_1d = data.get("1D")
    df_1w = data.get("1W")
    df_1m = data.get("1M")

    pip_size = PIP_SIZES.get(pair, 0.0001)
    last = df.iloc[-1]
    tick_ask = float(last["close"]) + pip_size
    tick_bid = float(last["close"]) - pip_size

    # ── Sector 1: Candle Pattern ──────────────────────────
    r1 = s1_candle.analyze(df)
    if r1["direction"] == "NEUTRAL":
        logger.debug("S1 neutral – no candle pattern for %s", pair)
        return None

    # ── Sector 2: Market Structure ────────────────────────
    r2 = s2_structure.analyze(df, s1=r1)

    # ── Sector 3: Key Levels ──────────────────────────────
    r3 = s3_levels.analyze(df, tf=tf)

    if r3["in_ignore"]:
        logger.debug("S3 ignore period active for %s", pair)
        return None

    # ── Sector 4: Rejections ──────────────────────────────
    r4 = s4_rejections.analyze(df, key_levels=r3["key_levels"],
                                momentum_of_approach=r3["momentum_of_approach"])

    if not r4.get("rejection", False):
        logger.debug("S4 no rejection for %s", pair)
        return None

    # ── Sector 5: Imbalances (multi-TF) ───────────────────
    r5 = s5_imbalances.analyze(df_15m, df_1h, df_4h, df_1d, df_1w, df_1m)

    # ── Sector 6: HTF Structure (multi-TF bias) ──────────
    r6 = s6_htf_structure.analyze(df_1d, df_1w, df_1m, df_4h)

    # ── Sector 7: TF Correlation ──────────────────────────
    r7 = s7_tf_correlation.analyze(df_15m, df_1h, df_4h, r1["direction"],
                                    d1_df=df_1d, w1_df=df_1w)

    # ── Sector 8: Bias Synthesizer ────────────────────────
    signal = s8_bias.synthesize(
        pair=pair,
        s1=r1, s2=r2, s3=r3, s4=r4, s5=r5, s6=r6, s7=r7,
        tick_ask=tick_ask,
        tick_bid=tick_bid,
    )

    direction = signal["direction"]
    confidence = signal["confidence"]

    if direction == "NEUTRAL":
        return None

    if confidence < CONFIDENCE_THRESHOLD:
        logger.info("Confidence too low for %s: %d < %d", pair, confidence, CONFIDENCE_THRESHOLD)
        return None

    alignment = signal.get("alignment", "NEUTRAL")
    if alignment not in VALID_ALIGNMENTS:
        logger.info("Alignment '%s' blocked for %s", alignment, pair)
        return None

    sl_pips = signal["sl_pips"]

    log_signal(pair, direction, confidence, alignment, signal["sectors"])

    return {
        "pair": pair,
        "direction": direction,
        "confidence": confidence,
        "alignment": alignment,
        "entry_price": signal["entry_price"],
        "stop_loss": signal["stop_loss"],
        "take_profit": signal["take_profit"],
        "sl_pips": sl_pips,
        "be_trigger": signal.get("be_trigger", 0.0),
        "sectors": signal["sectors"],
    }
