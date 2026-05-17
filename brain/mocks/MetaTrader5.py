"""
Mock MetaTrader5 module for backtesting.
Replaces the real MT5 with pre-loaded synthetic data.
"""
from __future__ import annotations

import numpy as np

# Timeframe constants
TIMEFRAME_M1 = 1; TIMEFRAME_M2 = 2; TIMEFRAME_M3 = 3
TIMEFRAME_M4 = 4; TIMEFRAME_M5 = 5; TIMEFRAME_M6 = 6
TIMEFRAME_M10 = 10; TIMEFRAME_M12 = 12; TIMEFRAME_M15 = 15
TIMEFRAME_M20 = 20; TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 16385; TIMEFRAME_H2 = 16386; TIMEFRAME_H3 = 16387
TIMEFRAME_H4 = 16388; TIMEFRAME_H6 = 16390; TIMEFRAME_H8 = 16392
TIMEFRAME_H12 = 16396
TIMEFRAME_D1 = 16408; TIMEFRAME_W1 = 32769; TIMEFRAME_MN1 = 49153

# Trade constants
SYMBOL_TRADE_MODE_FULL = 4
ORDER_TYPE_BUY = 0; ORDER_TYPE_SELL = 1
TRADE_ACTION_DEAL = 1; TRADE_ACTION_SLTP = 5
ORDER_TIME_GTC = 0; ORDER_FILLING_FOK = 0; ORDER_FILLING_IOC = 1
TRADE_RETCODE_DONE = 10009; TRADE_RETCODE_REQUOTE = 10004
TRADE_RETCODE_PRICE_CHANGED = 10015; TRADE_RETCODE_PRICE_OFF = 10005
TRADE_RETCODE_OFF_QUOTES = 10006; TRADE_RETCODE_CONNECTION = 10007
TRADE_RETCODE_TIMEOUT = 10008; TRADE_RETCODE_INVALID_FILL = 10025

# Global state - reset between backtest runs
_current_price = 1.25000
_data_cache: dict[tuple, np.ndarray] = {}
_account_balance = 10000.0


class _Tick:
    pass


class _Account:
    pass


class _SymbolInfo:
    point = 0.00001
    trade_tick_value = 1.0
    trade_tick_size = 0.00001
    volume_min = 0.01
    volume_max = 50.0
    volume_step = 0.01
    trade_mode = SYMBOL_TRADE_MODE_FULL


class _TerminalInfo:
    connected = True


def symbol_select(pair, enable=True):
    return True


def symbol_info_tick(pair):
    t = _Tick()
    t.ask = round(_current_price + 0.0001, 5)
    t.bid = round(_current_price - 0.0001, 5)
    return t


def account_info():
    a = _Account()
    a.balance = _account_balance
    return a


def symbol_info(pair):
    return _SymbolInfo()


def copy_rates_from_pos(pair, tf, start, count):
    key = (pair, tf)
    dtype = np.dtype([('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
                      ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'),
                      ('spread', '<i8'), ('real_volume', '<i8')])
    if key not in _data_cache:
        return np.array([], dtype=dtype)
    data = _data_cache[key]
    return data[-count:] if len(data) >= count else data


def order_send(request):
    return None


def positions_get(ticket=None):
    return []


def history_deals_get(*args):
    return []


def last_error():
    return ("MOCK_NO_ERROR", 0)


def initialize(**kwargs):
    return True


def shutdown():
    pass


def terminal_info():
    return _TerminalInfo()


def calendar_history_get(*args, **kwargs):
    return None


def reset(current_price=1.25000, balance=10000.0):
    """Reset all mock state between backtest runs."""
    global _current_price, _data_cache, _account_balance
    _current_price = current_price
    _data_cache = {}
    _account_balance = balance
