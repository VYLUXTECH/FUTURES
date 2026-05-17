from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

_SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
_SERVICE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

_client: Client | None = None


def _get_admin() -> Client | None:
    global _client
    if _client is None:
        if not _SUPABASE_URL or not _SERVICE_KEY:
            logger.warning("Supabase admin credentials not configured")
            return None
        _client = create_client(_SUPABASE_URL, _SERVICE_KEY)
    return _client


def _log(user_id: int, action: str, detail: str = "") -> None:
    cli = _get_admin()
    if not cli:
        return
    try:
        cli.table("system_logs").insert({
            "user_id": str(user_id),
            "action": action,
            "detail": detail,
            "level": "INFO",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logger.warning("Failed to log admin action: %s", exc)


def get_health() -> dict[str, Any]:
    cli = _get_admin()
    if not cli:
        return {"error": "Supabase not configured"}

    result: dict[str, Any] = {}

    now = datetime.now(timezone.utc)
    today_start = now.strftime("%Y-%m-%dT00:00:00Z")
    last_24h = (now - timedelta(hours=24)).isoformat()
    last_30d = (now - timedelta(days=30)).isoformat()

    try:
        prof = cli.table("profiles").select("id", count="exact").eq("bot_active", True).execute()
        result["active_users"] = prof.count if hasattr(prof, "count") else len(prof.data or [])
    except Exception:
        result["active_users"] = "N/A"

    try:
        trades_24h = cli.table("trades").select("pnl", "status", count="exact").gte("closed_at", last_24h).execute()
        result["trades_24h"] = trades_24h.count if hasattr(trades_24h, "count") else len(trades_24h.data or [])
        pnl = sum(t.get("pnl", 0) or 0 for t in (trades_24h.data or []))
        result["pnl_24h"] = round(pnl, 2)
    except Exception:
        result["trades_24h"] = "N/A"
        result["pnl_24h"] = "N/A"

    try:
        trades_30d = cli.table("trades").select("pnl", "status").gte("closed_at", last_30d).execute()
        data = trades_30d.data or []
        total = len(data)
        wins = sum(1 for t in data if (t.get("pnl") or 0) > 0)
        result["win_rate_30d"] = f"{round(wins / total * 100, 1)}%" if total else "N/A"
        net = sum(t.get("pnl", 0) or 0 for t in data)
        result["net_pnl_30d"] = round(net, 2)
    except Exception:
        result["win_rate_30d"] = "N/A"
        result["net_pnl_30d"] = "N/A"

    try:
        logs = cli.table("system_logs").select("detail").eq("level", "ERROR").gte("created_at", last_24h).limit(1).order("created_at", desc=True).execute()
        result["last_error"] = logs.data[0]["detail"] if logs.data else None
    except Exception:
        result["last_error"] = "N/A"

    try:
        news = cli.table("news_state").select("phase").limit(1).execute()
        result["news_monitor"] = "Active" if news.data else "Inactive"
    except Exception:
        result["news_monitor"] = "N/A"

    return result


def get_users() -> list[dict[str, Any]]:
    cli = _get_admin()
    if not cli:
        return []
    try:
        res = cli.table("profiles").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as exc:
        logger.warning("Failed to fetch users: %s", exc)
        return []


def get_user_detail(user_id: str) -> dict[str, Any] | None:
    cli = _get_admin()
    if not cli:
        return None
    try:
        res = cli.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if not res.data:
            return None
        user = res.data[0]
        trades = cli.table("trades").select("*").eq("user_id", user_id).is_("closed_at", "null").execute()
        user["open_positions"] = trades.data or []
        return user
    except Exception as exc:
        logger.warning("Failed to fetch user %s: %s", user_id, exc)
        return None


def stop_user(user_id: str) -> bool:
    cli = _get_admin()
    if not cli:
        return False
    try:
        cli.table("profiles").update({"bot_active": False}).eq("id", user_id).execute()
        _log(0, "stop_user", f"Stopped bot for user {user_id}")
        return True
    except Exception as exc:
        logger.warning("Failed to stop user %s: %s", user_id, exc)
        return False


def global_shutdown() -> bool:
    cli = _get_admin()
    if not cli:
        return False
    try:
        cli.table("profiles").update({"bot_active": False}).neq("id", "none").execute()
        _log(0, "global_shutdown", "Emergency stop for all users")
        return True
    except Exception as exc:
        logger.warning("Failed global shutdown: %s", exc)
        return False


def get_issues() -> list[dict[str, Any]]:
    cli = _get_admin()
    if not cli:
        return []
    try:
        res = cli.table("support_tickets").select("*").neq("status", "resolved").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as exc:
        logger.warning("Failed to fetch issues: %s", exc)
        return []


def resolve_issue(issue_id: int | str) -> bool:
    cli = _get_admin()
    if not cli:
        return False
    try:
        cli.table("support_tickets").update({"status": "resolved"}).eq("id", issue_id).execute()
        _log(0, "resolve_issue", f"Resolved issue #{issue_id}")
        return True
    except Exception as exc:
        logger.warning("Failed to resolve issue %s: %s", issue_id, exc)
        return False


def get_stats(days: int = 30) -> dict[str, Any]:
    cli = _get_admin()
    if not cli:
        return {"error": "Supabase not configured"}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result: dict[str, Any] = {}

    try:
        trades = cli.table("trades").select("pnl", "status").gte("closed_at", cutoff).execute()
        data = trades.data or []
        total = len(data)
        result["total_trades"] = total
        wins = [t for t in data if (t.get("pnl") or 0) > 0]
        losses = [t for t in data if (t.get("pnl") or 0) <= 0]
        result["wins"] = len(wins)
        result["losses"] = len(losses)
        result["win_rate"] = f"{round(len(wins) / total * 100, 1)}%" if total else "N/A"

        gross_win = sum(t.get("pnl", 0) or 0 for t in wins)
        gross_loss = abs(sum(t.get("pnl", 0) or 0 for t in losses))
        result["net_pnl"] = round(gross_win - gross_loss, 2)
        result["profit_factor"] = round(gross_win / gross_loss, 2) if gross_loss else "N/A"

        result["avg_win"] = round(gross_win / len(wins), 2) if wins else 0
        result["avg_loss"] = round(gross_loss / len(losses), 2) if losses else 0
        result["largest_win"] = round(max(t.get("pnl", 0) or 0 for t in wins), 2) if wins else 0
        result["largest_loss"] = round(min(t.get("pnl", 0) or 0 for t in losses), 2) if losses else 0

        result["period_days"] = days
    except Exception as exc:
        logger.warning("Failed to compute stats: %s", exc)
        return {"error": str(exc)}

    return result


def send_push_notification(title: str, body: str, push_tokens: list[str]) -> tuple[int, int]:
    if not push_tokens:
        return 0, 0
    try:
        import requests
        payload = [{"to": t, "title": title, "body": body, "sound": "default"} for t in push_tokens]
        resp = requests.post(
            "https://exp.host/--/api/v2/push/send",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        data = resp.json()
        sent = len(push_tokens)
        errors = sum(1 for d in data.get("data", []) if d.get("status") == "error") if isinstance(data.get("data"), list) else 0
        return sent, errors
    except Exception as exc:
        logger.warning("Push notification error: %s", exc)
        return 0, len(push_tokens)


def broadcast_to_all(title: str, message: str) -> tuple[int, int]:
    cli = _get_admin()
    if not cli:
        return 0, 0
    try:
        res = cli.table("profiles").select("expo_push_token").not_.is_("expo_push_token", "null").execute()
        tokens = [p["expo_push_token"] for p in (res.data or []) if p.get("expo_push_token")]
        sent, errors = send_push_notification(title, message, tokens)
        _log(0, "broadcast", f"Sent to {sent} users, {errors} errors: {message[:50]}")
        return sent, errors
    except Exception as exc:
        logger.warning("Broadcast error: %s", exc)
        return 0, 0


def get_daily_report() -> dict[str, Any]:
    cli = _get_admin()
    if not cli:
        return {"error": "Supabase not configured"}

    now = datetime.now(timezone.utc)
    today_start = now.strftime("%Y-%m-%dT00:00:00Z")
    result: dict[str, Any] = {}

    try:
        prof = cli.table("profiles").select("id", count="exact").eq("bot_active", True).execute()
        result["active_users"] = prof.count if hasattr(prof, "count") else len(prof.data or [])
    except Exception:
        result["active_users"] = "N/A"

    try:
        trades = cli.table("trades").select("pnl", "status").gte("closed_at", today_start).execute()
        data = trades.data or []
        total = len(data)
        result["trades_today"] = total
        wins = sum(1 for t in data if (t.get("pnl") or 0) > 0)
        result["wins"] = wins
        result["win_rate"] = f"{round(wins / total * 100, 1)}%" if total else "N/A"
        pnl = sum(t.get("pnl", 0) or 0 for t in data)
        result["pnl_today"] = round(pnl, 2)
    except Exception:
        result["trades_today"] = "N/A"
        result["win_rate"] = "N/A"
        result["pnl_today"] = "N/A"

    try:
        errors = cli.table("system_logs").select("id", count="exact").eq("level", "ERROR").gte("created_at", today_start).execute()
        result["errors_today"] = errors.count if hasattr(errors, "count") else "N/A"
    except Exception:
        result["errors_today"] = "N/A"

    return result
