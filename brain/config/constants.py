# ============================================================
# FuturesBrain v1.0 – Strategy Constants (Ground Truth)
# ALL risk rules, pip sizes, thresholds defined here.
# DO NOT change without updating the strategy spec.
# ============================================================
from __future__ import annotations

VERSION: str = "1.0.0"
APP_NAME: str = "FuturesBrain"

# ── Supported Instruments ──────────────────────────────────
# Original 3: GBPUSD, GBPJPY, USDJPY
# Added 5: EURUSD, AUDUSD, USDCAD, EURGBP, EURJPY
# Selected for: tight spreads, S/R respect, volatility for 1:3 RR
SUPPORTED_PAIRS: list[str] = [
    "GBPUSD", "GBPJPY", "USDJPY",
    "EURUSD", "AUDUSD", "USDCAD",
]

# Pip sizes: XXX/USD=4th decimal, JPY pairs=2nd decimal
PIP_SIZES: dict[str, float] = {
    "GBPUSD": 0.0001,
    "GBPJPY": 0.01,
    "USDJPY": 0.01,
    "EURUSD": 0.0001,
    "AUDUSD": 0.0001,
    "USDCAD": 0.0001,
}

# MT5 magic number identifying bot orders
MAGIC_NUMBER: int = 234_001

# ── Session Filter (stored as UTC, displayed in local TZ) ──
SESSION_START_UTC: int = 6   # inclusive  → 09:00 EAT
SESSION_END_UTC: int = 20    # exclusive  → 23:00 EAT
TIMEZONE_NAME: str = "EAT"
UTC_OFFSET_HOURS: int = 3

# ── Signal Quality Gates ───────────────────────────────────
CONFIDENCE_THRESHOLD: int = 50          # minimum confidence to trade
VALID_ALIGNMENTS: frozenset[str] = frozenset({"SAFE", "COMPLEX"})

# ── Risk Management ────────────────────────────────────────
DEFAULT_RISK_PERCENT: float = 5.0       # default 5% of balance per trade
MIN_RISK_PERCENT: float = 0.0           # minimum 0% (no trade)
MAX_RISK_PERCENT: float = 10.0          # maximum 10% per trade
RISK_PER_TRADE: float = 0.05            # derived from DEFAULT_RISK_PERCENT (kept for compat)
TARGET_RR: float = 3.0                  # risk-reward ratio 1:3
DAILY_DRAWDOWN_LIMIT: float = 0.05      # 5 % daily drawdown guard
MAX_DAILY_TRADES: int = 5               # default hard cap (overridable by user settings)
COOLDOWN_HOURS: int = 24                # cooldown after 3 losses or DD breach

# Minimum SL in pips to avoid degenerate lot sizing
MIN_SL_PIPS: float = 5.0
MAX_SL_PIPS: float = 300.0

# ── Trailing Stop ──────────────────────────────────────────
TRAILING_TRIGGER_PIPS: float = 10.0    # profit pips to arm trailing stop
TRAILING_ATR_MULT: float = 0.5         # trail distance = ATR × 0.5

# ── Volatility / News ──────────────────────────────────────
ATR_PERIOD: int = 14
ATR_SPIKE_MULTIPLIER: float = 1.25     # current ATR > baseline × 1.25 → skip
NEWS_WINDOW_MINUTES: int = 15          # ±15 min around high-impact event

# MT5 calendar importance level (3 = High)
NEWS_IMPORTANCE_HIGH: int = 3

# Country → currency mapping for news filter
COUNTRY_CURRENCY_MAP: dict[str, str] = {
    "US": "USD", "GB": "GBP", "EU": "EUR",
    "JP": "JPY", "CA": "CAD", "AU": "AUD",
    "NZ": "NZD", "CH": "CHF",
}

# ── Ignore Periods after Level FLIP ───────────────────────
# Values = number of candles to ignore after a flip event
IGNORE_PERIODS: dict[str, int] = {
    "1m": 5,  "3m": 5,  "5m": 5,
    "15m": 3, "30m": 3, "1H": 3, "4H": 3,
    "1D": 2,  "1W": 1,  "1M": 1,
}

# ── Timeframe Map (string key → MT5 constant name) ────────
# Resolved against live mt5 module in data/feed.py
TF_STRINGS: list[str] = [
    "1m", "3m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"
]

# ── Execution Safeguards ───────────────────────────────────
MAX_SPREAD_PIPS: float = 3.0          # reject trade if spread > this
MAX_SLIPPAGE_PIPS: float = 3.0        # allowed slippage in pips
POST_NEWS_COOLDOWN_MINUTES: int = 30  # cool down after news event passes
COMMISSION_PER_LOT: float = 7.0       # typical round-turn commission (USD)
ESTIMATED_SWAP_PER_NIGHT: float = 0.5 # estimated swap cost in pips equivalent

# ── SELL Trade Toggle ──────────────────────────────────────
ENABLE_SELL_TRADES: bool = False      # set False to disable SELL signals

# ── FastAPI ────────────────────────────────────────────────
API_HOST: str = "0.0.0.0"
API_PORT: int = 8000

# ── SQLite paths (news cache only) ─────────────────────────
SQLITE_NEWS_DB: str = "db/news_cache.db"
