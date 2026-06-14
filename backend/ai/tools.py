from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_account_summary",
        "description": "Get the user's account balance, equity, margin, trades remaining, daily usage, and bot status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "get_open_positions",
        "description": "Get all currently open positions with ticket, symbol, direction, entry price, current P&L, SL, TP.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "get_recent_trades",
        "description": "Get the most recent closed trades. Returns last N trades with symbol, direction, P&L, open/close times.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent trades to fetch (max 20).",
                    "default": 5,
                }
            },
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "get_market_summary",
        "description": "Get the current market summary for a traded pair (GBPUSD, GBPJPY, USDJPY). Returns price, nearest support/resistance, short-term bias, rejection candles, ATR.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "The trading pair symbol.",
                    "enum": ["GBPUSD", "GBPJPY", "USDJPY"],
                }
            },
            "additionalProperties": False,
            "required": ["symbol"],
        },
    },
    {
        "name": "explain_last_trade",
        "description": "Get the reason/analysis for the most recent trade execution from the trading brain.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "generate_chart",
        "description": "Generate a candlestick chart image with support/resistance levels and rejection markers.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "The trading pair symbol.",
                    "enum": ["GBPUSD", "GBPJPY", "USDJPY"],
                },
                "timeframe": {
                    "type": "string",
                    "description": "Chart timeframe (1m, 5m, 15m, 1H). Default 15m.",
                    "default": "15m",
                },
            },
            "additionalProperties": False,
            "required": ["symbol"],
        },
    },
    {
        "name": "get_news_status",
        "description": "Get current news/volatility status and whether trading is paused due to high-impact events.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "get_bot_health",
        "description": "Get the overall bot health status: MT5 connection, running state, cooldown, news pause.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "get_daily_pnl",
        "description": "Get today's profit and loss.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "get_trading_strategy",
        "description": "Explain the trading strategy used by the bot (pure price action, 8-sector analysis, multi-timeframe).",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "start_trading",
        "description": "Start the bot's autonomous trading engine. The brain runs the full 8-sector pipeline and handles all trade decisions (entry, SL, TP) automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "trade_count": {
                    "type": "integer",
                    "description": "Number of trades to execute this session (1-10). If not set, defaults to 1.",
                    "minimum": 1,
                    "maximum": 10,
                },
                "mode": {
                    "type": "string",
                    "description": "Trading mode (short for single trades, long for multiple concurrent trades).",
                    "enum": ["short", "long"],
                },
                "risk_percent": {
                    "type": "number",
                    "description": "Risk percentage per trade (1-10).",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "stop_trading",
        "description": "Stop/pause the bot's autonomous trading engine. The brain stops analysing and placing new trades.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
    {
        "name": "set_risk_percent",
        "description": "Set the risk percentage per trade (1-10%). Affects how the brain sizes lots.",
        "parameters": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": "Risk percentage per trade (1-10).",
                    "minimum": 1,
                    "maximum": 10,
                }
            },
            "additionalProperties": False,
            "required": ["value"],
        },
    },
    {
        "name": "set_daily_limit",
        "description": "Set the maximum number of trades per day (1-5) for the brain.",
        "parameters": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "integer",
                    "description": "Daily trade limit (1-5).",
                    "minimum": 1,
                    "maximum": 5,
                }
            },
            "additionalProperties": False,
            "required": ["value"],
        },
    },
    {
        "name": "set_mode",
        "description": "Switch between short-term and long-term trading mode for the brain.",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Trading mode.",
                    "enum": ["short", "long"],
                }
            },
            "additionalProperties": False,
            "required": ["mode"],
        },
    },
    {
        "name": "toggle_auto_compounding",
        "description": "Enable or disable auto-compounding of trading profits.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
            "required": [],
        },
    },
]

INFO_TOOL_NAMES: frozenset[str] = frozenset({
    "get_account_summary", "get_open_positions", "get_recent_trades",
    "get_market_summary", "explain_last_trade", "generate_chart",
    "get_news_status", "get_bot_health", "get_daily_pnl", "get_trading_strategy",
})

ACTION_TOOL_NAMES: frozenset[str] = frozenset({
    "start_trading", "stop_trading", "set_risk_percent",
    "set_daily_limit", "set_mode", "toggle_auto_compounding",
})
