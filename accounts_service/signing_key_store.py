"""Per-installation JWT signing-key store for the local accounts service.

Every Atlas installation generates its own 256-bit signing key on first
launch and stores it inside the current user's Atlas application-data
directory. On Windows the key material is wrapped with DPAPI
(CryptProtectData, CurrentUser scope) so only the same Windows user on the
same machine can unwrap it; elsewhere the file falls back to raw bytes with
owner-only permissions. There is no shipped default key, and key material is
never logged, returned by an API, or included in analytics — only the
non-secret fingerprint may be surfaced.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Optional

_MAGIC = b"ATLAS-SK1\x00"
_METHOD_DPAPI = b"D"
_METHOD_RAW = b"R"
_KEY_BYTES = 32  # 256 bits
# DPAPI optional entropy: domain separation only (NOT a secret, NOT a key —
# DPAPI's protection comes from the Windows user's credentials).
_DPAPI_CONTEXT = b"atlas-accounts-signing-key-v1"

KEY_FILE_NAME = "signing_key.v1.bin"


def _dpapi_available() -> bool:
    return sys.platform == "win32"


def _dpapi_protect(data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(raw: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    inp = _blob(data)
    entropy = _blob(_DPAPI_CONTEXT)
    out = DATA_BLOB()
    # CRYPTPROTECT_UI_FORBIDDEN = 0x1 — never show UI from a background service.
    if not crypt32.CryptProtectData(
        ctypes.byref(inp), None, ctypes.byref(entropy), None, None, 0x1, ctypes.byref(out)
    ):
        raise OSError("DPAPI CryptProtectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _dpapi_unprotect(blob: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(raw: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    inp = _blob(blob)
    entropy = _blob(_DPAPI_CONTEXT)
    out = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(inp), None, ctypes.byref(entropy), None, None, 0x1, ctypes.byref(out)
    ):
        raise OSError("DPAPI CryptUnprotectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


class LocalSigningKeyStore:
    """Load/create/rotate the per-installation signing key.

    The key lives at ``<directory>/signing_key.v1.bin``. File format:
    ``ATLAS-SK1\\x00`` + method byte (``D`` DPAPI / ``R`` raw) + payload.
    """

    def __init__(self, directory: os.PathLike | str):
        self.directory = Path(directory)
        self.path = self.directory / KEY_FILE_NAME

    # ── primitives ─────────────────────────────────────────────────────────
    def load(self) -> Optional[bytes]:
        """Return the stored key, or None if absent/unreadable-as-ours."""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return None
        if not raw.startswith(_MAGIC) or len(raw) <= len(_MAGIC) + 1:
            return None
        method = raw[len(_MAGIC):len(_MAGIC) + 1]
        payload = raw[len(_MAGIC) + 1:]
        if method == _METHOD_DPAPI:
            key = _dpapi_unprotect(payload)
        elif method == _METHOD_RAW:
            key = payload
        else:
            return None
        if len(key) < _KEY_BYTES:
            return None
        return key

    def create(self) -> bytes:
        """Generate and persist a fresh 256-bit key (atomic write)."""
        key = secrets.token_bytes(_KEY_BYTES)
        if _dpapi_available():
            body = _MAGIC + _METHOD_DPAPI + _dpapi_protect(key)
        else:
            body = _MAGIC + _METHOD_RAW + key
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.directory), prefix=".sk-", suffix=".tmp")
        try:
            os.write(fd, body)
            os.close(fd)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return key

    def load_or_create(self) -> bytes:
        key = self.load()
        if key is not None:
            return key
        return self.create()

    def rotate(self) -> bytes:
        """Force a new key (invalidates everything signed by the old one)."""
        return self.create()

    def delete(self) -> None:
        """Explicit reset/uninstall policy only — never called at runtime."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def fingerprint(self) -> Optional[str]:
        """Non-secret identifier of the current key (safe for logs/markers)."""
        key = self.load()
        if key is None:
            return None
        return hashlib.sha256(b"atlas-sk-fp:" + key).hexdigest()[:16]

    # ── convenience ────────────────────────────────────────────────────────
    def as_jwt_secret(self) -> str:
        """The key encoded for HS256 use. Never log this value."""
        return base64.urlsafe_b64encode(self.load_or_create()).decode("ascii")


def default_store() -> LocalSigningKeyStore:
    """Store rooted in the service's per-user data directory.

    ``ATLAS_ACCOUNTS_DATA_DIR`` is set by the desktop supervisor (and by
    tests); the ``auth`` subfolder keeps key material separate from the
    SQLite database so copying only the database never transfers trust.
    """
    base = (os.environ.get("ATLAS_ACCOUNTS_DATA_DIR") or "").strip()
    if not base:
        base = os.getcwd()
    return LocalSigningKeyStore(Path(base) / "auth")
