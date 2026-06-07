"""Atlas Accounts Service — password hashing, JWT, token utilities."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import sys, os
_lib = os.path.join(os.path.dirname(__file__), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

import bcrypt
import jwt

from .config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

# Precomputed hash for constant-time login when email is unknown.
_DUMMY_HASH = bcrypt.hashpw(b"dummy_constant_time_check", bcrypt.gensalt()).decode("utf-8")


def hash_password(plain: str) -> str:
    """Hash a plaintext password. Never log the input."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT access tokens ──────────────────────────────────────────────────────
def create_access_token(
    user_id: str,
    email: str,
    role: str,
    beta_flag: bool,
    plan: str = "free",
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Issue a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "beta": beta_flag,
        "plan": plan,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "aud": "atlas-api",
        "iss": "atlas-auth",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        audience="atlas-api",
        issuer="atlas-auth",
    )


# ── Refresh tokens ─────────────────────────────────────────────────────────
def generate_refresh_token() -> str:
    """Generate a cryptographically random refresh token (raw, 32 bytes hex)."""
    return secrets.token_hex(32)


def hash_token(raw_token: str) -> str:
    """SHA-256 hash a token for storage. Never store raw tokens."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


# ── Email verification / password reset tokens ────────────────────────────
def generate_email_token() -> str:
    """Generate a URL-safe random token for email verification or password reset."""
    return secrets.token_urlsafe(32)
