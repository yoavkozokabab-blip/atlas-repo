"""Phase 137A — billing-ready data models (plain dataclasses, JSON-serializable).

These describe WHO uses Atlas, WHAT they scanned, and HOW MUCH — the inputs a
future pricing/billing system would need. They carry no behaviour beyond
(de)serialization; persistence lives in :mod:`store`, plan catalogue in
:mod:`plans`.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


@dataclass
class User:
    id: str
    email: str
    name: str = ""
    role: str = "user"  # "user" | "admin"
    plan_id: str = "free"
    workspace_ids: List[str] = field(default_factory=list)
    created_ts: float = field(default_factory=_now)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "User":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class Workspace:
    id: str
    name: str
    owner_user_id: str
    member_user_ids: List[str] = field(default_factory=list)
    created_ts: float = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Workspace":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class RepositoryScan:
    id: str
    workspace_id: str
    user_id: str
    repo_path: str
    repo_name: str
    repo_size_bytes: int = 0
    files_scanned: int = 0
    modules_indexed: int = 0
    edges_indexed: int = 0
    symbols_indexed: int = 0
    scan_duration_sec: float = 0.0
    evidence_build_duration_sec: float = 0.0
    graph_size: int = 0
    cached: bool = False
    status: str = "ok"  # "ok" | "failed"
    timestamp: float = field(default_factory=_now)

    @property
    def size_bucket(self) -> str:
        f = self.files_scanned or 0
        if f >= 20000:
            return "xlarge"
        if f >= 3000:
            return "large"
        if f >= 500:
            return "medium"
        return "small"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["size_bucket"] = self.size_bucket
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RepositoryScan":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class UsageEvent:
    id: str
    user_id: str
    workspace_id: str
    action_type: str            # build | investigate | impact | export | scan | prompt
    prompt_type: str = ""       # e.g. "impact", "investigation", free-text intent
    repo_name: str = ""
    repo_path: str = ""
    estimated_token_cost: int = 0
    local_compute_cost_usd: float = 0.0
    cached: bool = False
    duration_sec: float = 0.0
    ok: bool = True
    timestamp: float = field(default_factory=_now)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UsageEvent":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class PlanLimit:
    workspaces: int = 1
    repositories: int = 3
    max_repo_size: str = "medium"        # small | medium | large | xlarge | unlimited
    scans_per_month: int = 30
    exports_per_month: int = 10
    team_features: bool = False
    admin_dashboard: bool = False
    repository_map: bool = True
    evidence_engine: bool = False
    knowledge_engine: bool = False
    export_prompts: bool = False
    sso: bool = False
    audit_logs: bool = False
    private_deployment: bool = False
    # -1 / "unlimited" express "no hard cap" without enforcing anything yet.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    id: str
    name: str
    price_display: str
    tagline: str
    features: List[str]
    limits: PlanLimit
    cta: str = "Coming soon"          # never a real payment button
    availability: str = "Coming soon"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["limits"] = self.limits.to_dict()
        return d


@dataclass
class BillingAccount:
    id: str
    user_id: str
    workspace_id: str
    plan_id: str = "free"
    status: str = "active_local"   # active_local | trial | waitlisted | none
    waitlisted: bool = False
    # Explicitly no payment fields — this is a placeholder, not a payment record.
    note: str = "Local/mock account — no payment method, no charges."
    created_ts: float = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BillingAccount":
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__ if k in d})


def new_id(prefix: str) -> str:
    return _uid(prefix)
