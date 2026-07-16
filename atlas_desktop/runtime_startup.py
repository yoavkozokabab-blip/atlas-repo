"""Authenticated local runtime discovery for the Atlas desktop server."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .data_paths import desktop_data_dir
from .persistence import load_persistence_secret

PROTOCOL = "atlas-desktop-runtime-v1"
PRODUCT = "Atlas Desktop"
PREFERRED_PORT = 8777
FALLBACK_PORT_START = 8778
FALLBACK_PORT_END = 8797
RESERVED_PORTS = frozenset({8788})
HANDSHAKE_PATH = "/api/runtime/handshake"
DESCRIPTOR_FILENAME = "runtime.json"


def controlled_ports(preferred: int = PREFERRED_PORT) -> List[int]:
    """Return the bounded candidate set, excluding the accounts sidecar."""
    out: List[int] = []
    if preferred > 0 and preferred not in RESERVED_PORTS:
        out.append(int(preferred))
    for port in range(FALLBACK_PORT_START, FALLBACK_PORT_END + 1):
        if port not in RESERVED_PORTS and port not in out:
            out.append(port)
    return out


def _secret(data_dir: Optional[str] = None) -> bytes:
    return load_persistence_secret(data_dir or desktop_data_dir())


def _handshake_message(challenge: str, port: int, pid: int, instance_id: str) -> bytes:
    return f"{PROTOCOL}|{challenge}|{port}|{pid}|{instance_id}".encode("utf-8")


def handshake_payload(
    challenge: str,
    *,
    port: int,
    pid: Optional[int] = None,
    instance_id: str,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    safe_challenge = str(challenge or "")[:256]
    actual_pid = int(pid or os.getpid())
    proof = hmac.new(
        _secret(data_dir),
        _handshake_message(safe_challenge, int(port), actual_pid, instance_id),
        hashlib.sha256,
    ).hexdigest()
    return {
        "ok": True,
        "product": PRODUCT,
        "protocol": PROTOCOL,
        "challenge": safe_challenge,
        "port": int(port),
        "pid": actual_pid,
        "instance_id": instance_id,
        "proof": proof,
    }


def verify_handshake(
    payload: Dict[str, Any], challenge: str, port: int, *, data_dir: Optional[str] = None
) -> bool:
    try:
        if payload.get("product") != PRODUCT or payload.get("protocol") != PROTOCOL:
            return False
        if payload.get("challenge") != challenge or int(payload.get("port")) != int(port):
            return False
        pid = int(payload.get("pid"))
        instance_id = str(payload.get("instance_id") or "")
        proof = str(payload.get("proof") or "")
        if not instance_id or not proof:
            return False
        expected = hmac.new(
            _secret(data_dir),
            _handshake_message(challenge, int(port), pid, instance_id),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(proof, expected)
    except (TypeError, ValueError, OSError):
        return False


def probe_atlas(
    host: str,
    port: int,
    *,
    timeout: float = 0.35,
    attempts: int = 1,
    retry_delay: float = 0.08,
    data_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return verified Atlas identity; foreign and malformed listeners are None."""
    challenge = secrets.token_urlsafe(24)
    query = urllib.parse.urlencode({"challenge": challenge})
    url = f"http://{host}:{int(port)}{HANDSHAKE_PATH}?{query}"
    count = max(1, int(attempts))
    for attempt in range(count):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                if int(getattr(response, "status", response.getcode())) != 200:
                    raise OSError("handshake status was not 200")
                payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict) and verify_handshake(
                payload, challenge, int(port), data_dir=data_dir
            ):
                return payload
            return None
        except (OSError, ValueError, json.JSONDecodeError):
            if attempt + 1 < count:
                time.sleep(max(0.0, retry_delay))
    return None


def runtime_descriptor_path(data_dir: Optional[str] = None) -> str:
    return os.path.join(data_dir or desktop_data_dir(), DESCRIPTOR_FILENAME)


def _descriptor_payload(identity: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "product": PRODUCT,
        "protocol": PROTOCOL,
        "port": int(identity["port"]),
        "pid": int(identity["pid"]),
        "instance_id": str(identity["instance_id"]),
        # Kept only in the user-scoped, HMAC-protected runtime descriptor so a
        # second Atlas launcher for the same installed user can open an already
        # running instance. It is never returned by HTTP status or handshake APIs.
        "runtime_token": str(identity["runtime_token"]),
        "started_at": str(identity.get("started_at") or ""),
    }


def _descriptor_proof(payload: Dict[str, Any], data_dir: Optional[str] = None) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_secret(data_dir), blob, hashlib.sha256).hexdigest()


def write_runtime_descriptor(identity: Dict[str, Any], *, data_dir: Optional[str] = None) -> str:
    root = data_dir or desktop_data_dir()
    os.makedirs(root, exist_ok=True)
    payload = _descriptor_payload(identity)
    record = {**payload, "proof": _descriptor_proof(payload, root)}
    path = runtime_descriptor_path(root)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True)
    os.replace(tmp, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def read_runtime_descriptor(*, data_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    root = data_dir or desktop_data_dir()
    try:
        with open(runtime_descriptor_path(root), encoding="utf-8") as handle:
            record = json.load(handle)
        payload = _descriptor_payload(record)
        if not hmac.compare_digest(str(record.get("proof") or ""), _descriptor_proof(payload, root)):
            return None
        return record
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def new_instance_identity(port: int) -> Dict[str, Any]:
    return {
        "product": PRODUCT,
        "protocol": PROTOCOL,
        "port": int(port),
        "pid": os.getpid(),
        "instance_id": secrets.token_urlsafe(24),
        "runtime_token": secrets.token_urlsafe(32),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
