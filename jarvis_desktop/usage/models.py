"""Phase 137A — usage event and account models."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

EVENT_TYPES = frozenset(
    {
        "scan_started",
        "scan_completed",
        "build_plan_created",
        "investigation_created",
        "impact_created",
        "export_created",
        "repository_map_opened",
    }
)


def _uid(prefix: str = "evt") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class UsageEvent:
    user_id: str
    workspace_id: str
    event_type: str
    repo_id: str = ""
    repo_path: str = ""
    repo_name: str = ""
    files_count: int = 0
    modules_count: int = 0
    edges_count: int = 0
    symbols_count: int = 0
    scan_duration_seconds: float = 0.0
    estimated_token_equivalent: int = 0
    plan: str = "FREE"
    created_at: str = field(default_factory=_now_iso)
    id: str = field(default_factory=lambda: _uid("evt"))
    ok: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "UsageEvent":
        fields = cls.__dataclass_fields__
        return cls(**{k: raw[k] for k in fields if k in raw})


@dataclass
class LocalUser:
    id: str
    email: str = "owner@localhost"
    name: str = "Local Owner"
    role: str = "user"  # user | admin
    plan: str = "FREE"
    workspace_id: str = "ws_default"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "LocalUser":
        return cls(
            id=str(raw.get("id") or "user_local_owner"),
            email=str(raw.get("email") or "owner@localhost"),
            name=str(raw.get("name") or "Local Owner"),
            role=str(raw.get("role") or "user"),
            plan=str(raw.get("plan") or "FREE").upper(),
            workspace_id=str(raw.get("workspace_id") or "ws_default"),
        )
