"""JWT signing secret resolution for the accounts service.

Resolution order:

1. ``ATLAS_AUTH_JWT_SECRET`` / ``ATLAS_JWT_SECRET`` environment variables —
   explicit synthetic values for development and tests only. Packaged
   production never requires users to configure these.
2. The per-installation :class:`LocalSigningKeyStore` — 256 bits of
   cryptographically random key material generated on first launch, stored
   DPAPI-protected (CurrentUser) in the per-user Atlas data directory.

There is no shipped default secret and no file-backed plaintext fallback
outside the protected store. Secret values are never logged.
"""
from __future__ import annotations

import os

from .signing_key_store import default_store


def load_jwt_secret() -> str:
    """Return the signing secret; generate the per-install key if needed."""
    for key in ("ATLAS_AUTH_JWT_SECRET", "ATLAS_JWT_SECRET"):
        value = (os.environ.get(key) or "").strip()
        if value:
            if len(value) < 32:
                raise RuntimeError(f"{key} must contain at least 32 characters")
            return value
    return default_store().as_jwt_secret()


def current_key_fingerprint() -> str:
    """Non-secret fingerprint of the active signing key (for token binding).

    When an explicit environment secret is used, the fingerprint is derived
    from that secret so tokens remain bound to the active key either way.
    """
    import hashlib

    for key in ("ATLAS_AUTH_JWT_SECRET", "ATLAS_JWT_SECRET"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return hashlib.sha256(b"atlas-env-fp:" + value.encode("utf-8")).hexdigest()[:16]
    fp = default_store().fingerprint()
    if fp is None:
        # Creating the key also creates the fingerprint deterministically.
        default_store().load_or_create()
        fp = default_store().fingerprint() or ""
    return fp
