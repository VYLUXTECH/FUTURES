from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from backend.db.supabase import sign_up, sign_in, sign_out, get_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth")


class SignUpRequest(BaseModel):
    email: str
    password: str


class SignInRequest(BaseModel):
    email: str
    password: str


@router.post("/signup")
async def register(req: SignUpRequest) -> dict:
    result = await sign_up(req.email, req.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/signin")
async def login(req: SignInRequest) -> dict:
    result = await sign_in(req.email, req.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@router.post("/signout")
async def logout() -> dict:
    await sign_out("")
    return {"status": "signed_out"}


@router.get("/user")
async def user_info() -> dict:
    user = await get_user("")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user": user}
