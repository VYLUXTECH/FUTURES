from __future__ import annotations

import csv
import io
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from brain.db.postgres import get_recent_trades
from backend.db.supabase import get_client
from backend.api.middleware import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

_bot_state_ref: dict[str, Any] | None = None


def set_bot_state_ref(state: dict) -> None:
    global _bot_state_ref
    _bot_state_ref = state


class SettingsUpdate(BaseModel):
    risk_percent: float | None = Field(default=None, ge=0.0, le=10.0)
    be_policy: str | None = Field(default=None, pattern="^(auto|notify|none)$")
    dry_run: bool | None = None
    auto_compounding: bool | None = None
    display_name: str | None = Field(default=None, max_length=100)
    notifications: dict[str, bool] | None = None
    max_daily_trades: int | None = Field(default=None, ge=1, le=25)


@router.get("/settings")
async def get_settings(request: Request, user: dict = Depends(require_auth)) -> dict:
    client = get_client()
    if not client:
        return _default_settings()
    user_id = user.get("sub")
    if not user_id:
        return _default_settings()
    try:
        res = client.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
        if res.data:
            profile = res.data if isinstance(res.data, dict) else {}
            max_daily = 5
            try:
                settings_res = client.table("user_settings").select("max_daily_trades").eq("user_id", user_id).maybe_single().execute()
                if settings_res.data:
                    max_daily = settings_res.data.get("max_daily_trades", 5)
            except Exception:
                pass
            return {
                "risk_percent": profile.get("risk_percent", 5.0),
                "be_policy": profile.get("be_policy", "auto"),
                "dry_run": profile.get("dry_run", False),
                "auto_compounding": profile.get("auto_compounding", False),
                "display_name": profile.get("display_name", "Trader"),
                "max_daily_trades": max_daily,
                "notifications": profile.get("notifications", {
                    "trade_execution": True, "trade_closed": True, "daily_summary": True,
                    "loss_cooldown": True, "maintenance": True, "email_trade": False,
                }),
            }
    except Exception as e:
        logger.warning("Failed to fetch settings: %s", e)

    return _default_settings()


def _default_settings() -> dict:
    risk = _bot_state_ref.get("risk_percent") if _bot_state_ref else 5.0
    return {
        "risk_percent": risk or 5.0,
        "be_policy": "auto",
        "dry_run": False,
        "auto_compounding": False,
        "display_name": "Trader",
        "max_daily_trades": _bot_state_ref.get("max_daily_trades", 5) if _bot_state_ref else 5,
        "notifications": {
            "trade_execution": True, "trade_closed": True, "daily_summary": True,
            "loss_cooldown": True, "maintenance": True, "email_trade": False,
        },
    }


@router.post("/settings")
async def update_settings(req: SettingsUpdate, user: dict = Depends(require_auth)) -> dict:
    client = get_client()
    if not client:
        if _bot_state_ref is not None and req.risk_percent is not None:
            _bot_state_ref["risk_percent"] = req.risk_percent
        if _bot_state_ref is not None and req.max_daily_trades is not None:
            _bot_state_ref["max_daily_trades"] = req.max_daily_trades
        return {"status": "updated", "note": "in-memory only (no supabase)"}

    user_id = user.get("sub")
    if not user_id:
        return {"status": "error", "note": "no user"}
    updates: dict[str, Any] = {}
    for field in ("risk_percent", "be_policy", "dry_run", "auto_compounding", "display_name", "notifications"):
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val

    if _bot_state_ref is not None and req.risk_percent is not None:
        _bot_state_ref["risk_percent"] = req.risk_percent
    if _bot_state_ref is not None and req.max_daily_trades is not None:
        _bot_state_ref["max_daily_trades"] = req.max_daily_trades

    if updates:
        try:
            client.table("profiles").update(updates).eq("id", user_id).execute()
        except Exception as e:
            logger.warning("Failed to update settings: %s", e)
            return {"status": "updated", "note": "in-memory only"}

    if req.max_daily_trades is not None:
        try:
            client.table("user_settings").upsert(
                {"user_id": user_id, "max_daily_trades": req.max_daily_trades},
                on_conflict="user_id",
            ).execute()
        except Exception as e:
            logger.warning("Failed to update user_settings: %s", e)

    return {"status": "updated"}


# ── MT5 Credentials (get/update for Settings page) ────────

class MT5CredentialsUpdate(BaseModel):
    login: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, max_length=100)
    server: str | None = Field(default=None, max_length=100)


@router.get("/mt5/credentials")
async def get_mt5_credentials(user: dict = Depends(require_auth)) -> dict:
    """Return the user's saved MT5 credentials (no password)."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    user_id = user.get("sub")
    if not user_id:
        return {"login": None, "server": None, "connected": False}
    try:
        res = client.table("mt5_credentials").select("login, server, connected, automated_trading_enabled, last_error, last_connected_at").eq("user_id", user_id).maybe_single().execute()
        if res.data:
            return res.data
    except Exception as e:
        logger.warning("Failed to fetch MT5 credentials: %s", e)
    return {"login": None, "server": None, "connected": False}


@router.post("/mt5/credentials")
async def save_mt5_credentials(req: MT5CredentialsUpdate, user: dict = Depends(require_auth)) -> dict:
    """Save full MT5 credentials (used by web signup page). Password is encrypted."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    user_id = user.get("sub")
    if not user_id:
        return {"error": "not authenticated"}
    if not req.login or not req.password:
        return {"error": "login and password required"}
    if not req.server:
        return {"error": "server is required"}
    try:
        is_demo = "demo" in req.server.lower()
        account_type = "demo" if is_demo else "real"

        existing = client.table("mt5_credentials").select("server").eq("user_id", user_id).execute()
        if existing.data:
            same_type = [
                e for e in existing.data
                if ("demo" in (e.get("server") or "").lower()) == is_demo
                and (e.get("server") or "") != req.server
            ]
            if same_type:
                return {"error": f"You can only connect one {account_type} account. Disconnect the existing one first."}

        from brain.utils.crypto import encrypt_password
        data: dict[str, Any] = {
            "user_id": user_id,
            "login": req.login,
            "password": encrypt_password(req.password),
            "server": req.server,
        }
        client.table("mt5_credentials").upsert(data, on_conflict="user_id, login, server").execute()
        return {"status": "saved"}
    except Exception as e:
        logger.warning("Failed to save MT5 credentials: %s", e)
        return {"error": str(e)}


@router.put("/mt5/credentials")
async def update_mt5_credentials(req: MT5CredentialsUpdate, user: dict = Depends(require_auth)) -> dict:
    """Update MT5 server selection and optionally test connection."""
    client = get_client()
    if not client:
        return {"error": "Supabase not configured"}
    user_id = user.get("sub")
    if not user_id:
        return {"error": "not authenticated"}
    updates: dict[str, Any] = {}
    if req.server is not None:
        updates["server"] = req.server
    try:
        client.table("mt5_credentials").update(updates).eq("user_id", user_id).execute()
        return {"status": "updated"}
    except Exception as e:
        logger.warning("Failed to update MT5 credentials: %s", e)
        return {"error": str(e)}


@router.get("/trades/export")
async def export_trades(
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    limit: int = Query(200, ge=1, le=10000),
    user: dict = Depends(require_auth),
) -> StreamingResponse:
    user_id = user.get("sub")
    trades = get_recent_trades(limit=limit, user_id=user_id)

    if format == "pdf":
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        from reportlab.lib import colors
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        data = [["Ticket", "Pair", "Direction", "Entry", "SL", "TP", "P&L", "Time"]]
        for t in trades:
            data.append([
                t.get("ticket", ""), t.get("pair", ""), t.get("direction", ""),
                str(t.get("entry_price", "")), str(t.get("sl_price", "")), str(t.get("tp_price", "")),
                str(t.get("pnl", "")), str(t.get("closed_at", "")),
            ])
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        doc.build([table])
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=trade_history.pdf"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket", "Pair", "Direction", "Entry", "SL", "TP", "P&L", "Close Time"])
    for t in trades:
        writer.writerow([
            t.get("ticket", ""), t.get("pair", ""), t.get("direction", ""),
            t.get("entry_price", ""), t.get("sl_price", ""), t.get("tp_price", ""),
            t.get("pnl", ""), t.get("closed_at", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trade_history.csv"},
    )
