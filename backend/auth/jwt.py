from __future__ import annotations

import os
import time

from jose import jwt, JWTError

JWT_SECRET: str = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 86400  # 24 hours


def _get_secret() -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET not set in environment")
    return JWT_SECRET


def create_access_token(user_id: str, email: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
        if "sub" not in payload:
            return None
        return payload
    except JWTError:
        return None
