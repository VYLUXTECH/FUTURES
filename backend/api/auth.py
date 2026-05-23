from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from backend.db.supabase import sign_up, sign_in, sign_out, get_user
from backend.api.middleware import get_current_user, require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth")

_rate_limit: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    _rate_limit[ip].append(now)


class SignUpRequest(BaseModel):
    email: str
    password: str


class SignInRequest(BaseModel):
    email: str
    password: str


@router.post("/signup")
async def register(req: SignUpRequest, request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    result = await sign_up(req.email, req.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/login")
async def login(req: SignInRequest, request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    result = await sign_in(req.email, req.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@router.post("/signout")
async def logout(user: dict = Depends(get_current_user)) -> dict:
    token = user.get("access_token", "")
    await sign_out(token)
    return {"status": "signed_out"}


class ForgotPasswordRequest(BaseModel):
    email: str


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    try:
        from backend.db.supabase import get_client
        client = get_client()
        if client:
            client.auth.reset_password_for_email(req.email)
        return {"status": "sent"}
    except Exception as exc:
        logger.warning("Forgot password error: %s", exc)
        return {"status": "sent"}


@router.get("/user")
async def user_info(user: dict = Depends(require_auth)) -> dict:
    return {"user": user}
