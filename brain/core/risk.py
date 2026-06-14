from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import NamedTuple

import MetaTrader5 as mt5

from brain.config.constants import (
    COOLDOWN_HOURS,
    DAILY_DRAWDOWN_LIMIT,
    DEFAULT_RISK_PERCENT,
    MIN_RISK_PERCENT,
    MAX_RISK_PERCENT,
    MAX_DAILY_TRADES,
    MIN_SL_PIPS,
    MAX_SL_PIPS,
    PIP_SIZES,
    MAX_SPREAD_PIPS,
)
from brain.core.news_volatility import MT5NewsFilter
from brain.db import (
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

    def __init__(self, max_daily_trades: int | None = None, user_id: str | None = None) -> None:
        self.user_id: str | None = user_id
        self.news_filter = MT5NewsFilter()

        self.daily_start_balance: float = 0.0
        self._last_reset_date: str = ""

        self.in_cooldown: bool = False
        self.cooldown_until: datetime | None = None

        self.baseline_atr: dict[str, float] = {}

        self.max_daily_trades: int = max_daily_trades if max_daily_trades is not None else MAX_DAILY_TRADES

        self._restore_state()

    def _cooldown_key(self) -> str:
        return f"cooldown_until:{self.user_id}" if self.user_id else "cooldown_until"

    def _restore_state(self) -> None:
        cd_until_iso = get_state(self._cooldown_key())
        if cd_until_iso:
            try:
                until = datetime.fromisoformat(cd_until_iso)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                if until > datetime.now(timezone.utc):
                    self.in_cooldown = True
                    self.cooldown_until = until
                    logger.info("Cooldown restored for user %s until %s", self.user_id, until.isoformat())
            except ValueError:
                pass

    def _persist_cooldown(self, until: datetime) -> None:
        set_state(self._cooldown_key(), until.isoformat())

    def maybe_reset_daily(self, current_balance: float) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._last_reset_date = today
            self.daily_start_balance = current_balance
            logger.info(
                "Daily reset | user=%s | date=%s | balance=%.2f",
                self.user_id, today, current_balance,
            )

    def allow_trade(
        self,
        pair: str,
        current_atr: float,
        account_balance: float,
    ) -> TradeDecision:
        if self.in_cooldown:
            if self.cooldown_until and datetime.now(timezone.utc) < self.cooldown_until:
                remaining = (self.cooldown_until - datetime.now(timezone.utc)).seconds // 60
                return TradeDecision(False, f"Cooldown active ({remaining}m remaining)")
            else:
                self.in_cooldown = False
                self.cooldown_until = None
                set_state("cooldown_until", None)
                logger.info("Cooldown expired – resuming trading")

        self.maybe_reset_daily(account_balance)
        if self.daily_start_balance > 0:
            drawdown = (self.daily_start_balance - account_balance) / self.daily_start_balance
            if drawdown >= DAILY_DRAWDOWN_LIMIT:
                return TradeDecision(
                    False,
                    f"Daily drawdown limit reached ({drawdown:.1%} >= {DAILY_DRAWDOWN_LIMIT:.0%})",
                )

        trades_today = count_trades_today(user_id=self.user_id)
        if trades_today >= self.max_daily_trades:
            return TradeDecision(
                False, f"Max daily trades reached ({trades_today}/{self.max_daily_trades})"
            )

        losses_24h = count_losses_last_24h(user_id=self.user_id)
        if losses_24h >= 3:
            self._trigger_cooldown(reason=f"{losses_24h} losses in 24h")
            return TradeDecision(False, f"3-loss cooldown triggered ({losses_24h} losses)")

        spread_pips = self._check_spread(pair)
        if spread_pips is not None and spread_pips > MAX_SPREAD_PIPS:
            return TradeDecision(
                False, f"Spread too wide: {spread_pips:.1f} pips > {MAX_SPREAD_PIPS:.1f}"
            )

        if not self._check_margin(pair, account_balance):
            return TradeDecision(False, "Insufficient free margin")

        self.news_filter.refresh(hours_ahead=4)
        if self.news_filter.is_news_window(pair):
            return TradeDecision(False, f"High-impact news window for {pair}")

        if pair in self.baseline_atr and self.baseline_atr[pair] > 0:
            if current_atr > self.baseline_atr[pair] * 1.25:
                return TradeDecision(
                    False,
                    f"ATR spike: {current_atr:.5f} > baseline {self.baseline_atr[pair]:.5f} x 1.25",
                )
        else:
            if current_atr > 0:
                self.baseline_atr[pair] = current_atr
                logger.debug("ATR baseline set for %s: %.5f", pair, current_atr)

        return TradeDecision(True, "OK")

    def _check_spread(self, pair: str) -> float | None:
        tick = mt5.symbol_info_tick(pair)
        if tick is None:
            return None
        spread_points = tick.spread
        info = mt5.symbol_info(pair)
        if info is None:
            return None
        point = info.point or 0.00001
        pip_size = PIP_SIZES.get(pair, 0.0001)
        spread_pips = (spread_points * point) / pip_size
        return spread_pips

    def _check_margin(self, pair: str, account_balance: float) -> bool:
        account = mt5.account_info()
        if account is None:
            return True
        free_margin = getattr(account, "margin_free", 0.0)
        if free_margin <= 0:
            return False
        info = mt5.symbol_info(pair)
        if info is None:
            return True
        min_lot = getattr(info, "volume_min", 0.01) or 0.01
        price = 0.0
        tick = mt5.symbol_info_tick(pair)
        if tick:
            price = tick.ask
        if price <= 0:
            return True
        leverage = getattr(account, "leverage", 100) or 100
        contract_size = getattr(info, "trade_contract_size", 100000) or 100000
        required_margin = (min_lot * contract_size * price) / leverage
        return free_margin >= required_margin

    def _trigger_cooldown(self, reason: str = "") -> None:
        now = datetime.now(timezone.utc)
        until = now + timedelta(hours=COOLDOWN_HOURS)
        self.in_cooldown = True
        self.cooldown_until = until
        self._persist_cooldown(until)
        logger.warning(
            "Trading cooldown triggered | reason=%s | until=%s",
            reason, until.isoformat()
        )

    def update_baseline_atr(self, pair: str, atr: float) -> None:
        if atr <= 0:
            return
        if pair not in self.baseline_atr:
            self.baseline_atr[pair] = atr
        else:
            alpha = 0.05
            self.baseline_atr[pair] = (
                alpha * atr + (1 - alpha) * self.baseline_atr[pair]
            )

    def calculate_lot(
        self,
        pair: str,
        account_balance: float,
        sl_pips: float,
        risk_percent: float | None = None,
        auto_compound: bool = False,
    ) -> float:
        from brain.config.constants import COMMISSION_PER_LOT

        if risk_percent is None:
            risk_percent = DEFAULT_RISK_PERCENT
        risk_percent = max(MIN_RISK_PERCENT, min(MAX_RISK_PERCENT, risk_percent))
        risk_frac = risk_percent / 100.0

        sl_pips = max(MIN_SL_PIPS, min(MAX_SL_PIPS, sl_pips))

        info = mt5.symbol_info(pair)
        if info is None:
            logger.warning("symbol_info(%s) returned None – using 0.01 lot", pair)
            return 0.01

        pip_size = PIP_SIZES.get(pair, 0.0001)

        tick_val: float = info.trade_tick_value
        tick_size: float = info.trade_tick_size
        if tick_size <= 0 or tick_val <= 0:
            return 0.01

        pip_value_per_lot: float = (tick_val / tick_size) * pip_size

        commission_pips_equiv = COMMISSION_PER_LOT / pip_value_per_lot if pip_value_per_lot > 0 else 0
        effective_sl_pips = sl_pips + commission_pips_equiv

        risk_amount = account_balance * risk_frac
        lots = risk_amount / (effective_sl_pips * pip_value_per_lot)

        vol_min: float = getattr(info, "volume_min", 0.01) or 0.01
        vol_max: float = getattr(info, "volume_max", 50.0) or 50.0
        vol_step: float = getattr(info, "volume_step", 0.01) or 0.01

        lots = max(vol_min, min(vol_max, round(lots / vol_step) * vol_step))
        lots = round(lots, 2)

        logger.debug(
            "Lot calc | %s | balance=%.2f | sl_pips=%.1f | comm_adj_sl=%.1f | pip_val=%.4f | lots=%.2f",
            pair, account_balance, sl_pips, effective_sl_pips, pip_value_per_lot, lots,
        )
        return lots
