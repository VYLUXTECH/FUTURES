from __future__ import annotations

import logging
import os

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
async def root() -> dict:
    return {"message": "THE DISCIPLE Trading Bot API is running"}


@router.get("/api/config")
async def client_config() -> dict:
    """Public config for frontend — no auth required."""
    return {}
