# ============================================================
# FuturesBrain v1.0 – Trade Executor
# BUG FIXES:
#   • SL/TP now uses ABSOLUTE prices, not (pips × point)
#     point is 0.00001 for 5-digit brokers; multiplying pip
#     counts by it gave ~10× wrong distances
#   • modify_sl_to_break_even buffer calculation fixed
#   • Full retcode handling with retry on REQUOTE / PRICE_CHANGED
#   • ORDER_FILLING_IOC fallback when FOK rejected
#   • Trailing stop logic uses ATR correctly
# ============================================================
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Literal

import MetaTrader5 as mt5

from config.constants import (
    MAGIC_NUMBER,
    PIP_SIZES,
    TRAILING_ATR_MULT,
    TRAILING_TRIGGER_PIPS,
)
from db import sync_trade, get_state

logger = logging.getLogger(__name__)

DRY_RUN_KEY = "dry_run"

# Retcodes that justify a retry (price moved, not a logic error)
_RETRYABLE_RETCODES: frozenset[int] = frozenset({
    mt5.TRADE_RETCODE_REQUOTE,
    mt5.TRADE_RETCODE_PRICE_CHANGED,
    mt5.TRADE_RETCODE_PRICE_OFF,
    mt5.TRADE_RETCODE_OFF_QUOTES,
    mt5.TRADE_RETCODE_CONNECTION,
    mt5.TRADE_RETCODE_TIMEOUT,
})

Direction = Literal["BUY", "SELL"]


def place_order(
    pair: str,
    direction: Direction,
    lots: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    confidence: int,
    sectors: dict,
    supabase_uri: str | None = None,
    max_retries: int = 3,
    slippage_pips: float = 3.0,
) -> dict | None:
    """
    Place a market order with SL and TP as ABSOLUTE price levels.

    BUG FIX: Previous code multiplied pips by `point` (0.00001) producing
    wildly wrong SL/TP levels. Entry/SL/TP must be absolute prices as
    calculated by the pipeline from key levels.

    Returns the MT5 order result dict, or None on failure.
    """
    if get_state(DRY_RUN_KEY, default=False):
        logger.info(
            "DRY RUN | %s %s | lots=%.2f | entry=%.5f | sl=%.5f | tp=%.5f | conf=%d%%",
            direction, pair, lots, entry_price, sl_price, tp_price, confidence,
        )
        sync_trade(
            ticket=0, pair=pair, direction=direction,
            lots=lots, entry_price=entry_price, sl_price=sl_price,
            tp_price=tp_price, pnl=None, status="DRY_RUN",
            opened_at=datetime.now(timezone.utc).isoformat(),
            closed_at=None, confidence=confidence,
            sectors_json=json.dumps(sectors) if sectors else None,
            uri=supabase_uri,
        )
        return {"ticket": 0, "entry": entry_price, "retcode": 0, "dry_run": True}

    if not mt5.symbol_select(pair, True):
        logger.error("symbol_select(%s) failed – cannot place order", pair)
        return None

    tick = mt5.symbol_info_tick(pair)
    if tick is None:
        logger.error("No tick data for %s", pair)
        return None

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    exec_price = tick.ask if direction == "BUY" else tick.bid
    pip_size = PIP_SIZES.get(pair, 0.0001)

    # Deviation in POINTS (smallest MT5 unit), not pips
    info = mt5.symbol_info(pair)
    if info is None:
        return None
    point = info.point or 0.00001
    deviation = int((slippage_pips * pip_size) / point)

    request: dict = {
        "action":        mt5.TRADE_ACTION_DEAL,
        "symbol":        pair,
        "volume":        lots,
        "type":          order_type,
        "price":         exec_price,
        "sl":            sl_price,
        "tp":            tp_price,
        "deviation":     deviation,
        "magic":         MAGIC_NUMBER,
        "comment":       f"FB_v1 conf={confidence}",
        "type_time":     mt5.ORDER_TIME_GTC,
        "type_filling":  mt5.ORDER_FILLING_FOK,
    }

    result = None
    for attempt in range(1, max_retries + 1):
        result = mt5.order_send(request)
        if result is None:
            logger.warning("order_send returned None on attempt %d", attempt)
            time.sleep(0.5 * attempt)
            continue

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                "✅ Order placed | %s %s | ticket=%d | lots=%.2f | entry=%.5f "
                "| sl=%.5f | tp=%.5f | conf=%d%%",
                direction, pair, result.order, lots,
                exec_price, sl_price, tp_price, confidence,
            )
            sync_trade(
                ticket=result.order, pair=pair, direction=direction,
                lots=lots, entry_price=exec_price, sl_price=sl_price,
                tp_price=tp_price, pnl=None, status="OPEN",
                opened_at=datetime.now(timezone.utc).isoformat(),
                closed_at=None, confidence=confidence,
                sectors_json=json.dumps(sectors) if sectors else None,
                uri=supabase_uri,
            )
            return {"ticket": result.order, "entry": exec_price, "retcode": result.retcode}

        if result.retcode in _RETRYABLE_RETCODES:
            # Refresh price and retry
            tick = mt5.symbol_info_tick(pair)
            if tick:
                request["price"] = tick.ask if direction == "BUY" else tick.bid
            logger.warning(
                "Retryable retcode %d on attempt %d/%d – retrying…",
                result.retcode, attempt, max_retries,
            )
            time.sleep(0.3 * attempt)
            continue

        # ORDER_FILLING_FOK rejected by some brokers – try IOC
        if result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
            request["type_filling"] = mt5.ORDER_FILLING_IOC
            logger.warning("FOK fill rejected – switching to IOC")
            continue

        # Non-retryable failure
        logger.error(
            "❌ Order failed | retcode=%d | comment=%s | pair=%s %s",
            result.retcode, result.comment, direction, pair,
        )
        break

    return None


def close_position(
    ticket: int,
    pair: str,
    direction: Direction,
    lots: float,
    supabase_uri: str | None = None,
) -> bool:
    """
    Close an open position by ticket.
    Returns True on success.
    """
    tick = mt5.symbol_info_tick(pair)
    if tick is None:
        return False

    close_type = mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY
    price = tick.bid if direction == "BUY" else tick.ask

    info = mt5.symbol_info(pair)
    point = (info.point if info else None) or 0.00001
    pip_size = PIP_SIZES.get(pair, 0.0001)

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       pair,
        "volume":       lots,
        "type":         close_type,
        "position":     ticket,
        "price":        price,
        "deviation":    int((3 * pip_size) / point),
        "magic":        MAGIC_NUMBER,
        "comment":      "FB_v1 close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        pnl = _get_position_pnl(ticket)
        sync_trade(
            ticket=ticket, pair=pair, direction=direction, lots=lots,
            entry_price=None, sl_price=0, tp_price=0, pnl=pnl,
            status="CLOSED", opened_at="", closed_at=datetime.now(timezone.utc).isoformat(),
            confidence=0, uri=supabase_uri,
        )
        logger.info("✅ Position closed | ticket=%d | pnl=%.2f", ticket, pnl)
        return True

    logger.error(
        "❌ Close failed | ticket=%d | retcode=%s",
        ticket, getattr(result, "retcode", "None"),
    )
    return False


def modify_sl_to_break_even(
    ticket: int,
    pair: str,
    entry_price: float,
    current_price: float,
    direction: Direction,
    buffer_pips: float = 2.0,
    be_trigger_price: float | None = None,
    pip_size: float | None = None,
) -> bool:
    """
    Move SL to break-even when price reaches the S8-identified BE trigger
    level (first key level between entry and TP), OR at 5 pips profit as
    a safety fallback.
    """
    if pip_size is None:
        pip_size = PIP_SIZES.get(pair, 0.0001)
    buffer_price = buffer_pips * pip_size

    if direction == "BUY":
        profit_pips = (current_price - entry_price) / pip_size
        be_level = entry_price + buffer_price
        if be_trigger_price is not None and be_trigger_price > entry_price:
            be_level = be_trigger_price
    else:
        profit_pips = (entry_price - current_price) / pip_size
        be_level = entry_price - buffer_price
        if be_trigger_price is not None and be_trigger_price < entry_price:
            be_level = be_trigger_price

    if profit_pips < 0.5:
        return False

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False
    pos = positions[0]

    if direction == "BUY" and be_level <= pos.sl:
        return False
    if direction == "SELL" and be_level >= pos.sl:
        return False

    request = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   pair,
        "position": ticket,
        "sl":       round(be_level, 5),
        "tp":       pos.tp,
    }
    result = mt5.order_send(request)
    ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
    if ok:
        logger.info(
            "BE stop set | ticket=%d | new_sl=%.5f | profit=%.1f pips",
            ticket, be_level, profit_pips,
        )
    return ok


def update_trailing_stop(
    ticket: int,
    pair: str,
    entry_price: float,
    current_price: float,
    direction: Direction,
    current_atr: float,
) -> bool:
    """
    Arm and update trailing stop when +TRAILING_TRIGGER_PIPS profit reached.
    Trail distance = ATR × TRAILING_ATR_MULT.
    """
    pip_size = PIP_SIZES.get(pair, 0.0001)
    profit_pips = (
        (current_price - entry_price) if direction == "BUY"
        else (entry_price - current_price)
    ) / pip_size

    if profit_pips < TRAILING_TRIGGER_PIPS:
        return False

    trail_distance = current_atr * TRAILING_ATR_MULT   # absolute price

    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False
    pos = positions[0]

    if direction == "BUY":
        new_sl = current_price - trail_distance
        if new_sl <= pos.sl:
            return False
    else:
        new_sl = current_price + trail_distance
        if new_sl >= pos.sl:
            return False

    request = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   pair,
        "position": ticket,
        "sl":       round(new_sl, 5),
        "tp":       pos.tp,
    }
    result = mt5.order_send(request)
    ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
    if ok:
        logger.debug(
            "🔁 Trailing stop updated | ticket=%d | new_sl=%.5f | trail_dist=%.5f",
            ticket, new_sl, trail_distance,
        )
    return ok


def _get_position_pnl(ticket: int) -> float:
    """Attempt to retrieve closed-deal profit from MT5 history."""
    try:
        since = datetime(2020, 1, 1, tzinfo=timezone.utc)
        deals = mt5.history_deals_get(since, datetime.now(timezone.utc))
        if deals:
            for d in deals:
                if d.position_id == ticket:
                    return float(d.profit)
    except Exception:
        pass
    return 0.0
