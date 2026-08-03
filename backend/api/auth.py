from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.auth import (
    create_access_token, hash_password, verify_password,
    create_user, get_user_by_email,
)
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
    display_name: str = ""


class SignInRequest(BaseModel):
    email: str
    password: str


class ResetPasswordRequest(BaseModel):
    password: str


@router.post("/signup")
async def signup(req: SignUpRequest, request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")

    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    pw_hash = hash_password(req.password)
    user = create_user(req.email, pw_hash, req.display_name)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create account")

    token = create_access_token(user["id"], user["email"])
    return {
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
async def login(req: SignInRequest, request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")

    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user["id"], user["email"])
    return {
        "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/signout")
async def signout(user: dict = Depends(require_auth)) -> dict:
    # Stateless JWT — client discards token. No server-side session to revoke.
    return {"status": "signed_out"}


@router.get("/user")
async def user_info(user: dict = Depends(require_auth)) -> dict:
    from backend.auth import get_user_by_id
    full_user = get_user_by_id(user["sub"])
    if full_user:
        return {"user": full_user}
    return {"user": {"id": user["sub"], "email": user.get("email", "")}}


@router.post("/forgot-password")
async def forgot_password(request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    # For now: in a real app you'd send an email with a reset link.
    # The token is logged to the bot log for development purposes.
    logger.info("Password reset requested — implement email sending in production")
    return {"status": "sent", "detail": "If an account exists with this email, a reset link has been sent."}


class VerifyOtpRequest(BaseModel):
    email: str
    token: str
    type: str = "recovery"


@router.post("/verify-otp")
async def verify_otp(req: VerifyOtpRequest) -> dict:
    # Placeholder: in production, verify the reset token from the email.
    # For now, accept any non-empty token for development.
    if not req.token:
        raise HTTPException(status_code=400, detail="Invalid token")
    if req.type == "recovery" and req.email:
        user = get_user_by_email(req.email)
        if user:
            token = create_access_token(user["id"], user["email"])
            return {"status": "verified", "detail": "Token accepted", "access_token": token}
    return {"status": "verified", "detail": "Token accepted"}


@router.post("/update-password")
async def update_password(req: ResetPasswordRequest, user: dict = Depends(require_auth)) -> dict:
    from backend.auth import update_password as update_pw
    pw_hash = hash_password(req.password)
    ok = update_pw(user["sub"], pw_hash)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update password")
    return {"status": "updated"}


class ResendOtpRequest(BaseModel):
    email: str


@router.post("/resend-otp")
async def resend_otp(req: ResendOtpRequest, request: Request) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    logger.info("OTP resend requested for %s — implement email sending in production", req.email)
    return {"status": "sent"}


class ConfirmRequest(BaseModel):
    token: str


@router.post("/confirm")
async def confirm_email(req: ConfirmRequest) -> dict:
    # Placeholder: in production, verify the confirmation token
    return {"status": "confirmed"}
