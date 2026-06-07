"""Atlas Accounts Service — configuration."""
from __future__ import annotations

import os

from .jwt_secret import load_jwt_secret

# ── Database ───────────────────────────────────────────────────────────────
# SQLite for development; set DATABASE_URL to a PostgreSQL URL in production.
DATABASE_URL: str = os.environ.get(
    "ATLAS_ACCOUNTS_DB",
    "sqlite:///./atlas_accounts.db",
)

# ── JWT ────────────────────────────────────────────────────────────────────
# Prefer ATLAS_AUTH_JWT_SECRET; otherwise load/create a persisted local secret.
JWT_SECRET: str = load_jwt_secret()
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
REFRESH_TOKEN_EXPIRE_DAYS: int = 30

# ── Service ────────────────────────────────────────────────────────────────
SERVICE_HOST: str = os.environ.get("ATLAS_ACCOUNTS_HOST", "127.0.0.1")
SERVICE_PORT: int = int(os.environ.get("ATLAS_ACCOUNTS_PORT", "8788"))

# CORS: localhost variants for the desktop app's browser
CORS_ORIGINS: list[str] = [
    "http://localhost:8777",
    "http://127.0.0.1:8777",
    "http://localhost:8788",
    "http://127.0.0.1:8788",
]

# ── Rate limiting ─────────────────────────────────────────────────────────
# Simple in-memory sliding window (dev). In production: Redis.
LOGIN_RATE_LIMIT_PER_15MIN: int = 5
REGISTER_RATE_LIMIT_PER_HOUR: int = 10

# ── Offline grace ─────────────────────────────────────────────────────────
OFFLINE_GRACE_DAYS: int = int(os.environ.get("ATLAS_OFFLINE_GRACE_DAYS", "7"))

# ── Admin ─────────────────────────────────────────────────────────────────
# Set to comma-separated emails of initial superadmins (bootstrapping only).
INITIAL_ADMINS: list[str] = [
    e.strip()
    for e in os.environ.get("ATLAS_INITIAL_ADMINS", "").split(",")
    if e.strip()
]
