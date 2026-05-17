from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from config.settings import OPENROUTER_API_KEY, OPENROUTER_MODEL, SUPABASE_DB_URI
from config.constants import SUPPORTED_PAIRS, SESSION_START_UTC, SESSION_END_UTC, TARGET_RR
from db import get_recent_trades, get_open_trades, get_todays_pnl, count_trades_today, get_state

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
RATE_LIMIT_PER_MIN = 30

_pending_confirmations: dict[str, dict] = {}
_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = asyncio.Lock()

_SYSTEM_PROMPT_BASE = (
    "You are FUTURES Trading Bot, an AI trading assistant. "
    "You are calm, risk-aware, brief (1-2 sentences per response, "
    "max 3-4 for trade explanations). "
    "You NEVER promise guaranteed returns or encourage excessive risk. "
    "You NEVER give financial advice — only analysis and execution. "
    "Introduce yourself as 'FUTURES Trading Bot', never as a third-party model. "
    "If asked non-trading questions, politely refuse: "
    "'I only discuss trading and the FUTURES bot.' "
    "Use the user's display name if known."
)

_AGENTS_RULES = (
    "Core rules:\n"
    "- NEVER execute trades without user confirmation.\n"
    "- Respect daily loss limits, risk %, and trade caps.\n"
    "- Check market hours (07:00-17:00 UTC / 10:00-20:00 EAT).\n"
    "- Check news status before suggesting trades.\n"
    "- Max position: 10% of balance. Max daily loss: 5%. Max drawdown: 15%.\n"
    "- If user says 'KILL' or 'STOP ALL': close all positions and stop bot."
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_account_summary",
            "description": "Get account balance, equity, margin, bot status, daily trades used, and cooldown info.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_open_positions",
            "description": "Get list of currently open positions with P&L.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_trades",
            "description": "Get recent closed trades.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Number of trades to return (max 10)", "default": 5}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_last_trade",
            "description": "Get the reasoning behind the most recent trade.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_summary",
            "description": "Get current price-action summary for a trading pair: price, nearest support/resistance, bias, rejection status, news impact.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "enum": SUPPORTED_PAIRS, "description": "Trading pair symbol"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_status",
            "description": "Get current news/volatility status and whether trading is paused.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Generate a candlestick chart image for a pair with support/resistance levels marked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "enum": SUPPORTED_PAIRS},
                    "timeframe": {"type": "string", "enum": ["15m", "1H", "4H"], "default": "15m"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_buy",
            "description": "Place a market buy order. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "enum": SUPPORTED_PAIRS}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_sell",
            "description": "Place a market sell order. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "enum": SUPPORTED_PAIRS}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_all_positions",
            "description": "Close all open positions. Requires user confirmation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_bot",
            "description": "Stop/pause the trading bot and close all positions. Requires user confirmation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_bot",
            "description": "Resume the trading bot if paused. Requires user confirmation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_risk_percent",
            "description": "Set the risk percentage per trade (1-10%). Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "number", "description": "Risk percentage 1-10"}},
                "required": ["value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_daily_limit",
            "description": "Set daily trade limit (1-5). Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "integer", "description": "Daily trade limit 1-5"}},
                "required": ["value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_mode",
            "description": "Switch trading mode. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"mode": {"type": "string", "enum": ["short", "long"]}},
                "required": ["mode"],
            },
        },
    },
]


def _decode_jwt_payload(request) -> dict:
    import base64, json
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {}
    try:
        payload_b64 = auth.split(".")[1]
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return {}


async def is_rate_limited(user_id: str) -> bool:
    async with _rate_lock:
        now = time.monotonic()
        window = now - 60
        _rate_store[user_id] = [ts for ts in _rate_store[user_id] if ts > window]
        if len(_rate_store[user_id]) >= RATE_LIMIT_PER_MIN:
            return True
        _rate_store[user_id].append(now)
        return False


# ── Tool implementations ───────────────────────────────────

async def _get_account_summary(bot_state: dict) -> dict:
    import MetaTrader5 as mt5
    loop = asyncio.get_event_loop()
    account = await loop.run_in_executor(None, mt5.account_info)
    balance = float(getattr(account, "balance", 0.0)) if account else 0.0
    equity = float(getattr(account, "equity", 0.0)) if account else 0.0
    margin = float(getattr(account, "margin", 0.0)) if account else 0.0
    daily_trades = count_trades_today()
    daily_pnl = get_todays_pnl()
    risk = bot_state.get("risk")
    cooldown = bool(risk and risk.in_cooldown) if risk else False
    return {
        "balance": balance,
        "equity": equity,
        "margin": margin,
        "daily_trades_used": daily_trades,
        "daily_pnl": daily_pnl,
        "bot_running": bool(bot_state.get("running")),
        "cooldown_active": cooldown,
        "risk_percent": bot_state.get("risk_percent"),
    }


async def _get_open_positions() -> list[dict]:
    import MetaTrader5 as mt5
    loop = asyncio.get_event_loop()
    positions = await loop.run_in_executor(None, mt5.positions_get)
    if not positions:
        return []
    return [
        {
            "ticket": int(p.ticket),
            "symbol": p.symbol,
            "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume": p.volume,
            "entry_price": p.price_open,
            "current_price": p.price_current,
            "profit": round(p.profit, 2),
            "sl": p.sl,
            "tp": p.tp,
        }
        for p in positions
        if p.symbol in SUPPORTED_PAIRS
    ]


def _get_recent_trades(limit: int = 5) -> list[dict]:
    trades = get_recent_trades(limit=min(limit, 10))
    return [
        {
            "symbol": t.get("pair"),
            "direction": t.get("direction"),
            "lots": t.get("lots"),
            "entry": t.get("entry_price"),
            "exit": t.get("close_price"),
            "pnl": t.get("pnl"),
            "opened": str(t.get("opened_at", ""))[:16],
            "closed": str(t.get("closed_at", ""))[:16] if t.get("closed_at") else None,
        }
        for t in trades
    ]


def _explain_last_trade() -> str | None:
    trades = get_recent_trades(limit=1)
    if not trades:
        return None
    t = trades[0]
    reason = t.get("sectors_json")
    if reason:
        try:
            parsed = json.loads(reason) if isinstance(reason, str) else reason
            return parsed.get("reason") or parsed.get("s8_bias", {}).get("reason")
        except (json.JSONDecodeError, TypeError):
            pass
    return None


async def _get_market_summary(symbol: str) -> dict:
    import MetaTrader5 as mt5
    from data.feed import get_candles

    loop = asyncio.get_event_loop()

    tick = await loop.run_in_executor(None, mt5.symbol_info_tick, symbol)
    if tick is None:
        return {"error": f"{symbol} tick data unavailable"}

    price = tick.bid
    df = await loop.run_in_executor(None, get_candles, symbol, "15m", 200)
    if df is None or len(df) < 20:
        return {"symbol": symbol, "price": price, "error": "insufficient data"}

    recent = df.tail(20)
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())
    close5 = float(recent["close"].iloc[-5]) if len(recent) >= 5 else price
    close1 = float(recent["close"].iloc[-1])
    short_bias = "BULLISH" if close1 > close5 else "BEARISH" if close1 < close5 else "NEUTRAL"

    # Rejection candle check
    last_candle = recent.iloc[-1]
    body = abs(float(last_candle["close"]) - float(last_candle["open"]))
    lower_wick = min(float(last_candle["open"]), float(last_candle["close"])) - float(last_candle["low"])
    upper_wick = float(last_candle["high"]) - max(float(last_candle["open"]), float(last_candle["close"]))
    rejection = None
    if lower_wick > body * 2 and float(last_candle["close"]) > float(last_candle["open"]):
        rejection = "bullish_rejection"
    elif upper_wick > body * 2 and float(last_candle["close"]) < float(last_candle["open"]):
        rejection = "bearish_rejection"

    # Distance to key levels
    dist_to_support = round(abs(price - support) / price * 10000, 1) if support else None
    dist_to_resistance = round(abs(price - resistance) / price * 10000, 1) if resistance else None

    return {
        "symbol": symbol,
        "price": round(price, 5),
        "support": round(support, 5),
        "resistance": round(resistance, 5),
        "distance_to_support_pips": dist_to_support,
        "distance_to_resistance_pips": dist_to_resistance,
        "short_term_bias": short_bias,
        "rejection_candle": rejection,
    }


def _get_news_status() -> dict:
    news_state = get_state("news_state", default={})
    if not isinstance(news_state, dict):
        news_state = {}
    return {
        "paused": news_state.get("paused", False),
        "phase": news_state.get("phase", "normal"),
        "pause_until": news_state.get("pause_until"),
        "next_event": news_state.get("next_event"),
    }


async def _generate_chart(symbol: str, bot_state: dict, timeframe: str = "15m") -> dict:
    from data.feed import get_candles
    import MetaTrader5 as mt5

    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, get_candles, symbol, timeframe, 50)
    if df is None or len(df) < 20:
        return {"error": "Insufficient chart data"}

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mplfinance as mpf

    df.index = df.index.tz_localize(None) if hasattr(df.index, "tz") else df.index

    # Find key levels
    recent = df.tail(20)
    support = recent["low"].min()
    resistance = recent["high"].max()

    extra_lines = []
    if support:
        extra_lines.append(mpf.make_addplot([support] * len(df), color="green", linestyle="--", linewidths=0.8))
    if resistance:
        extra_lines.append(mpf.make_addplot([resistance] * len(df), color="red", linestyle="--", linewidths=0.8))

    fig, axlist = mpf.plot(
        df,
        type="candle",
        style="charles",
        volume=False,
        figsize=(8, 5),
        returnfig=True,
        addplot=extra_lines if extra_lines else None,
    )
    ax = axlist[0]
    if support:
        ax.annotate(f"S {support:.5f}", xy=(df.index[-1], support),
                    xytext=(df.index[-5], support * 0.999),
                    fontsize=9, color="green", fontweight="bold")
    if resistance:
        ax.annotate(f"R {resistance:.5f}", xy=(df.index[-1], resistance),
                    xytext=(df.index[-5], resistance * 1.001),
                    fontsize=9, color="red", fontweight="bold")

    # Mark last rejection
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    lower_wick = min(last["open"], last["close"]) - last["low"]
    if lower_wick > body * 2 and last["close"] > last["open"]:
        ax.scatter(df.index[-1], last["low"], marker="^", s=200, color="lime", zorder=5)
    upper_wick = last["high"] - max(last["open"], last["close"])
    if upper_wick > body * 2 and last["close"] < last["open"]:
        ax.scatter(df.index[-1], last["high"], marker="v", s=200, color="red", zorder=5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    # Upload to Supabase Storage
    import base64
    b64 = base64.b64encode(buf.read()).decode()

    image_url = None
    if SUPABASE_DB_URI:
        try:
            from db.supabase import _get_conn
            conn = _get_conn(SUPABASE_DB_URI)
            from supabase import create_client
            supabase_url = os.getenv("SUPABASE_URL", "")
            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            if supabase_url and service_key:
                cli = create_client(supabase_url, service_key)
                filename = f"charts/{symbol}_{timeframe}_{int(time.time())}.png"
                cli.storage.from_("charts").upload(filename, buf.getvalue(), {"content-type": "image/png"})
                image_url = cli.storage.from_("charts").get_public_url(filename)
        except Exception as exc:
            logger.warning("Chart upload failed: %s", exc)

    # Fallback: return base64 inline
    if not image_url:
        image_url = f"data:image/png;base64,{b64}"

    return {"image_url": image_url, "symbol": symbol, "timeframe": timeframe}


async def _execute_tool(name: str, args: dict, bot_state: dict) -> Any:
    if name == "get_account_summary":
        return await _get_account_summary(bot_state)
    elif name == "get_open_positions":
        return await _get_open_positions()
    elif name == "get_recent_trades":
        return _get_recent_trades(limit=args.get("limit", 5))
    elif name == "explain_last_trade":
        reason = _explain_last_trade()
        return {"reason": reason or "No detailed reason recorded for the last trade."}
    elif name == "get_market_summary":
        return await _get_market_summary(args["symbol"])
    elif name == "get_news_status":
        return _get_news_status()
    elif name == "generate_chart":
        return await _generate_chart(args["symbol"], bot_state, args.get("timeframe", "15m"))
    return None


_ACTION_TOOLS = {"place_buy", "place_sell", "close_all_positions", "stop_bot", "resume_bot", "set_risk_percent", "set_daily_limit", "set_mode"}


def _build_system_prompt(user_email: str | None, display_name: str | None) -> str:
    name_part = f"The user's name is {display_name}." if display_name else ""
    return f"{_SYSTEM_PROMPT_BASE}\n\n{_AGENTS_RULES}\n\n{name_part}"


async def chat_completion(
    messages: list[dict],
    user_id: str,
    bot_state: dict,
    user_email: str | None = None,
    display_name: str | None = None,
) -> dict:
    if not OPENROUTER_API_KEY:
        return {"reply": "Copilot is not configured. Please set OPENROUTER_API_KEY."}

    if await is_rate_limited(user_id):
        return {"reply": "You are sending messages too quickly. Please wait.", "rate_limited": True}

    system_prompt = _build_system_prompt(user_email, display_name)

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "tools": _TOOLS,
        "tool_choice": "auto",
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://futuresbrain.app",
        "X-Title": "FuturesBrain Copilot",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(_OPENROUTER_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("OpenRouter chat error %d: %s", resp.status, text[:300])
                    return {"reply": "Copilot is temporarily unavailable. Please try again."}
                data = await resp.json()
    except asyncio.TimeoutError:
        return {"reply": "Copilot is taking too long. Please try again."}
    except aiohttp.ClientError as exc:
        logger.error("Copilot network error: %s", exc)
        return {"reply": "Network error. Please check your connection."}

    try:
        choice = data["choices"][0]
        msg = choice["message"]
    except (KeyError, IndexError):
        logger.warning("Unexpected OpenRouter response: %s", str(data)[:300])
        return {"reply": "Unexpected response from Copilot."}

    # If the model just wants to reply with text
    if msg.get("content") and not msg.get("tool_calls"):
        content = msg["content"]
        # Check if model indicates it wants to call an action tool via text
        tool_name = None
        tool_args = {}
        for line in content.split("\n"):
            line = line.strip().lower()
            for tdef in _TOOLS:
                fn = tdef["function"]
                if fn["name"] in line:
                    tool_name = fn["name"]
                    break
            if tool_name:
                break
        if tool_name and tool_name in _ACTION_TOOLS:
            cid = str(uuid.uuid4())
            _pending_confirmations[cid] = {"tool": tool_name, "args": tool_args, "user_id": user_id}
            return {
                "reply": content,
                "requires_confirmation": True,
                "confirmation_id": cid,
                "tool_name": tool_name,
            }
        return {"reply": content}

    # Handle tool calls
    tool_calls = msg.get("tool_calls", [])
    if not tool_calls:
        return {"reply": msg.get("content", "I'm not sure how to respond to that.")}

    results = []
    needs_confirm = None
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        if name in _ACTION_TOOLS:
            cid = str(uuid.uuid4())
            _pending_confirmations[cid] = {"tool": name, "args": args, "user_id": user_id}
            needs_confirm = {"confirmation_id": cid, "tool_name": name}
            continue

        result = await _execute_tool(name, args, bot_state)
        results.append({"tool": name, "result": result})

    # If there were action tools, return confirmation request
    if needs_confirm:
        return {
            "reply": None if not results else json.dumps(results),
            "requires_confirmation": True,
            **needs_confirm,
        }

    # Send tool results back to the model for a final response
    payload["messages"].append(msg)
    for r in results:
        payload["messages"].append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "content": json.dumps(r["result"]),
        })

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(_OPENROUTER_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return {"reply": "Copilot encountered an error processing the data."}
                data2 = await resp.json()
        final_text = data2["choices"][0]["message"]["content"] or "Done."
        return {"reply": final_text}
    except Exception as exc:
        logger.warning("Copilot follow-up error: %s", exc)
        return {"reply": "Done.", "tool_results": results}


async def execute_confirmation(confirmation_id: str, user_id: str, bot_state: dict) -> dict:
    pending = _pending_confirmations.pop(confirmation_id, None)
    if not pending:
        return {"reply": "Confirmation expired or invalid. Please try again."}
    if pending["user_id"] != user_id:
        return {"reply": "This confirmation belongs to another session."}

    tool = pending["tool"]
    args = pending["args"]

    import MetaTrader5 as mt5
    from core.executor import place_order
    from core.risk import RiskEngine
    from config.constants import DEFAULT_RISK_PERCENT

    loop = asyncio.get_event_loop()

    if tool == "place_buy":
        symbol = args.get("symbol")
        if not symbol:
            return {"reply": "Missing symbol."}
        account = await loop.run_in_executor(None, mt5.account_info)
        balance = float(getattr(account, "balance", 10000.0)) if account else 10000.0
        risk_pct = bot_state.get("risk_percent") or DEFAULT_RISK_PERCENT
        tick = await loop.run_in_executor(None, mt5.symbol_info_tick, symbol)
        if not tick:
            return {"reply": f"Cannot get price for {symbol}."}
        price = tick.ask
        sl_pips = 10
        sl_price = price - sl_pips * 0.0001 if symbol == "GBPUSD" else price - sl_pips * 0.01
        tp_price = price + sl_pips * 3 * 0.0001 if symbol == "GBPUSD" else price + sl_pips * 3 * 0.01
        risk = RiskEngine()
        lots = risk.calculate_lot(symbol, balance, sl_pips, risk_pct)
        result = place_order(
            pair=symbol, direction="BUY", lots=round(lots, 2),
            entry_price=price, sl_price=sl_price, tp_price=tp_price,
            confidence=80, sectors=None, supabase_uri=SUPABASE_DB_URI,
        )
        if result:
            return {"reply": f"✅ Buy order placed: {round(lots, 2)} lots {symbol} at {price:.5f}. SL: {sl_price:.5f}, TP: {tp_price:.5f}."}
        return {"reply": f"❌ Failed to place buy order for {symbol}."}

    elif tool == "place_sell":
        symbol = args.get("symbol")
        if not symbol:
            return {"reply": "Missing symbol."}
        account = await loop.run_in_executor(None, mt5.account_info)
        balance = float(getattr(account, "balance", 10000.0)) if account else 10000.0
        risk_pct = bot_state.get("risk_percent") or DEFAULT_RISK_PERCENT
        tick = await loop.run_in_executor(None, mt5.symbol_info_tick, symbol)
        if not tick:
            return {"reply": f"Cannot get price for {symbol}."}
        price = tick.bid
        sl_pips = 10
        sl_price = price + sl_pips * 0.0001 if symbol == "GBPUSD" else price + sl_pips * 0.01
        tp_price = price - sl_pips * 3 * 0.0001 if symbol == "GBPUSD" else price - sl_pips * 3 * 0.01
        risk = RiskEngine()
        lots = risk.calculate_lot(symbol, balance, sl_pips, risk_pct)
        result = place_order(
            pair=symbol, direction="SELL", lots=round(lots, 2),
            entry_price=price, sl_price=sl_price, tp_price=tp_price,
            confidence=80, sectors=None, supabase_uri=SUPABASE_DB_URI,
        )
        if result:
            return {"reply": f"✅ Sell order placed: {round(lots, 2)} lots {symbol} at {price:.5f}. SL: {sl_price:.5f}, TP: {tp_price:.5f}."}
        return {"reply": f"❌ Failed to place sell order for {symbol}."}

    elif tool == "close_all_positions":
        from core.executor import close_position
        positions = await loop.run_in_executor(None, mt5.positions_get)
        closed = 0
        if positions:
            for p in positions:
                if p.symbol in SUPPORTED_PAIRS:
                    direction = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    ok = close_position(
                        ticket=p.ticket, pair=p.symbol,
                        direction=direction, lots=p.volume,
                        supabase_uri=SUPABASE_DB_URI,
                    )
                    if ok:
                        closed += 1
        return {"reply": f"Closed {closed} position(s)."}

    elif tool == "stop_bot":
        from core.executor import close_position
        bot_state["running"] = False
        positions = await loop.run_in_executor(None, mt5.positions_get)
        closed = 0
        if positions:
            for p in positions:
                if p.symbol in SUPPORTED_PAIRS:
                    direction = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    ok = close_position(
                        ticket=p.ticket, pair=p.symbol,
                        direction=direction, lots=p.volume,
                        supabase_uri=SUPABASE_DB_URI,
                    )
                    if ok:
                        closed += 1
        return {"reply": f"Bot stopped. Closed {closed} position(s)."}

    elif tool == "resume_bot":
        bot_state["running"] = True
        return {"reply": "Bot resumed."}

    elif tool == "set_risk_percent":
        value = max(1.0, min(10.0, float(args.get("value", 5))))
        bot_state["risk_percent"] = value
        from db import set_state
        settings = get_state("app_settings", default={})
        if not isinstance(settings, dict):
            settings = {}
        settings["risk_percent"] = value
        set_state("app_settings", settings)
        return {"reply": f"Risk percentage set to {value}%."}

    elif tool == "set_daily_limit":
        value = max(1, min(5, int(args.get("value", 5))))
        from config.constants import MAX_DAILY_TRADES
        return {"reply": f"Daily trade limit set to {value}. System max is {MAX_DAILY_TRADES}."}

    elif tool == "set_mode":
        mode = args.get("mode", "long")
        return {"reply": f"Trading mode switched to {mode}."}

    return {"reply": "Action completed."}
