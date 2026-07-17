"""Environment-only JWT signing secret for the accounts service."""
from __future__ import annotations

import os
def load_jwt_secret() -> str:
    """Return a configured signer secret; never read or create secret files."""
    for key in ("ATLAS_AUTH_JWT_SECRET", "ATLAS_JWT_SECRET"):
        value = (os.environ.get(key) or "").strip()
        if value:
            if len(value) < 32:
                raise RuntimeError(f"{key} must contain at least 32 characters")
            return value
    raise RuntimeError("ATLAS_AUTH_JWT_SECRET is required; file-backed JWT secrets are disabled")
