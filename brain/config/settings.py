# ============================================================
# FuturesBrain v1.0 – Settings (Environment Variables)
# Uses pydantic-settings for type-safe env loading.
# ============================================================
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env before anything reads os.environ
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# ── Derived paths ──────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Ensure runtime directories exist (idempotent)
for _dir in ["db", "logs", "charts"]:
    (BASE_DIR / _dir).mkdir(parents=True, exist_ok=True)

# ── OpenRouter ─────────────────────────────────────────────
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL: str = os.getenv(
    "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
)

# ── Supabase (Transaction Pooler port 6543, IPv4) ─────────
SUPABASE_DB_URI: str | None = os.getenv("SUPABASE_DB_URI")

# ── Logging ────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Supabase Service Role (admin) ─────────────────────────
SUPABASE_SERVICE_ROLE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ── Telegram Admin Bot ─────────────────────────────────────
TELEGRAM_ADMIN_BOT_TOKEN: str | None = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")
TELEGRAM_ADMIN_ID_1: int = int(os.getenv("TELEGRAM_ADMIN_ID_1", "0"))
TELEGRAM_ADMIN_ID_2: int = int(os.getenv("TELEGRAM_ADMIN_ID_2", "0"))

# ── Telegram (legacy) ──────────────────────────────────────
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")


def validate_required() -> list[str]:
    """
    Return list of missing required env vars.
    """
    missing: list[str] = []
    if not OPENROUTER_API_KEY:
        missing.append("OPENROUTER_API_KEY")
    return missing
