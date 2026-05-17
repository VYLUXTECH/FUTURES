# ============================================================
# FuturesBrain v1.0 – Risk Engine
# BUG FIXES:
#   • MT5NewsFilter() instantiated ONCE in __init__, not per check
#   • Lot sizing formula completely rewritten (was tick_val/pip_val)
#   • Daily reset uses date comparison, not balance==0.0
#   • 3-loss cooldown now persists across restarts via DB state
#   • allow_trade() returns a structured rejection reason
# ============================================================
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import NamedTuple

import MetaTrader5 as mt5

from config.constants import (
    COOLDOWN_HOURS,
    DAILY_DRAWDOWN_LIMIT,
    DEFAULT_RISK_PERCENT,
    MIN_RISK_PERCENT,
    MAX_RISK_PERCENT,
    MAX_DAILY_TRADES,
    MIN_SL_PIPS,
    MAX_SL_PIPS,
    PIP_SIZES,
)
from core.news_volatility import MT5NewsFilter
from db import (
    count_losses_last_24h,
    count_trades_today,
    get_state,
    set_state,
)

logger = logging.getLogger(__name__)


class TradeDecision(NamedTuple):
    allowed: bool
    reason: str


class RiskEngine:
    """
    Stateful risk manager. One instance for the lifetime of the process.
    Thread-safety: all mutations are gated behind the GIL (single trading
    thread model). Do NOT call from multiple threads simultaneously.
    """

    def __init__(self, max_daily_trades: int | None = None) -> None:
        # ── FIX: instantiate news filter ONCE ─────────────────
        self.news_filter = MT5NewsFilter()

        # Daily tracking (reset when calendar date changes)
        self.daily_start_balance: float = 0.0
        self._last_reset_date: str = ""     # "YYYY-MM-DD"

        # Cooldown tracking
        self.in_cooldown: bool = False
        self.cooldown_until: datetime | None = None

        # Baseline ATR per pair (set on first observation)
        self.baseline_atr: dict[str, float] = {}

        # Per-user max daily trades (defaults to constant if not provided)
        self.max_daily_trades: int = max_daily_trades if max_daily_trades is not None else MAX_DAILY_TRADES

        # Restore persisted cooldown state across restarts
        self._restore_state()

    # ── State Persistence ─────────────────────────────────────

    def _restore_state(self) -> None:
        cd_until_iso = get_state("cooldown_until")
        if cd_until_iso:
            try:
                until = datetime.fromisoformat(cd_until_iso)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                if until > datetime.now(timezone.utc):
                    self.in_cooldown = True
                    self.cooldown_until = until
                    logger.info("🔒 Cooldown restored until %s", until.isoformat())
            except ValueError:
                pass

    def _persist_cooldown(self, until: datetime) -> None:
        set_state("cooldown_until", until.isoformat())

    # ── Daily Reset ───────────────────────────────────────────

    def maybe_reset_daily(self, current_balance: float) -> None:
        """
        Reset daily counters when the calendar date changes (UTC).
        BUG FIX: Previously compared balance==0.0 which was unreliable.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._last_reset_date = today
            self.daily_start_balance = current_balance
            logger.info(
                "📅 Daily reset | date=%s | balance=%.2f", today, current_balance
            )

    # ── Master Trade Gate ─────────────────────────────────────

    def allow_trade(
        self,
        pair: str,
        current_atr: float,
        account_balance: float,
    ) -> TradeDecision:
        """
        Run all risk gates in priority order.
        Returns TradeDecision(allowed=True) only when ALL gates pass.
        """
        # 1. Cooldown gate
        if self.in_cooldown:
            if self.cooldown_until and datetime.now(timezone.utc) < self.cooldown_until:
                remaining = (self.cooldown_until - datetime.now(timezone.utc)).seconds // 60
                return TradeDecision(False, f"Cooldown active ({remaining}m remaining)")
            else:
                # Cooldown expired – reset
                self.in_cooldown = False
                self.cooldown_until = None
                set_state("cooldown_until", None)
                logger.info("✅ Cooldown expired – resuming trading")

        # 2. Daily drawdown gate (5%)
        self.maybe_reset_daily(account_balance)
        if self.daily_start_balance > 0:
            drawdown = (self.daily_start_balance - account_balance) / self.daily_start_balance
            if drawdown >= DAILY_DRAWDOWN_LIMIT:
                return TradeDecision(
                    False,
                    f"Daily drawdown limit reached ({drawdown:.1%} ≥ {DAILY_DRAWDOWN_LIMIT:.0%})",
                )

        # 3. Max daily trades gate
        trades_today = count_trades_today()
        if trades_today >= self.max_daily_trades:
            return TradeDecision(
                False, f"Max daily trades reached ({trades_today}/{self.max_daily_trades})"
            )

        # 4. 3-loss cooldown check
        losses_24h = count_losses_last_24h()
        if losses_24h >= 3:
            self._trigger_cooldown(reason=f"{losses_24h} losses in 24h")
            return TradeDecision(False, f"3-loss cooldown triggered ({losses_24h} losses)")

        # 5. News window gate
        self.news_filter.refresh(hours_ahead=4)
        if self.news_filter.is_news_window(pair):
            return TradeDecision(False, f"High-impact news window for {pair}")

        # 6. ATR volatility spike gate
        if pair in self.baseline_atr and self.baseline_atr[pair] > 0:
            if current_atr > self.baseline_atr[pair] * 1.25:
                return TradeDecision(
                    False,
                    f"ATR spike: {current_atr:.5f} > baseline {self.baseline_atr[pair]:.5f} × 1.25",
                )
        else:
            # Seed baseline on first observation
            if current_atr > 0:
                self.baseline_atr[pair] = current_atr
                logger.debug("ATR baseline set for %s: %.5f", pair, current_atr)

        return TradeDecision(True, "OK")

    def _trigger_cooldown(self, reason: str = "") -> None:
        """Arm COOLDOWN_HOURS-hour cooldown and persist to DB."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        until = now + timedelta(hours=COOLDOWN_HOURS)
        self.in_cooldown = True
        self.cooldown_until = until
        self._persist_cooldown(until)
        logger.warning(
            "🚫 Trading cooldown triggered | reason=%s | until=%s",
            reason, until.isoformat()
        )

    def update_baseline_atr(self, pair: str, atr: float) -> None:
        """
        Exponentially smooth the baseline ATR to adapt over time.
        α=0.05 means baseline updates slowly (keeps historical context).
        """
        if atr <= 0:
            return
        if pair not in self.baseline_atr:
            self.baseline_atr[pair] = atr
        else:
            alpha = 0.05
            self.baseline_atr[pair] = (
                alpha * atr + (1 - alpha) * self.baseline_atr[pair]
            )

    # ── Lot Sizing ────────────────────────────────────────────

    def calculate_lot(
        self,
        pair: str,
        account_balance: float,
        sl_pips: float,
        risk_percent: float | None = None,
    ) -> float:
        """
        Dynamic lot sizing using MT5 tick value.

        Formula:
            risk_amount   = balance × risk_percent
            pip_value     = (tick_value / tick_size) × pip_size
            lots          = risk_amount / (sl_pips × pip_value_per_lot)

        BUG FIX: Previous code did tick_val/pip_val which is dimensionally
        wrong. Now uses the correct pip value per lot formula.

        risk_percent: user-configurable 0-10% (defaults to DEFAULT_RISK_PERCENT)
        """
        if risk_percent is None:
            risk_percent = DEFAULT_RISK_PERCENT
        risk_percent = max(MIN_RISK_PERCENT, min(MAX_RISK_PERCENT, risk_percent))
        risk_frac = risk_percent / 100.0

        # Clamp SL pips to safe bounds
        sl_pips = max(MIN_SL_PIPS, min(MAX_SL_PIPS, sl_pips))

        info = mt5.symbol_info(pair)
        if info is None:
            logger.warning("symbol_info(%s) returned None – using 0.01 lot", pair)
            return 0.01

        pip_size = PIP_SIZES.get(pair, 0.0001)

        # Value of 1 pip per 1.0 standard lot in account currency
        tick_val: float = info.trade_tick_value       # e.g. 1.0 USD per tick per lot
        tick_size: float = info.trade_tick_size       # e.g. 0.00001 for 5-digit broker
        if tick_size <= 0 or tick_val <= 0:
            return 0.01

        pip_value_per_lot: float = (tick_val / tick_size) * pip_size

        risk_amount = account_balance * risk_frac
        lots = risk_amount / (sl_pips * pip_value_per_lot)

        # Snap to broker's allowed lot step
        vol_min: float = getattr(info, "volume_min", 0.01) or 0.01
        vol_max: float = getattr(info, "volume_max", 50.0) or 50.0
        vol_step: float = getattr(info, "volume_step", 0.01) or 0.01

        lots = max(vol_min, min(vol_max, round(lots / vol_step) * vol_step))
        lots = round(lots, 2)

        logger.debug(
            "Lot calc | %s | balance=%.2f | sl_pips=%.1f | pip_val=%.4f | lots=%.2f",
            pair, account_balance, sl_pips, pip_value_per_lot, lots,
        )
        return lots
