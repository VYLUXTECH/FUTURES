# ============================================================
# FuturesBrain v1.0 – AI Copilot Endpoint (Custom AI + HF Vision)
# Uses DeepSeek via all-in-1-ais for text analysis and
# Qwen-VL via HuggingFace Inference API for chart vision.
# ============================================================
from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.parse
from collections import defaultdict
from typing import Any

import aiohttp

from brain.config.settings import AI_BASE_URL, AI_MODEL, HF_TOKEN, HF_VISION_MODEL

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────
COPILOT_CACHE_TTL: int = 300        # 5 minutes
RATE_LIMIT_PER_HOUR: int = 15

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


async def _analyze_with_hf_vision(
    chart_data_uri: str,
    pair: str,
    tf: str,
    context: dict | None = None,
) -> dict | None:
    """Analyze chart image using HuggingFace Qwen-VL vision model."""
    if not HF_TOKEN:
        logger.warning("HF_TOKEN not configured, skipping vision analysis")
        return None

    if not chart_data_uri.startswith("data:image/"):
        chart_data_uri = f"data:image/png;base64,{chart_data_uri}"

    user_text = (
        f"Analyse this {pair} {tf} forex chart. "
        f"Describe the candlestick pattern, support/resistance levels, "
        f"and any rejection wicks or market structure breaks you see."
        + (f" Context: {context}" if context else "")
    )

    hf_url = f"https://api-inference.huggingface.co/models/{HF_VISION_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}

    payload = {
        "inputs": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": chart_data_uri}},
                    ],
                }
            ],
            "max_tokens": 512,
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                hf_url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning("HF vision error %d: %s", resp.status, text[:200])
                    return None
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0:
                    content = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    content = data.get("generated_text", "")
                else:
                    content = str(data)
                return {"vision_analysis": content[:1000]}
    except Exception as exc:
        logger.warning("HF vision call failed: %s", exc)
        return None


async def _call_ai_text(messages: list[dict]) -> dict:
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

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error("AI text error %d: %s", resp.status, text[:300])
                return {"error": f"upstream_error_{resp.status}"}
            data = await resp.json()
            content = data.get("message", {}).get("content", "")
            return {"content": content}


async def analyze_chart(
    chart_data_uri: str,
    pair: str,
    tf: str,
    context: dict | None = None,
    client_ip: str = "unknown",
) -> dict:
    """
    Analyze chart screenshot using custom AI endpoint for text analysis
    and optionally HuggingFace Qwen-VL for vision-based insights.
    Returns structured JSON dict or error dict.
    """
    if not AI_BASE_URL:
        return {"error": "AI_BASE_URL not configured"}

    if await is_rate_limited(client_ip):
        return {"error": "rate_limit_exceeded", "limit": RATE_LIMIT_PER_HOUR}

    cache_key = f"{pair}_{tf}_{chart_data_uri[:50]}"
    cached = await get_cached(cache_key)
    if cached:
        logger.debug("Copilot cache hit for %s/%s", pair, tf)
        return {**cached, "_cached": True}

    # Try HF vision analysis first (adds chart context)
    vision_insight = await _analyze_with_hf_vision(chart_data_uri, pair, tf, context)
    vision_context = ""
    if vision_insight:
        vision_context = f"\nChart vision analysis: {vision_insight.get('vision_analysis', '')}"

    user_text = (
        f"Analyse this {pair} {tf} chart."
        + (f" Context: {context}" if context else "")
        + vision_context
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    result = await _call_ai_text(messages)
    if "error" in result:
        return result

    content = result.get("content", "")

    try:
        content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Copilot JSON parse error: %s | raw=%s", exc, content[:200])
        return {"error": "parse_error", "raw": content[:500]}

    await set_cached(cache_key, parsed)
    return parsed
