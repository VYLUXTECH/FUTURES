from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

import aiohttp
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

from brain.config.settings import AI_BASE_URL, AI_MODEL
from brain.db.postgres import (
    get_open_trades,
    get_recent_trades,
    get_todays_pnl,
    count_trades_today,
)

from backend.ai.market_summary import MarketSummaryEngine
from backend.ai.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)

RATE_LIMIT_PER_MIN = 30
CONFIRMATION_TIMEOUT = 120


class CopilotEngine:
    """
    AI Copilot — control interface for the autonomous trading brain.
    - DeepSeek via custom AI endpoint
    - Starts/stops the brain's trading loop
    - Answers market questions using pre-computed summaries
    - Does NOT execute individual trades (the brain's pipeline handles all entries/SL/TP)
    """

    def __init__(
        self,
        market_summary: MarketSummaryEngine,
        chart_generator: ChartGenerator,
    ) -> None:
        self.market_summary = market_summary
        self.chart_generator = chart_generator
        self._bot_state: dict = {}
        self._user_profile: dict = {}

        self._rate_store: dict[str, list[float]] = defaultdict(list)
        self._rate_lock = asyncio.Lock()

        self._pending_confirmations: dict[str, dict] = {}
        self._conf_lock = asyncio.Lock()

        self._conversations: dict[str, list[dict]] = defaultdict(list)
        self._conv_lock = asyncio.Lock()

    def set_bot_state(self, state: dict) -> None:
        self._bot_state = state

    def set_user_profile(self, profile: dict) -> None:
        self._user_profile = profile

    # ── System Prompt ──────────────────────────────────────

    def _build_system_prompt(self, user_id: str = "") -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        summaries = self.market_summary.get_all_summaries()
        market_text = ""
        for pair, s in summaries.items():
            rejection = f", rejection: {s['rejection']}" if s.get("rejection") else ""
            market_text += (
                f"- {pair}: ${s['price']}, bias {s['bias']}, "
                f"support ${s['support']}, resistance ${s['resistance']}"
                f"{rejection}\n"
            )

        return f"""You are FUTURES, an AI trading assistant. You are calm, risk-aware, and brief (1-2 sentences). You NEVER promise returns or encourage excessive risk. You NEVER give financial advice — only analysis. Introduce yourself as 'FUTURES'. If asked non-trading questions, politely refuse. Use the user's name if known.

DATE: {now} UTC

CURRENT MARKET CONDITIONS:
{market_text or "Market data not yet available."}

RESPOND naturally and conversationally. Do NOT output JSON or code."""

    # ── Rate Limiting ──────────────────────────────────────

    async def _check_rate_limit(self, user_id: str) -> bool:
        async with self._rate_lock:
            now = time.monotonic()
            window_start = now - 60
            self._rate_store[user_id] = [t for t in self._rate_store[user_id] if t > window_start]
            if len(self._rate_store[user_id]) >= RATE_LIMIT_PER_MIN:
                return True
            self._rate_store[user_id].append(now)
            return False

    # ── Tool Handlers ──────────────────────────────────────

    async def _handle_tool(self, tool_name: str, args: dict) -> Any:
        handlers: dict[str, Callable] = {
            "get_account_summary": self._tool_account_summary,
            "get_open_positions": self._tool_open_positions,
            "get_recent_trades": self._tool_recent_trades,
            "get_market_summary": self._tool_market_summary,
            "explain_last_trade": self._tool_explain_last_trade,
            "generate_chart": self._tool_generate_chart,
            "get_news_status": self._tool_news_status,
            "get_bot_health": self._tool_bot_health,
            "get_daily_pnl": self._tool_daily_pnl,
            "get_trading_strategy": self._tool_trading_strategy,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = await handler(args)
            return result
        except Exception as exc:
            logger.error("Tool %s error: %s", tool_name, exc)
            return {"error": str(exc)}

    async def _tool_account_summary(self, _args: dict) -> dict:
        if not MT5_AVAILABLE:
            return {"error": "MT5 not available"}
        loop = asyncio.get_event_loop()
        account = await loop.run_in_executor(None, mt5.account_info)
        balance = getattr(account, "balance", 0.0) if account else 0.0
        equity = getattr(account, "equity", 0.0) if account else 0.0
        margin = getattr(account, "margin", 0.0) if account else 0.0
        trades_today = count_trades_today()
        risk_pct = self._bot_state.get("risk_percent", 5.0)
        return {
            "balance": round(balance, 2),
            "equity": round(equity, 2),
            "margin": round(margin, 2),
            "trades_remaining": 5 - trades_today,
            "daily_used": trades_today,
            "daily_limit": self._bot_state.get("daily_limit", 5),
            "bot_active": self._bot_state.get("running", False),
            "risk_percent": risk_pct,
        }

    async def _tool_open_positions(self, _args: dict) -> list:
        if not MT5_AVAILABLE:
            return []
        positions = await asyncio.get_event_loop().run_in_executor(None, mt5.positions_get)
        if not positions:
            return []
        result = []
        for p in positions:
            result.append({
                "ticket": int(p.ticket),
                "symbol": p.symbol,
                "direction": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "entry": p.price_open,
                "current_price": p.price_current,
                "profit": round(p.profit, 2),
                "sl": p.sl,
                "tp": p.tp,
            })
        return result

    async def _tool_recent_trades(self, args: dict) -> list:
        limit = min(args.get("limit", 5), 20)
        trades = get_recent_trades(limit=limit)
        return [
            {
                "symbol": t.get("pair", ""),
                "direction": t.get("direction", ""),
                "pnl": round(t.get("pnl", 0), 2),
                "entry": t.get("entry_price", 0),
                "close": t.get("close_price", 0),
                "opened_at": t.get("opened_at", ""),
                "closed_at": t.get("closed_at", ""),
            }
            for t in trades
        ]

    async def _tool_market_summary(self, args: dict) -> dict:
        symbol = args.get("symbol", "").upper()
        summary = self.market_summary.get_summary(symbol)
        if not summary:
            return {"error": f"No market data for {symbol}"}
        return summary

    async def _tool_explain_last_trade(self, _args: dict) -> dict:
        trades = get_recent_trades(limit=1)
        if not trades:
            return {"message": "No trades have been executed yet."}
        t = trades[0]
        sectors_raw = t.get("sectors_json")
        reason = "No detailed reason recorded."
        if sectors_raw:
            try:
                parsed = json.loads(sectors_raw) if isinstance(sectors_raw, str) else sectors_raw
                reason = parsed.get("s8_bias", {}).get("reason") or json.dumps(parsed, indent=2)[:500]
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "pair": t.get("pair", ""),
            "direction": t.get("direction", ""),
            "entry": t.get("entry_price", 0),
            "pnl": round(t.get("pnl", 0), 2),
            "reason": reason,
        }

    async def _tool_generate_chart(self, args: dict) -> dict:
        symbol = args.get("symbol", "").upper()
        tf = args.get("timeframe", "15m")
        path = await asyncio.get_event_loop().run_in_executor(
            None, self.chart_generator.generate, symbol, tf, 50
        )
        if path:
            return {"image_path": path, "message": f"Chart generated for {symbol} ({tf})."}
        return {"error": "Failed to generate chart. Ensure mplfinance is installed."}

    async def _tool_news_status(self, _args: dict) -> dict:
        try:
            paused_pairs = []
            for pair in SUPPORTED_PAIRS:
                pass
            return {
                "news_paused": False,
                "status": "No news impact",
            }
        except Exception as exc:
            return {"news_paused": False, "status": f"News check unavailable: {exc}"}

    async def _tool_bot_health(self, _args: dict) -> dict:
        if not MT5_AVAILABLE:
            return {"mt5_connected": False, "bot_running": False, "cooldown_active": False, "healthy": False}
        loop = asyncio.get_event_loop()
        terminal = await loop.run_in_executor(None, mt5.terminal_info)
        connected = terminal is not None and bool(terminal.connected)
        risk = self._bot_state.get("risk")
        cooldown_active = bool(risk and getattr(risk, "in_cooldown", False)) if risk else False
        return {
            "mt5_connected": connected,
            "bot_running": self._bot_state.get("running", False),
            "cooldown_active": cooldown_active,
            "healthy": connected and self._bot_state.get("running", False) and not cooldown_active,
        }

    async def _tool_daily_pnl(self, _args: dict) -> dict:
        pnl = get_todays_pnl()
        return {"pnl": round(pnl, 2)}

    async def _tool_trading_strategy(self, _args: dict) -> dict:
        return {
            "strategy": "Pure price action – no indicators",
            "sectors": [
                "Candle pattern analysis",
                "Market structure (BOS/CHoCH)",
                "Key support/resistance levels",
                "Rejection candles at levels",
                "Imbalances / Fair Value Gaps",
                "Higher timeframe structure (4H)",
                "Multi-timeframe correlation (15m/1H)",
                "Bias synthesizer with confidence scoring",
            ],
            "risk_reward": "Fixed 1:3 R:R ratio",
            "pairs": ["GBPUSD", "GBPJPY", "USDJPY"],
            "session": "10:00-20:00 EAT",
        }

    # ── Confirmation Flow ──────────────────────────────────

    async def request_confirmation(self, user_id: str, action: dict) -> str:
        conf_id = f"conf_{user_id}_{int(time.time())}"
        async with self._conf_lock:
            self._pending_confirmations[conf_id] = {
                "user_id": user_id,
                "action": action,
                "expires_at": time.monotonic() + CONFIRMATION_TIMEOUT,
            }
        return conf_id

    async def confirm_action(self, conf_id: str, user_id: str) -> dict:
        async with self._conf_lock:
            entry = self._pending_confirmations.pop(conf_id, None)
            if not entry:
                return {"reply": "Confirmation expired or invalid. Please try again."}
            if entry["user_id"] != user_id:
                return {"reply": "This confirmation belongs to another session."}
            if time.monotonic() > entry["expires_at"]:
                return {"reply": "Confirmation timed out. Please try again."}
            action = entry["action"]
        return await self._execute_action(action, user_id)

    async def _execute_action(self, action: dict, user_id: str) -> dict:
        action_type = action.get("tool")
        args = action.get("args", {})
        if action_type == "start_trading":
            return await self._execute_start_trading(args, user_id)
        elif action_type == "stop_trading":
            return await self._execute_stop_trading(args, user_id)
        elif action_type == "set_risk_percent":
            return await self._execute_set_risk(args, user_id)
        elif action_type == "set_mode":
            return await self._execute_set_mode(args, user_id)
        elif action_type == "set_daily_limit":
            return await self._execute_set_daily_limit(args, user_id)
        elif action_type == "toggle_auto_compounding":
            return await self._execute_toggle_compound(args, user_id)
        return {"reply": f"Unknown action: {action_type}"}

    async def _execute_start_trading(self, _args: dict, _user_id: str) -> dict:
        risk = self._bot_state.get("risk")
        if risk and getattr(risk, "in_cooldown", False):
            return {"reply": "Brain is in cooldown. Cannot trade until it expires."}
        self._bot_state["running"] = True
        return {"reply": "Trading started. The brain is now analysing and executing trades autonomously."}

    async def _execute_stop_trading(self, _args: dict, _user_id: str) -> dict:
        self._bot_state["running"] = False
        return {"reply": "Trading stopped."}

    async def _execute_set_risk(self, args: dict, _user_id: str) -> dict:
        value = float(args.get("value", 5))
        value = max(MIN_RISK_PERCENT, min(MAX_RISK_PERCENT, value))
        self._bot_state["risk_percent"] = value
        return {"reply": f"Risk set to {value}%."}

    async def _execute_set_mode(self, args: dict, _user_id: str) -> dict:
        mode = args.get("mode", "long")
        self._bot_state["mode"] = mode
        return {"reply": f"Mode set to {mode}."}

    async def _execute_set_daily_limit(self, args: dict, _user_id: str) -> dict:
        value = int(args.get("value", 5))
        value = max(1, min(5, value))
        self._bot_state["daily_limit"] = value
        return {"reply": f"Daily limit set to {value}."}

    async def _execute_toggle_compound(self, _args: dict, _user_id: str) -> dict:
        current = self._bot_state.get("auto_compounding", False)
        self._bot_state["auto_compounding"] = not current
        status = "enabled" if not current else "disabled"
        return {"reply": f"Auto-compounding {status}."}

    # ── Chat ───────────────────────────────────────────────

    async def chat(
        self,
        user_message: str,
        user_id: str = "default",
    ) -> dict:
        if await self._check_rate_limit(user_id):
            return {"reply": "Too fast. Please wait."}

        system_prompt = self._build_system_prompt(user_id)

        async with self._conv_lock:
            conv = self._conversations[user_id]
            conv.append({"role": "user", "content": user_message})
            if len(conv) > 50:
                conv = conv[-50:]
                self._conversations[user_id] = conv

        if not AI_BASE_URL:
            return {"reply": "Copilot not configured."}

        messages = [{"role": "system", "content": system_prompt}]
        async with self._conv_lock:
            for msg in self._conversations[user_id][-20:]:
                messages.append(msg)

        reply = await self._call_llm(messages)

        async with self._conv_lock:
            self._conversations[user_id].append({"role": "assistant", "content": reply})

        return {"reply": reply}

    async def _call_llm(
        self,
        messages: list[dict],
    ) -> str:
        query_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                query_parts.append(f"System: {content}")
            elif role == "user":
                query_parts.append(f"User: {content}")
            elif role == "assistant":
                query_parts.append(f"Assistant: {content}")
        query = "\n\n".join(query_parts) + "\n\nAssistant:"
        params = urllib.parse.urlencode({"query": query, "model": AI_MODEL})
        url = f"{AI_BASE_URL}/?{params}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error("LLM error %d: %s", resp.status, text[:300])
                        return "I'm having trouble connecting right now."
                    data = await resp.json()
                    return data.get("message", {}).get("content", "") or "Done."
        except asyncio.TimeoutError:
            return "I'm thinking too long. Try again."
        except aiohttp.ClientError as exc:
            logger.error("LLM network error: %s", exc)
            return "Network issue. Please check your connection."

    def clear_conversation(self, user_id: str) -> None:
        self._conversations[user_id] = []
