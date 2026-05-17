from __future__ import annotations

import os
import logging
from typing import Any

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")

_supabase: Client | None = None


def get_client() -> Client | None:
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("Supabase credentials not configured")
            return None
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


async def sign_up(email: str, password: str) -> dict:
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    res = client.auth.sign_up({"email": email, "password": password})
    return {"user": res.user.model_dump() if res.user else None, "session": res.session.model_dump() if res.session else None}


async def sign_in(email: str, password: str) -> dict:
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    return {"user": res.user.model_dump() if res.user else None, "session": res.session.model_dump() if res.session else None}


async def sign_out(access_token: str) -> dict:
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    if access_token:
        client.auth.sign_out()
    return {"status": "signed_out"}


async def get_user(access_token: str) -> dict | None:
    client = get_client()
    if not client:
        return None
    if not access_token:
        return None
    res = client.auth.get_user(access_token)
    return res.user.model_dump() if res.user else None


async def save_trade(trade_data: dict) -> dict:
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    res = client.table("trades").insert(trade_data).execute()
    return res.data[0] if res.data else {}


async def get_trades(user_id: str, limit: int = 50) -> list:
    client = get_client()
    if not client:
        return []
    res = client.table("trades").select("*").eq("user_id", user_id).order("opened_at", desc=True).limit(limit).execute()
    return res.data or []
