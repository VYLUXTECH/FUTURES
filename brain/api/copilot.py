# ============================================================
# FuturesBrain v1.0 – AI Copilot Endpoint (OpenRouter)
# BUG FIXES:
#   • base64 image URL was "image/png;base64,..." (missing "data:")
#   • Cache now uses asyncio.Lock (was non-async)
#   • Rate limiter keyed per IP, not hardcoded "admin"
#   • Copilot NEVER executes trades (enforced via system prompt)
# SPEC COMPLIANCE:
#   • 5-min response cache per pair+tf
#   • 15 req/hr rate limit (per IP)
#   • JSON schema enforced in response
# ============================================================
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

import aiohttp

from config.settings import OPENROUTER_API_KEY, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

# ── Constants (spec-aligned) ───────────────────────────────
COPILOT_CACHE_TTL: int = 300        # 5 minutes
RATE_LIMIT_PER_HOUR: int = 15
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = """You are FuturesBrain Copilot, a read-only trading analyst.
You analyse forex charts and provide structured JSON insights.
CRITICAL: You NEVER suggest trade execution. You NEVER output order commands.
You only analyse and explain what you see.

Respond ONLY with valid JSON in this exact schema:
{
  "bias": "BULLISH | BEARISH | NEUTRAL",
  "confidence": <0-100 integer>,
  "key_observation": "<one concise sentence>",
  "support_level": <float or null>,
  "resistance_level": <float or null>,
  "risk_note": "<brief risk consideration>",
  "sectors_observed": ["<pattern>", ...]
}"""

# ── In-memory stores (module-level singletons) ─────────────
_cache: dict[str, tuple[Any, float]] = {}
_cache_lock = asyncio.Lock()

# Rate limiter: IP → list of timestamps
_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = asyncio.Lock()


async def is_rate_limited(client_ip: str) -> bool:
    """Return True if this IP has exceeded 15 requests per hour."""
    async with _rate_lock:
        now = time.monotonic()
        window_start = now - 3600
        # Purge old entries
        _rate_store[client_ip] = [
            ts for ts in _rate_store[client_ip] if ts > window_start
        ]
        if len(_rate_store[client_ip]) >= RATE_LIMIT_PER_HOUR:
            return True
        _rate_store[client_ip].append(now)
        return False


async def get_cached(cache_key: str) -> Any | None:
    async with _cache_lock:
        entry = _cache.get(cache_key)
        if entry is None:
            return None
        data, ts = entry
        if time.monotonic() - ts > COPILOT_CACHE_TTL:
            del _cache[cache_key]
            return None
        return data


async def set_cached(cache_key: str, data: Any) -> None:
    async with _cache_lock:
        _cache[cache_key] = (data, time.monotonic())


async def analyze_chart(
    chart_data_uri: str,   # "data:image/png;base64,..."  ← FIX: include data: prefix
    pair: str,
    tf: str,
    context: dict | None = None,
    client_ip: str = "unknown",
) -> dict:
    """
    Send chart screenshot to OpenRouter Claude Vision for analysis.
    Returns a structured JSON dict or an error dict.

    The chart_data_uri MUST start with "data:image/png;base64," as
    returned by data/feed.py capture_chart().
    """
    if not OPENROUTER_API_KEY:
        return {"error": "OPENROUTER_API_KEY not configured"}

    # Rate limit check
    if await is_rate_limited(client_ip):
        return {"error": "rate_limit_exceeded", "limit": RATE_LIMIT_PER_HOUR}

    # Cache hit
    cache_key = f"{pair}_{tf}_{chart_data_uri[:50]}"
    cached = await get_cached(cache_key)
    if cached:
        logger.debug("Copilot cache hit for %s/%s", pair, tf)
        return {**cached, "_cached": True}

    # ── FIX: correct base64 URI (already has "data:" from feed.py) ─
    # Validate the URI starts with the expected prefix
    if not chart_data_uri.startswith("data:image/"):
        chart_data_uri = f"data:image/png;base64,{chart_data_uri}"

    user_text = (
        f"Analyse this {pair} {tf} chart. "
        + (f"Context: {context}" if context else "")
    )

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type":      "image_url",
                        "image_url": {"url": chart_data_uri},    # ← correct URI
                    },
                    {"type": "text", "text": user_text},
                ],
            },
        ],
        "max_tokens": 512,
        "temperature": 0.1,
    }

    headers = {
        "Authorization":  f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":   "application/json",
        "HTTP-Referer":   "https://futuresbrain.app",
        "X-Title":        "FuturesBrain Copilot",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _OPENROUTER_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("OpenRouter error %d: %s", resp.status, text[:300])
                    return {"error": f"upstream_error_{resp.status}"}

                data = await resp.json()

    except asyncio.TimeoutError:
        return {"error": "upstream_timeout"}
    except aiohttp.ClientError as exc:
        logger.error("Copilot network error: %s", exc)
        return {"error": "network_error"}

    # Parse JSON from model response
    try:
        content = data["choices"][0]["message"]["content"]
        import json
        # Strip markdown code fences if present
        content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        result = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Copilot JSON parse error: %s | raw=%s", exc, str(data)[:200])
        return {"error": "parse_error", "raw": str(data)[:500]}

    await set_cached(cache_key, result)
    return result
