"""License client — fetches and caches Atlas subscription status.

Network access uses only the Python standard library (urllib) so this module
adds no new dependencies. All calls are best-effort: if the backend is
unreachable, the last-known cached status is used (offline fallback), and if
nothing is cached the user is treated as Free.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

# Re-check the license at most this often (seconds). 24h per spec.
CACHE_TTL_SECONDS = 24 * 60 * 60
_HTTP_TIMEOUT = 6  # seconds


def _site_url() -> str:
    """Base URL of the Atlas website/API (no trailing slash)."""
    return os.getenv("ATLAS_SITE_URL", "https://atlas.dev").rstrip("/")


def _cache_path() -> Path:
    """Where the license cache lives. Prefers the app data dir, falls back to ~."""
    override = os.getenv("ATLAS_LICENSE_CACHE")
    if override:
        return Path(override).expanduser()
    try:  # use the app's DATA_DIR when importable
        from config import DATA_DIR  # type: ignore

        return Path(DATA_DIR) / "license_cache.json"
    except Exception:
        return Path.home() / ".atlas" / "license_cache.json"


# Free-tier limits (mirrors the server's /api/license response defaults).
_FREE_ENTITLEMENTS: dict[str, Any] = {
    "max_repos": 1,
    "max_files_per_repo": 50,
    "features": {
        "dependency_graph": True,
        "impact_analysis": False,
        "context_compression": False,
        "investigation": False,
        "risk_detection": False,
        "priority_support": False,
    },
}


@dataclass
class LicenseStatus:
    """Effective license state for the current user."""

    plan: str = "free"  # free | trial | pro
    status: Optional[str] = None  # raw server status (free|trial|pro|cancelled)
    email: Optional[str] = None
    trial_end: Optional[str] = None
    current_period_end: Optional[str] = None
    trial_days_left: Optional[int] = None
    entitlements: dict[str, Any] = field(default_factory=lambda: dict(_FREE_ENTITLEMENTS))
    fetched_at: float = 0.0
    stale: bool = False  # True when served from cache after a failed refresh

    # --- convenience ---
    @property
    def is_pro(self) -> bool:
        return self.plan in ("pro", "trial")

    @property
    def is_trial(self) -> bool:
        return self.plan == "trial"

    def feature_enabled(self, name: str) -> bool:
        return bool(self.entitlements.get("features", {}).get(name, False))

    @property
    def max_files_per_repo(self) -> Optional[int]:
        return self.entitlements.get("max_files_per_repo")

    @property
    def max_repos(self) -> Optional[int]:
        return self.entitlements.get("max_repos")

    @property
    def banner(self) -> Optional[str]:
        """Banner text to show in the app, or None."""
        if self.plan == "trial":
            n = self.trial_days_left
            if n is None:
                return "Pro trial active"
            if n <= 0:
                return "Your trial ends today — add a payment method to keep Pro."
            return f"{n} day{'s' if n != 1 else ''} left in your Pro trial"
        if self.plan == "free" and self.status in ("trial", "cancelled"):
            return "Your Pro trial has ended — you're on the Free plan. Upgrade to unlock everything."
        return None

    @classmethod
    def free(cls, email: Optional[str] = None) -> "LicenseStatus":
        return cls(plan="free", status="free", email=email,
                   entitlements=dict(_FREE_ENTITLEMENTS), fetched_at=time.time())

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "LicenseStatus":
        return cls(
            plan=data.get("plan", "free"),
            status=data.get("status"),
            email=data.get("email"),
            trial_end=data.get("trial_end"),
            current_period_end=data.get("current_period_end"),
            trial_days_left=data.get("trial_days_left"),
            entitlements=data.get("entitlements") or dict(_FREE_ENTITLEMENTS),
            fetched_at=time.time(),
            stale=False,
        )


class LicenseClient:
    """Stateful client holding the current email + cached status."""

    def __init__(self) -> None:
        self._status: Optional[LicenseStatus] = None
        self._email: Optional[str] = None
        self._load_cache()

    # ---- identity ----
    def set_email(self, email: Optional[str]) -> None:
        email = (email or "").strip().lower() or None
        if email != self._email:
            self._email = email
            # Force a fresh check next time the email changes.
            if self._status:
                self._status.fetched_at = 0.0
        self._persist_cache()

    @property
    def email(self) -> Optional[str]:
        return self._email

    # ---- status access ----
    @property
    def status(self) -> LicenseStatus:
        if self._status is None:
            self._status = LicenseStatus.free(self._email)
        return self._status

    def _fresh(self) -> bool:
        return bool(self._status and (time.time() - self._status.fetched_at) < CACHE_TTL_SECONDS)

    def refresh(self, force: bool = False) -> LicenseStatus:
        """Return the license status, hitting the network at most once per TTL."""
        if not force and self._fresh():
            return self.status
        if not self._email:
            self._status = LicenseStatus.free(None)
            self._persist_cache()
            return self._status

        url = f"{_site_url()}/api/license?" + urllib.parse.urlencode({"email": self._email})
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._status = LicenseStatus.from_api(data)
            self._persist_cache()
        except Exception:
            # Offline / server error → keep last-known status but mark it stale.
            if self._status is not None:
                self._status.stale = True
            else:
                self._status = LicenseStatus.free(self._email)
                self._status.stale = True
        return self._status

    # ---- gates (delegated to gates.py to keep this file focused) ----
    def feature_gate(self, feature: str):
        from .gates import evaluate_gate

        return evaluate_gate(self, feature)

    def enforce_scan_limit(self, files):
        from .gates import enforce_scan_limit

        return enforce_scan_limit(self, files)

    # ---- analytics passthrough ----
    def track(self, event_type: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Best-effort POST to /api/track. Never raises."""
        payload = {"event_type": event_type, "metadata": metadata or {}}
        if self._email:
            payload["email"] = self._email
        body = json.dumps(payload).encode("utf-8")
        url = f"{_site_url()}/api/track"
        try:
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}, method="POST"
            )
            urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT).close()
        except Exception:
            pass  # analytics must never break the app

    # ---- cache persistence ----
    def _load_cache(self) -> None:
        path = _cache_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._email = raw.get("email")
            st = raw.get("status")
            if st:
                self._status = LicenseStatus(**st)
        except Exception:
            self._status = None

    def _persist_cache(self) -> None:
        path = _cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"email": self._email, "status": asdict(self.status)}
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass
