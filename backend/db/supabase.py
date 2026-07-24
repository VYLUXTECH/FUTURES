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
