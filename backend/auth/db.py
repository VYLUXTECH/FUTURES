from __future__ import annotations

import logging
import uuid

from brain.config.settings import SUPABASE_DB_URI

logger = logging.getLogger(__name__)

try:
    import psycopg2
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False


def _get_conn(uri: str | None = None):
    if not _PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not available")
    uri = uri or SUPABASE_DB_URI
    if not uri:
        raise RuntimeError("SUPABASE_DB_URI not configured")
    return psycopg2.connect(uri, connect_timeout=10, options="-c statement_timeout=8000")


def ensure_users_table(uri: str | None = None) -> None:
    """Create users table if it doesn't exist."""
    conn = _get_conn(uri)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email         VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    display_name  VARCHAR(255) DEFAULT '',
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
        logger.info("users table ready")
    except Exception as exc:
        logger.warning("ensure_users_table error: %s", exc)
    finally:
        conn.close()


def create_user(email: str, password_hash: str, display_name: str = "") -> dict | None:
    """Create a new user. Returns the user dict or None on error."""
    user_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, email, password_hash, display_name) VALUES (%s, %s, %s, %s) RETURNING id, email, display_name, created_at",
                (user_id, email.lower().strip(), password_hash, display_name),
            )
            row = cur.fetchone()
            conn.commit()
            if row:
                # Also create a profiles row so the rest of the app works
                cur.execute(
                    "INSERT INTO profiles (id, display_name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                    (row[0], display_name or "Trader"),
                )
                conn.commit()
                return {"id": str(row[0]), "email": row[1], "display_name": row[2], "created_at": str(row[3])}
    except Exception as exc:
        logger.warning("create_user error: %s", exc)
        return None
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash, display_name, created_at FROM users WHERE email = %s",
                (email.lower().strip(),),
            )
            row = cur.fetchone()
            if row:
                return {"id": str(row[0]), "email": row[1], "password_hash": row[2], "display_name": row[3], "created_at": str(row[4])}
    except Exception as exc:
        logger.warning("get_user_by_email error: %s", exc)
    finally:
        conn.close()
    return None


def get_user_by_id(user_id: str) -> dict | None:
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, display_name, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return {"id": str(row[0]), "email": row[1], "display_name": row[2], "created_at": str(row[3])}
    except Exception as exc:
        logger.warning("get_user_by_id error: %s", exc)
    finally:
        conn.close()
    return None


def update_password(user_id: str, password_hash: str) -> bool:
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
            conn.commit()
            return cur.rowcount > 0
    except Exception as exc:
        logger.warning("update_password error: %s", exc)
        return False
    finally:
        conn.close()
