from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_USERS_FILE = _DATA_DIR / "users.json"
_lock = threading.Lock()


def _load_users() -> list[dict]:
    try:
        if _USERS_FILE.exists():
            data = json.loads(_USERS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Failed to load users file: %s", exc)
    return []


def _save_users(users: list[dict]) -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _USERS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(users, indent=2), encoding="utf-8")
        tmp.replace(_USERS_FILE)
    except Exception as exc:
        logger.warning("Failed to save users file: %s", exc)


def ensure_users_table(uri: str | None = None) -> None:
    """Local store — ensure the users file exists (no-op beyond file creation)."""
    with _lock:
        _save_users(_load_users())


def seed_admin(password_hash: str | None = None, email: str | None = None) -> None:
    """Seed a default admin account if one doesn't exist. Requires a password hash."""
    if not password_hash:
        return
    email = (email or os.getenv("ADMIN_EMAIL", "admin@futuretraders.net")).strip().lower()
    with _lock:
        users = _load_users()
        if any(u.get("email") == email for u in users):
            return
        users.append({
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_hash,
            "display_name": "Admin",
            "created_at": "",
        })
        _save_users(users)
        logger.info("Seeded local admin account: %s", email)


def create_user(email: str, password_hash: str, display_name: str = "") -> dict | None:
    """Create a new user. Returns the user dict or None on error."""
    email = email.lower().strip()
    with _lock:
        users = _load_users()
        if any(u.get("email") == email for u in users):
            return None
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_hash,
            "display_name": display_name or "Trader",
            "created_at": "",
        }
        users.append(user)
        _save_users(users)
        return {"id": user["id"], "email": user["email"], "display_name": user["display_name"], "created_at": user["created_at"]}


def get_user_by_email(email: str) -> dict | None:
    email = email.lower().strip()
    with _lock:
        for u in _load_users():
            if u.get("email") == email:
                return dict(u)
    return None


def get_user_by_id(user_id: str) -> dict | None:
    with _lock:
        for u in _load_users():
            if u.get("id") == user_id:
                return {
                    "id": u["id"],
                    "email": u["email"],
                    "display_name": u.get("display_name", ""),
                    "created_at": u.get("created_at", ""),
                }
    return None


def update_password(user_id: str, password_hash: str) -> bool:
    with _lock:
        users = _load_users()
        for u in users:
            if u.get("id") == user_id:
                u["password_hash"] = password_hash
                _save_users(users)
                return True
    return False
