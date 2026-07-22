"""Windows user-scoped protected storage for Atlas desktop credentials.

The encrypted blob is only decryptable by the Windows user that created it.
No application-managed encryption key is generated, stored, or shipped.
"""
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from typing import Any, Dict


_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_DESCRIPTION = "Atlas Desktop account credentials"
_FORMAT_VERSION = 1


class ProtectedStorageError(RuntimeError):
    """Raised when credentials cannot be protected or recovered safely."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _input_blob(value: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(value)
    blob = _DataBlob(
        len(value),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _windows_libraries() -> tuple[Any, Any]:
    if os.name != "nt":
        raise ProtectedStorageError("Windows protected storage is unavailable")
    try:
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError) as exc:
        raise ProtectedStorageError("Windows protected storage is unavailable") from exc
    return crypt32, kernel32


def protect_bytes(value: bytes) -> bytes:
    """Protect bytes with DPAPI's current-user scope."""
    crypt32, kernel32 = _windows_libraries()
    source, source_buffer = _input_blob(value)
    destination = _DataBlob()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        _DESCRIPTION,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(destination),
    ):
        raise ProtectedStorageError("Windows could not protect Atlas credentials")
    del source_buffer
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)


def unprotect_bytes(value: bytes) -> bytes:
    """Recover bytes protected by the current Windows user."""
    crypt32, kernel32 = _windows_libraries()
    source, source_buffer = _input_blob(value)
    destination = _DataBlob()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(destination),
    ):
        raise ProtectedStorageError("Atlas credentials cannot be recovered by this Windows user")
    del source_buffer
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)


def encode_credentials(credentials: Dict[str, Any]) -> bytes:
    payload = {"version": _FORMAT_VERSION, "credentials": credentials}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return protect_bytes(raw)


def decode_credentials(blob: bytes) -> Dict[str, Any]:
    try:
        payload = json.loads(unprotect_bytes(blob).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtectedStorageError("Atlas credential data is corrupted") from exc
    if not isinstance(payload, dict) or payload.get("version") != _FORMAT_VERSION:
        raise ProtectedStorageError("Atlas credential format is unsupported")
    credentials = payload.get("credentials")
    if not isinstance(credentials, dict):
        raise ProtectedStorageError("Atlas credential data is corrupted")
    return credentials
