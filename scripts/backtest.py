#!/usr/bin/env python3
"""
FUTURES Trading Bot — Comprehensive Backtest Engine
Uses real 15min candle data (Dukascopy 2024-2026, ~58k candles/pair).
Tests both BUY and SELL signals with proper HTF bias matching.
"""
from __future__ import annotations

import sys
import random
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np
import pandas as pd

# ── Add brain to path ──────────────────────────────────────
_BRAIN = str(Path(__file__).resolve().parent.parent / "brain")
if _BRAIN not in sys.path:
    sys.path.insert(0, _BRAIN)

# ── Mock MT5 ──────────────────────────────────────────────
class MockTick:
    def __init__(self, bid, ask):
        self.bid, self.ask = bid, ask

class MockSymbolInfo:
    def __init__(self, pair):
        if "JPY" in pair:
            self.trade_tick_value, self.trade_tick_size, self.point = 10.0, 0.01, 0.001
        else:
            self.trade_tick_value, self.trade_tick_size, self.point = 10.0, 0.00001, 0.00001
        self.volume_min, self.volume_max, self.volume_step = 0.01, 50.0, 0.01

class MockAccount:
    def __init__(self):
        self.balance = self.equity = 10000.0
        self.margin = 0.0
        self.trade_allowed = True

class MockTerminal:
    def __init__(self):
        self.connected = self.trade_allowed = True
        self.build, self.name = 4000, "MetaTrader 5"

class MockMT5:
    TRADE_RETCODE_DONE = 10009
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    TIMEFRAME_M15 = 4

    def symbol_info_tick(self, pair): return MockTick(self._last_bid, self._last_ask)
    def symbol_info(self, pair): return MockSymbolInfo(pair)
    def account_info(self): return MockAccount()
    def terminal_info(self): return MockTerminal()
    def positions_get(self, ticket=None): return None
    def symbol_select(self, pair, flag): return True
    def copy_rates_from_pos(self, pair, tf, pos, count): return None
    def last_error(self): return (0, "OK")
    def initialize(self, **kwargs): return True
    def shutdown(self): pass
    def order_send(self, request):
        r = type('Result', (), {'retcode': 10009, 'order': random.randint(100000, 999999), 'comment': 'Done'})()
        return r

mt5 = MockMT5()
sys.modules["MetaTrader5"] = mt5

# ── Import brain modules ───────────────────────────────────
from config.constants import SUPPORTED_PAIRS, PIP_SIZES, TARGET_RR, SESSION_START_UTC, SESSION_END_UTC, ENABLE_SELL_TRADES
from sectors import s1_candle, s2_structure, s3_levels, s4_rejections, s5_imbalances, s6_htf_structure, s7_tf_correlation

# ── Patch s8_bias to allow SELL signals ────────────────────
import sectors.s8_bias as s8_bias

def synthesize_allow_sell(pair, s1, s2, s3, s4, s5, s6, s7, tick_ask, tick_bid):
    pip_size = PIP_SIZES.get(pair, 0.0001)
    if not s4.get("rejection", False):
        return _neutral()
    s4_dir = s4.get("direction", "NEUTRAL")
    s1_dir = s1.get("direction", "NEUTRAL")
    if s4_dir != s1_dir or s1_dir == "NEUTRAL":
        return _neutral()
    direction = s1_dir

    if not ENABLE_SELL_TRADES and direction == "SELL":
        return _neutral()

    htf_bias = s6.get("htf_bias", "NEUTRAL")
    if direction == "BUY" and htf_bias == "BEARISH":
        return _neutral()
    if direction == "SELL" and htf_bias == "BULLISH":
        return _neutral()
    if htf_bias not in ("BULLISH", "BEARISH", "NEUTRAL"):
        return _neutral()

    mom = s3.get("momentum_of_approach", "NEUTRAL")
    if direction == "BUY" and mom == "HIGH_TO_SUP":
        return _neutral()
    if direction == "SELL" and mom == "HIGH_TO_RES":
        return _neutral()

    confirmations = _count_confirmations(direction, s2, s5, s7)
    if confirmations < 1:
        return _neutral()

    entry_price = s4.get("level", tick_ask if direction == "BUY" else tick_bid)
    rejection_level = s4.get("level", 0.0)
    candle_ref = s1.get("candle_low" if direction == "BUY" else "candle_high", entry_price)

    if direction == "BUY":
        sl_raw = min(rejection_level, candle_ref) - 2 * pip_size
        sl_pips = abs(entry_price - sl_raw) / pip_size
        sl_pips = max(sl_pips, 5.0)
        stop_loss = entry_price - sl_pips * pip_size
        tp_distance = sl_pips * 3.0
        take_profit = entry_price + tp_distance * pip_size
    else:
        sl_raw = max(rejection_level, candle_ref) + 2 * pip_size
        sl_pips = abs(entry_price - sl_raw) / pip_size
        sl_pips = max(sl_pips, 5.0)
        stop_loss = entry_price + sl_pips * pip_size
        tp_distance = sl_pips * 3.0
        take_profit = entry_price - tp_distance * pip_size

    confidence = _calc_confidence(confirmations, s1, s2, s3, s4, s5, s6, s7)
    if confidence < 45:
        return _neutral()

    return {
        "direction": direction, "confidence": confidence,
        "alignment": s7.get("alignment", "NEUTRAL"),
        "entry_price": entry_price, "stop_loss": stop_loss,
        "take_profit": take_profit, "sl_pips": round(sl_pips, 1),
    }

def _neutral():
    return {"direction": "NEUTRAL", "confidence": 0, "entry_price": 0.0,
            "stop_loss": 0.0, "take_profit": 0.0, "sl_pips": 0.0}

def _count_confirmations(direction, s2, s5, s7):
    count = 1
    if s2.get("direction") == direction: count += 1
    if s5.get("fvg_found") and s5.get("direction") == direction: count += 1
    if s7.get("alignment") in ("SAFE", "COMPLEX"): count += 1
    if s7.get("direction_consensus") == direction: count += 1
    return count

def _calc_confidence(confirmations, s1, s2, s3, s4, s5, s6, s7):
    base = 55
    if confirmations >= 4: base += 15
    elif confirmations >= 3: base += 10
    s1_mom = s1.get("momentum", "MEDIUM")
    s1_press = s1.get("pressure", "MEDIUM")
    if s1_mom in ("HIGH", "MEDIUM") and s1_press == "HIGH": base += 10
    s4_quality = int(s4.get("wick_ratio", 0) * 30)
    fvg_bonus = 8 if s5.get("fvg_found") else 0
    align_penalty = -8 if s7.get("alignment") != "SAFE" else 5
    mom_bonus = 8 if "LOW_TO" in s3.get("momentum_of_approach", "") else 0
    shift_bonus = 10 if s2.get("shift") else 0
    htf_strength = s6.get("strength", 0)
    if htf_strength >= 70: base += 5
    return int(min(100, max(0, base + s4_quality + fvg_bonus + align_penalty + mom_bonus + shift_bonus)))

s8_bias.synthesize = synthesize_allow_sell

logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")

# ── Data Loading ───────────────────────────────────────────
def load_data(pair):
    fname = pair.replace("/", "")
    path = Path(__file__).parent / "data" / f"{fname}_15m.csv"
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.sort_index(inplace=True)
    df["atr"] = _compute_atr(df, 14)
    return df

def _compute_atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def build_multi_tf(df_15m):
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    data = {"15m": df_15m}
    data["1H"] = df_15m.resample("1h").agg(agg).dropna()
    data["4H"] = df_15m.resample("4h").agg(agg).dropna()
    try:
        data["1D"] = df_15m.resample("1D").agg(agg).dropna()
        data["1W"] = df_15m.resample("W").agg(agg).dropna()
        data["1M"] = df_15m.resample("ME").agg(agg).dropna()
    except Exception:
        pass
    return data

# ── Pipeline Runner ────────────────────────────────────────
def run_pipeline(pair, df_window, data_multi):
    if len(df_window) < 20:
        return None
    pip_size = PIP_SIZES[pair]
    last = df_window.iloc[-1]
    tick_ask = float(last["close"]) + pip_size
    tick_bid = float(last["close"]) - pip_size

    df_15m = data_multi.get("15m", df_window)
    df_1h = data_multi.get("1H", df_window)
    df_4h = data_multi.get("4H", df_window)
    df_1d = data_multi.get("1D")
    df_1w = data_multi.get("1W")
    df_1m = data_multi.get("1M")

    r1 = s1_candle.analyze(df_window)
    if r1["direction"] == "NEUTRAL": return None

    r2 = s2_structure.analyze(df_window, s1=r1)
    r3 = s3_levels.analyze(df_window, tf="15m")
    if r3["in_ignore"]: return None

    r4 = s4_rejections.analyze(df_window, key_levels=r3["key_levels"],
                                momentum_of_approach=r3["momentum_of_approach"])
    if not r4.get("rejection", False): return None
    if r4.get("direction", "NEUTRAL") != r1["direction"]: return None

    r5 = s5_imbalances.analyze(df_15m, df_1h, df_4h, df_1d, df_1w, df_1m)
    r6 = s6_htf_structure.analyze(df_1d, df_1w, df_1m, df_4h)
    r7 = s7_tf_correlation.analyze(df_15m, df_1h, df_4h, r1["direction"],
                                    d1_df=df_1d, w1_df=df_1w)

    signal = s8_bias.synthesize(
        pair=pair, s1=r1, s2=r2, s3=r3, s4=r4, s5=r5, s6=r6, s7=r7,
        tick_ask=tick_ask, tick_bid=tick_bid,
    )
    if signal["direction"] == "NEUTRAL": return None
    if signal["confidence"] < 50: return None
    if signal.get("alignment", "NEUTRAL") not in ("SAFE", "COMPLEX"): return None
    return signal

def simulate_trade(df_future, signal, pip_size, lookahead=200):
    future = df_future.head(lookahead)
    if len(future) == 0: return "TIMEOUT", 0.0
    entry, sl, tp, direction = signal["entry_price"], signal["stop_loss"], signal["take_profit"], signal["direction"]
    if entry <= 0 or sl <= 0 or tp <= 0: return "INVALID", 0.0

    highs, lows = future["high"].values, future["low"].values
    if direction == "BUY":
        sl_hits = np.where(lows <= sl)[0]
        tp_hits = np.where(highs >= tp)[0]
    else:
        sl_hits = np.where(highs >= sl)[0]
        tp_hits = np.where(lows <= tp)[0]

    if len(sl_hits) == 0 and len(tp_hits) == 0: return "TIMEOUT", 0.0
    first_sl = sl_hits[0] if len(sl_hits) > 0 else float("inf")
    first_tp = tp_hits[0] if len(tp_hits) > 0 else float("inf")

    if first_sl < first_tp:
        return "SL", -abs(entry - sl) / pip_size
    else:
        return "TP", abs(tp - entry) / pip_size

# ── Main Backtest ──────────────────────────────────────────
def run_backtest():
    print("=" * 70)
    print("  FUTURES Trading Bot — Comprehensive Backtest")
    print("  Dukascopy 15m Data | 3 Pairs | 1:3 RR | BUY+SELL | 8-Sector Pipeline")
    print("=" * 70)
    print()

    all_trades = []
    pair_results = {}

    for pair in SUPPORTED_PAIRS:
        print(f"Loading {pair}...")
        df = load_data(pair)
        print(f"  {len(df)} candles | {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")

        pip_size = PIP_SIZES[pair]
        window_size, scan_step, cooldown = 500, 20, 80
        trades = []
        last_signal_idx = -cooldown

        total_windows = (len(df) - window_size - 200) // scan_step
        print(f"  Scanning {total_windows} windows...")

        for i in range(window_size, len(df) - 200, scan_step):
            pct = int((i - window_size) / (len(df) - window_size - 200) * 100)
            if pct % 25 == 0 and pct > 0:
                print(f"    {pct}%...", end="\r")

            df_window = df.iloc[i-window_size:i]
            df_future = df.iloc[i:i+200]

            candle_hour = df_window.index[-1].hour
            candle_weekday = df_window.index[-1].weekday()
            if candle_weekday >= 5:
                continue
            if candle_hour < SESSION_START_UTC or candle_hour >= SESSION_END_UTC:
                continue

            current_atr = df_window.iloc[-1].get("atr", 0)
            avg_atr = df_window["atr"].iloc[-50:].mean()
            if avg_atr > 0:
                atr_ratio = current_atr / avg_atr
                if atr_ratio < 0.3 or atr_ratio > 2.5:
                    continue

            if i - last_signal_idx < cooldown:
                continue

            data_multi = build_multi_tf(df_window)
            signal = run_pipeline(pair, df_window, data_multi)
            if signal is None:
                continue

            last_signal_idx = i
            outcome, pips = simulate_trade(df_future, signal, pip_size)

            trade = {
                "pair": pair, "idx": i,
                "direction": signal["direction"],
                "confidence": signal["confidence"],
                "alignment": signal.get("alignment", "NEUTRAL"),
                "entry": signal["entry_price"],
                "sl": signal["stop_loss"],
                "tp": signal["take_profit"],
                "sl_pips": signal["sl_pips"],
                "outcome": outcome, "pips": pips,
                "timestamp": df_window.index[-1],
            }
            trades.append(trade)
            all_trades.append(trade)

        print(f"    100%  |  {len(trades)} trades found")
        pair_results[pair] = trades

    # ── Statistics ─────────────────────────────────────────
    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)

    for pair in SUPPORTED_PAIRS:
        trades = pair_results[pair]
        _print_pair_stats(pair, trades)

    # Overall
    print()
    print("-" * 70)
    print("  OVERALL")
    print("-" * 70)
    _print_stats("ALL", all_trades)

    # By direction
    print()
    print("-" * 70)
    print("  WIN RATE BY DIRECTION")
    print("-" * 70)
    for direction in ["BUY", "SELL"]:
        dir_trades = [t for t in all_trades if t["direction"] == direction and t["outcome"] in ("TP", "SL")]
        if dir_trades:
            _print_stats(direction, dir_trades)

    # By confidence band
    print()
    print("-" * 70)
    print("  WIN RATE BY CONFIDENCE BAND")
    print("-" * 70)
    for lo, hi in [(50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]:
        band = [t for t in all_trades if lo <= t["confidence"] < hi and t["outcome"] in ("TP", "SL")]
        if band:
            _print_stats(f"{lo}-{hi-1}%", band)

    # By pair
    print()
    print("-" * 70)
    print("  WIN RATE BY PAIR")
    print("-" * 70)
    for pair in SUPPORTED_PAIRS:
        pair_trades = [t for t in all_trades if t["pair"] == pair and t["outcome"] in ("TP", "SL")]
        if pair_trades:
            _print_stats(pair, pair_trades)

    # Trades per day
    print()
    print("-" * 70)
    print("  TRADES PER DAY")
    print("-" * 70)
    if all_trades:
        date_counts = defaultdict(int)
        date_wins = defaultdict(int)
        for t in all_trades:
            date = t["timestamp"].strftime("%Y-%m-%d")
            date_counts[date] += 1
            if t["outcome"] == "TP":
                date_wins[date] += 1

        days = len(date_counts)
        avg_trades = len(all_trades) / days if days else 0
        max_trades = max(date_counts.values()) if date_counts else 0
        winning_days = sum(1 for d in date_counts if date_wins.get(d, 0) > date_counts[d] / 2)

        print(f"  Trading days:        {days}")
        print(f"  Avg trades/day:      {avg_trades:.1f}")
        print(f"  Max trades in a day: {max_trades}")
        print(f"  Winning days (>50%): {winning_days}/{days} ({winning_days/days*100:.1f}%)")

        # Top 10 busiest days
        sorted_days = sorted(date_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"  Top 10 busiest days:")
        for date, count in sorted_days:
            wins = date_wins.get(date, 0)
            wr = wins/count*100 if count else 0
            print(f"    {date}: {count} trades | {wins} wins | {wr:.0f}% WR")

    print()
    print("=" * 70)
    overall_wr = sum(1 for t in all_trades if t["outcome"] == "TP") / max(1, sum(1 for t in all_trades if t["outcome"] in ("TP", "SL"))) * 100
    verdict = "PROFITABLE" if overall_wr > 25.0 else "NEEDS IMPROVEMENT"
    print(f"  VERDICT: {verdict} (need >25% WR for 1:3 RR)")
    print("=" * 70)

def _print_pair_stats(pair, trades):
    print()
    print(f"  {pair}")
    _print_stats("", trades)

def _print_stats(label, trades):
    resolved = [t for t in trades if t["outcome"] in ("TP", "SL")]
    if not resolved:
        if label: print(f"    {label}: No resolved trades")
        return

    tp = sum(1 for t in resolved if t["outcome"] == "TP")
    sl = sum(1 for t in resolved if t["outcome"] == "SL")
    wr = tp / len(resolved) * 100
    net_pips = sum(t["pips"] for t in resolved)
    avg_pips = net_pips / len(resolved)

    rr_wins = sum(t["sl_pips"] * 3 for t in resolved if t["outcome"] == "TP")
    rr_losses = sum(t["sl_pips"] for t in resolved if t["outcome"] == "SL")
    pf = rr_wins / rr_losses if rr_losses else float("inf")

    expectancy = net_pips / len(resolved)

    prefix = f"    {label}: " if label else "    "
    print(f"{prefix}Trades: {len(resolved)} | Wins: {tp} | Losses: {sl}")
    print(f"{prefix}Win Rate: {wr:.1f}% | Net Pips: {net_pips:+.1f} | Avg: {avg_pips:+.1f}")
    print(f"{prefix}Profit Factor: {pf:.2f} | Expectancy: {expectancy:+.1f} pips/trade")

if __name__ == "__main__":
    run_backtest()
