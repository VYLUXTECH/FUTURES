# ============================================================
# FuturesBrain v1.0 – Centralised Logger
# Call setup_logging() ONCE from main.py. All other modules
# just use logging.getLogger(__name__).
# ============================================================
from __future__ import annotations

import logging
import sys
from config.settings import LOG_LEVEL, BASE_DIR


def setup_logging() -> None:
    """Configure root logger. Must be called exactly once at startup."""
    log_file = BASE_DIR / "logs" / "futuresbrain.log"

    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # Only configure if not already set up (prevents duplicate handlers)
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, date_fmt))

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(fmt, date_fmt))

    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "aiohttp", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
