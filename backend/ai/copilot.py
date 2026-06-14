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

from brain.config.constants import SUPPORTED_PAIRS, MIN_RISK_PERCENT, MAX_RISK_PERCENT
from brain.config.settings import AI_BASE_URL, AI_MODEL
from brain.db.supabase import (
    get_state,
    set_state,
    get_all_mt5_credentials,
    get_open_trades,
    get_recent_trades,
    get_todays_pnl,
    count_trades_today,
)

from backend.ai.market_summary import MarketSummaryEngine
from backend.ai.chart_generator import ChartGenerator
from backend.ai.tools import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

RATE_LIMIT_PER_MIN = 30
CONFIRMATION_TIMEOUT = 120

_SUPABASE_CLIENT: Any = None

def _get_supabase():
    global _SUPABASE_CLIENT
    if _SUPABASE_CLIENT is None:
        from backend.db.supabase import get_client
        _SUPABASE_CLIENT = get_client()
    return _SUPABASE_CLIENT


class CopilotEngine:

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

        memories = self._load_memories(user_id)
        memory_text = ""
        if memories:
            items = [f"- {k}: {v}" for k, v in memories.items()]
            memory_text = "REMEMBERED ABOUT YOU:\n" + "\n".join(items) + "\n\n"

        user_info = self._get_user_info(user_id)
        user_text = ""
        if user_info:
            user_text = f"YOUR SETTINGS:\n- risk: {user_info.get('risk_percent', 5)}%\n- mode: {user_info.get('trading_mode', 'short')}\n- daily limit: {user_info.get('max_daily_trades', 5)}\n- compounding: {'on' if user_info.get('auto_compounding') else 'off'}\n- broker connected: {'yes' if user_info.get('broker_verified') else 'no'}\n\n"

        return f"""You are FUTURES — a trading bot that uses a proprietary strategy created by Richie Rich. You are calm, risk-aware, and brief (1-2 sentences). You NEVER promise returns or encourage excessive risk. You NEVER give financial advice — only analysis. If asked non-trading questions, politely refuse. Use the user's name if known.

DATE: {now} UTC

{memory_text}{user_text}CURRENT MARKET CONDITIONS:
{market_text or "Market data not yet available."}

AVAILABLE TOOLS (use via TOOL_CALL format when user asks for data or wants to change settings):
""" + "\n".join(f"- {t['name']}: {t['description']}" for t in TOOL_DEFINITIONS) + """

When the user asks for data or wants to change settings, respond with a tool call in this exact format:
TOOL_CALL: tool_name | arg1=val1 | arg2=val2

CRITICAL INSTRUCTION: When the user says something like "trade X times" or "start trading for X trades" or "trade X times with Y% risk", call the start_trading tool with trade_count=X and/or risk_percent=Y. Ignore casual filler words like "trmx", "pls", "now", "please" — they are not trading pairs. The only supported pairs are: GBPUSD, GBPJPY, USDJPY, EURUSD, AUDUSD, USDCAD.

RESPOND naturally and conversationally. Do NOT output JSON or code unless calling a tool."""

    def _get_user_info(self, user_id: str) -> dict | None:
        try:
            sb = _get_supabase()
            if not sb:
                return None
            profile = sb.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
            settings = sb.table("user_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            creds = sb.table("mt5_credentials").select("connected").eq("user_id", user_id).maybe_single().execute()
            info = {}
            if profile.data:
                info["risk_percent"] = profile.data.get("risk_percent", 5)
                info["auto_compounding"] = profile.data.get("auto_compounding", False)
                info["broker_verified"] = profile.data.get("broker_verified", False)
            if settings.data:
                info["trading_mode"] = settings.data.get("trading_mode", "short")
                info["max_daily_trades"] = settings.data.get("max_daily_trades", 5)
                info["trade_count"] = settings.data.get("trade_count", 1)
            info["mt5_connected"] = bool(creds.data.get("connected")) if creds.data else False
            return info
        except Exception as exc:
            logger.debug("Failed to fetch user info for %s: %s", user_id, exc)
            return None

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

    # ── Tool Dispatch ──────────────────────────────────────

    async def _handle_tool(self, tool_name: str, args: dict, user_id: str) -> Any:
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
            result = await handler(args, user_id)
            return result
        except Exception as exc:
            logger.error("Tool %s error for user %s: %s", tool_name, user_id, exc)
            return {"error": str(exc)}

    async def _tool_account_summary(self, _args: dict, user_id: str) -> dict:
        info = self._get_user_info(user_id)
        trades_today = count_trades_today(user_id=user_id)
        daily_limit = info.get("max_daily_trades", 5) if info else 5
        bot_running = self._bot_state.get("running", False)
        return {
            "trades_today": trades_today,
            "trades_remaining": max(0, daily_limit - trades_today),
            "daily_limit": daily_limit,
            "bot_active": bot_running,
            "risk_percent": info.get("risk_percent", 5) if info else 5,
            "trading_mode": info.get("trading_mode", "short") if info else "short",
            "mt5_connected": info.get("mt5_connected", False) if info else False,
            "broker_verified": info.get("broker_verified", False) if info else False,
        }

    async def _tool_open_positions(self, _args: dict, user_id: str) -> list:
        trades = get_open_trades(user_id=user_id)
        return [
            {
                "ticket": t.get("ticket", 0),
                "symbol": t.get("pair", ""),
                "direction": t.get("direction", ""),
                "entry": t.get("entry_price", 0),
                "sl": t.get("sl_price", 0),
                "tp": t.get("tp_price", 0),
                "profit": round(t.get("pnl", 0), 2) if t.get("pnl") else 0,
                "opened_at": t.get("opened_at", ""),
            }
            for t in trades
        ]

    async def _tool_recent_trades(self, args: dict, user_id: str) -> list:
        limit = min(args.get("limit", 5), 20)
        trades = get_recent_trades(limit=limit, user_id=user_id)
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

    async def _tool_market_summary(self, args: dict, _user_id: str) -> dict:
        symbol = args.get("symbol", "").upper()
        summary = self.market_summary.get_summary(symbol)
        if not summary:
            return {"error": f"No market data for {symbol}"}
        return summary

    async def _tool_explain_last_trade(self, _args: dict, user_id: str) -> dict:
        trades = get_recent_trades(limit=1, user_id=user_id)
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

    async def _tool_generate_chart(self, args: dict, _user_id: str) -> dict:
        symbol = args.get("symbol", "").upper()
        tf = args.get("timeframe", "15m")
        path = await asyncio.get_event_loop().run_in_executor(
            None, self.chart_generator.generate, symbol, tf, 50
        )
        if path:
            return {"image_path": path, "message": f"Chart generated for {symbol} ({tf})."}
        return {"error": "Failed to generate chart. Ensure mplfinance is installed."}

    async def _tool_news_status(self, _args: dict, _user_id: str) -> dict:
        try:
            from brain.core.news_volatility import MT5NewsFilter
            filter = MT5NewsFilter()
            filter.refresh(hours_ahead=4)
            events = filter.get_upcoming_events(hours_ahead=4)
            now_paused = any(filter.is_news_window(p) for p in SUPPORTED_PAIRS)
            return {
                "news_paused": now_paused,
                "upcoming_events": events[:10],
                "status": f"{len(events)} upcoming events in next 4h" if events else "No high-impact news expected",
            }
        except Exception as exc:
            logger.warning("News status error: %s", exc)
            return {"news_paused": False, "upcoming_events": [], "status": "News check unavailable"}

    async def _tool_bot_health(self, _args: dict, user_id: str) -> dict:
        info = self._get_user_info(user_id)
        mt5_ok = info.get("mt5_connected", False) if info else False
        bot_running = self._bot_state.get("running", False)
        return {
            "mt5_connected": mt5_ok,
            "bot_running": bot_running,
            "broker_verified": info.get("broker_verified", False) if info else False,
            "healthy": mt5_ok and bot_running,
        }

    async def _tool_daily_pnl(self, _args: dict, user_id: str) -> dict:
        pnl = get_todays_pnl(user_id=user_id)
        return {"pnl": round(pnl, 2)}

    async def _tool_trading_strategy(self, _args: dict, _user_id: str) -> dict:
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
            "pairs": SUPPORTED_PAIRS,
            "session": "06:00-20:00 UTC",
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

    async def _update_profile(self, user_id: str, updates: dict) -> bool:
        try:
            sb = _get_supabase()
            if not sb:
                return False
            sb.table("profiles").update(updates).eq("id", user_id).execute()
            return True
        except Exception as exc:
            logger.warning("Failed to update profile for %s: %s", user_id, exc)
            return False

    async def _upsert_user_settings(self, user_id: str, updates: dict) -> bool:
        try:
            sb = _get_supabase()
            if not sb:
                return False
            data = {"user_id": user_id, **updates}
            sb.table("user_settings").upsert(data, on_conflict="user_id").execute()
            return True
        except Exception as exc:
            logger.warning("Failed to update user_settings for %s: %s", user_id, exc)
            return False

    async def _execute_start_trading(self, args: dict, user_id: str) -> dict:
        trade_count = args.get("trade_count")
        if trade_count is not None:
            trade_count = max(1, min(10, int(trade_count)))
            self._bot_state["trade_count"] = trade_count
            await self._upsert_user_settings(user_id, {"trade_count": trade_count})

        mode = args.get("mode")
        if mode:
            await self._upsert_user_settings(user_id, {"trading_mode": mode})

        risk_pct = args.get("risk_percent")
        if risk_pct is not None:
            risk_pct = max(1, min(10, float(risk_pct)))
            await self._update_profile(user_id, {"risk_percent": risk_pct})

        self._bot_state["running"] = True
        await self._update_profile(user_id, {"bot_active": True})
        return {"reply": "Trading started. The brain is now analysing and executing trades for all connected users."}

    async def _execute_stop_trading(self, _args: dict, user_id: str) -> dict:
        self._bot_state["running"] = False
        await self._update_profile(user_id, {"bot_active": False})
        return {"reply": "Trading stopped for all users."}

    async def _execute_set_risk(self, args: dict, user_id: str) -> dict:
        value = float(args.get("value", 5))
        value = max(MIN_RISK_PERCENT, min(MAX_RISK_PERCENT, value))
        ok = await self._update_profile(user_id, {"risk_percent": value})
        if ok:
            return {"reply": f"Risk set to {value}% per trade."}
        return {"reply": "Failed to save risk setting. Try again."}

    async def _execute_set_mode(self, args: dict, user_id: str) -> dict:
        mode = args.get("mode", "long")
        ok = await self._upsert_user_settings(user_id, {"trading_mode": mode})
        if ok:
            return {"reply": f"Trading mode set to {mode}."}
        return {"reply": "Failed to save mode. Try again."}

    async def _execute_set_daily_limit(self, args: dict, user_id: str) -> dict:
        value = int(args.get("value", 5))
        value = max(1, min(20, value))
        ok = await self._upsert_user_settings(user_id, {"max_daily_trades": value})
        if ok:
            return {"reply": f"Daily trade limit set to {value}."}
        return {"reply": "Failed to save daily limit. Try again."}

    async def _execute_toggle_compound(self, _args: dict, user_id: str) -> dict:
        info = self._get_user_info(user_id)
        current = info.get("auto_compounding", False) if info else False
        new_val = not current
        ok = await self._update_profile(user_id, {"auto_compounding": new_val})
        status = "enabled" if new_val else "disabled"
        if ok:
            return {"reply": f"Auto-compounding {status}."}
        return {"reply": "Failed to toggle compounding. Try again."}

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
            if user_id not in self._conversations or not self._conversations[user_id]:
                saved = get_state(f"conversation:{user_id}", default=[])
                self._conversations[user_id] = saved if isinstance(saved, list) else []

            conv = self._conversations[user_id]
            conv.append({"role": "user", "content": user_message})
            if len(conv) > 50:
                conv = conv[-50:]
                self._conversations[user_id] = conv

        self._extract_and_save_memories(user_message, user_id)

        if not AI_BASE_URL:
            return {"reply": "Copilot not configured."}

        messages = [{"role": "system", "content": system_prompt}]
        async with self._conv_lock:
            for msg in self._conversations[user_id][-20:]:
                messages.append(msg)

        reply = await self._call_llm(messages)

        tool_result = await self._try_handle_tool_call(reply, user_id)
        if tool_result is not None:
            reply = tool_result

        async with self._conv_lock:
            self._conversations[user_id].append({"role": "assistant", "content": reply})
            set_state(f"conversation:{user_id}", self._conversations[user_id])

        return {"reply": reply}

    async def _try_handle_tool_call(self, reply: str, user_id: str) -> str | None:
        if not reply.startswith("TOOL_CALL:"):
            return None
        parts = reply[len("TOOL_CALL:"):].strip().split("|")
        tool_name = parts[0].strip()
        args = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                args[k.strip()] = v.strip()
        if tool_name in ("start_trading", "stop_trading", "toggle_auto_compounding"):
            conf_id = await self.request_confirmation(user_id, {"tool": tool_name, "args": args})
            return f"I'll need your confirmation. Please reply with your confirmation ID: {conf_id}"
        result = await self._handle_tool(tool_name, args, user_id)
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        return str(result)

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
        params = urllib.parse.urlencode({"text": query})
        url = f"{AI_BASE_URL}?{params}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers={"Accept": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error("LLM error %d: %s", resp.status, body[:300])
                        return "I'm having trouble connecting right now."
                    data = await resp.json()
                    if isinstance(data, str):
                        return data
                    return (data.get("result", "")
                            or data.get("message", {}).get("content", "")
                            or data.get("response", "")
                            or data.get("text", "")
                            or str(data)[:500] or "Done.")
        except asyncio.TimeoutError:
            return "I'm thinking too long. Try again."
        except aiohttp.ClientError as exc:
            logger.error("LLM network error: %s", exc)
            return "Network issue. Please check your connection."

    def _load_memories(self, user_id: str) -> dict:
        key = f"ai_memories:{user_id}"
        mem = get_state(key)
        return mem if isinstance(mem, dict) else {}

    def _save_memory(self, user_id: str, key: str, value: str) -> None:
        memories = self._load_memories(user_id)
        memories[key] = value
        set_state(f"ai_memories:{user_id}", memories)

    async def _extract_and_save_memories(self, user_message: str, user_id: str) -> None:
        lower = user_message.lower()
        for pattern, mem_key in [
            ("my name is", "name"),
            ("i'm ", "name"),
            ("call me ", "name"),
        ]:
            if pattern in lower:
                idx = lower.index(pattern) + len(pattern)
                val = user_message[idx:].strip().rstrip(".!,?").split()[0].strip("'")
                if val:
                    self._save_memory(user_id, mem_key, val)

    def clear_conversation(self, user_id: str) -> None:
        self._conversations[user_id] = []
        set_state(f"conversation:{user_id}", [])
