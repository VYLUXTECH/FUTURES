from __future__ import annotations

import logging
import os
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from jose.exceptions import JWKError

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

security = HTTPBearer(auto_error=False)


@lru_cache
def _get_jwt_secret() -> str:
    if SUPABASE_JWT_SECRET:
        return SUPABASE_JWT_SECRET
    url = f"{SUPABASE_URL}/rest/v1/"
    try:
        resp = httpx.get(url, headers={"apikey": os.getenv("SUPABASE_KEY", "")}, timeout=5)
        if resp.status_code == 401 and "www-authenticate" in resp.headers:
            header = resp.headers["www-authenticate"]
            if 'jwt_secret="' in header:
                secret = header.split('jwt_secret="')[1].split('"')[0]
                return secret
    except Exception as exc:
        logger.warning("Failed to fetch Supabase JWT secret: %s", exc)
    return ""


def decode_jwt_payload(token: str) -> dict:
    secret = _get_jwt_secret()
    if not secret:
        payload_b64 = token.split(".")[1]
        import base64
        import json
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        return payload
    except (JWTError, JWKError) as exc:
        logger.warning("JWT decode failed: %s", exc)
        return {}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None:
        return {}
    payload = decode_jwt_payload(credentials.credentials)
    if not payload or "sub" not in payload:
        return {}
    return payload


async def require_auth(
    user: dict = Depends(get_current_user),
) -> dict:
    if not user or "sub" not in user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
