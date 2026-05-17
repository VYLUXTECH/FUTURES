from __future__ import annotations

import base64
import hashlib
import os
from cryptography.fernet import Fernet

_ENCRYPTION_KEY_ENV = "ENCRYPTION_KEY"


def _get_key() -> bytes:
    key_str = os.getenv(_ENCRYPTION_KEY_ENV)
    if key_str:
        return base64.urlsafe_b64decode(key_str)
    fallback = hashlib.sha256(b"futures-trading-bot-fallback-key-2024").digest()
    return base64.urlsafe_b64encode(fallback)


def encrypt_password(plaintext: str) -> str:
    f = Fernet(_get_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    f = Fernet(_get_key())
    return f.decrypt(encrypted.encode()).decode()
