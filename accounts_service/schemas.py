"""Atlas Accounts Service — Pydantic v2 request/response schemas."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict, model_validator


ProfileUse = Literal["personal", "work", "both"]
CompanySize = Literal["just_me", "2_10", "11_50", "51_200", "201_1000", "1000_plus", "prefer_not_to_say"]
DeveloperExperience = Literal["lt_1", "1_2", "3_5", "6_10", "10_plus"]
PrimaryRole = Literal[
    "student", "frontend", "backend", "full_stack", "devops_platform",
    "engineering_manager", "founder", "other",
]
CodingTool = Literal["claude", "cursor", "codex", "github_copilot", "windsurf", "other"]
RepoSize = Literal["small", "medium", "large", "very_large", "not_sure"]
AtlasHelp = Literal[
    "understand_codebases", "planning_changes", "debugging", "what_breaks",
    "reduce_context", "onboarding", "other",
]

_PROFILE_SENSITIVE_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|token|bearer|ghp_|github_pat_|sk-[a-z0-9_-]+|[a-z]:\\|/home/|/users/|def\s+|class\s+|function\s+)",
    re.IGNORECASE,
)


def _clean_optional_profile_text(value: Optional[str], *, max_len: int) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > max_len:
        raise ValueError(f"Must be {max_len} characters or fewer")
    if _PROFILE_SENSITIVE_PATTERN.search(text):
        raise ValueError("Do not include secrets, code, repository names, or local paths")
    return text


class BetaProfileCreate(BaseModel):
    currently_developer: bool
    project_use: ProfileUse
    company_name: Optional[str] = None
    company_size: CompanySize
    developer_experience: DeveloperExperience
    primary_role: PrimaryRole
    coding_tools: List[CodingTool]
    languages_frameworks: Optional[str] = None
    repo_size: RepoSize
    atlas_help: List[AtlasHelp]
    notes: Optional[str] = None

    @field_validator("company_name")
    @classmethod
    def clean_company_name(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_profile_text(v, max_len=120)

    @field_validator("languages_frameworks")
    @classmethod
    def clean_languages(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_profile_text(v, max_len=500)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_profile_text(v, max_len=1000)

    @field_validator("coding_tools", "atlas_help")
    @classmethod
    def non_empty_lists(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Select at least one option")
        if len(v) > 8:
            raise ValueError("Too many selections")
        return v


class BetaProfileOut(BetaProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    profile_id: str
    created_at: datetime
    updated_at: datetime


# ── Auth ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: Optional[str] = None
    device_id: str
    app_version: str = "unknown"
    platform: str = "unknown"
    beta_profile: Optional[BetaProfileCreate] = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 1024:
            raise ValueError("Password too long")
        return v

    @field_validator("confirm_password")
    @classmethod
    def confirm_password_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 1024:
            raise ValueError("Password too long")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: str
    app_version: str = "unknown"
    platform: str = "unknown"


class RefreshRequest(BaseModel):
    refresh_token: str
    device_id: str


class LogoutRequest(BaseModel):
    refresh_token: str


# ── User ───────────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    status: str
    role: str
    beta_flag: bool
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    beta_profile: Optional[BetaProfileOut] = None


class LicenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    license_id: str
    plan: str
    status: str
    expires_at: Optional[datetime] = None
    max_devices: int


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    app_version: str
    platform: str
    first_seen_at: datetime
    last_seen_at: datetime
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    license: Optional[LicenseOut] = None


class LicenseCheckResponse(BaseModel):
    valid: bool
    plan: str
    status: str
    expires_at: Optional[datetime] = None
    max_devices: int
    beta_features: bool
    message: Optional[str] = None


# ── Usage/analytics ────────────────────────────────────────────────────────
class UsageEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    event_type: str
    app_version: str = "unknown"
    date: Optional[str] = None  # YYYY-MM-DD; server uses today if absent

    # Numeric counters only — no strings carrying code/paths
    launches: int = 0
    scans: int = 0
    change_plans: int = 0
    debug_runs: int = 0
    what_breaks_runs: int = 0
    exports: int = 0
    estimated_tokens_saved: int = 0

    @field_validator(
        "launches", "scans", "change_plans", "debug_runs",
        "what_breaks_runs", "exports", "estimated_tokens_saved",
        mode="before",
    )
    @classmethod
    def non_negative(cls, v: int) -> int:
        v = int(v)
        if v < 0:
            raise ValueError("Counter fields must be non-negative integers")
        return v


# ── Admin ──────────────────────────────────────────────────────────────────
class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    status: str
    role: str
    beta_flag: bool
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    admin_notes: Optional[str] = None
    license: Optional[LicenseOut] = None
    device_count: int = 0
    beta_profile: Optional[BetaProfileOut] = None


class AdminUserUpdate(BaseModel):
    status: Optional[Literal["pending", "active", "beta", "suspended", "banned", "expired"]] = None
    role: Optional[Literal["user", "admin", "superadmin"]] = None
    beta_flag: Optional[bool] = None
    plan: Optional[Literal["beta", "free", "pro", "enterprise"]] = None
    max_devices: Optional[int] = None
    expires_at: Optional[datetime] = None
    admin_notes: Optional[str] = None

    @field_validator("max_devices")
    @classmethod
    def max_devices_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("max_devices must be at least 1")
        return v


class AdminDashboard(BaseModel):
    total_users: int
    active_users: int
    beta_users: int
    suspended_users: int
    banned_users: int
    active_devices: int
    launches_today: int
    scans_today: int
    exports_today: int
    tokens_saved_today: int
    feedback_pending: int


class AdminAuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action_id: str
    admin_email: str
    action: str
    target_user_email: Optional[str] = None
    target_device_id: Optional[str] = None
    created_at: datetime


# ── Feedback ───────────────────────────────────────────────────────────────
class FeedbackCreate(BaseModel):
    category: str = "general"
    message: str
    contact_email: Optional[EmailStr] = None

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        text = (v or "").strip()
        if len(text) < 3:
            raise ValueError("Message must be at least 3 characters")
        if len(text) > 4000:
            raise ValueError("Message too long")
        return text


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: str
    category: str
    message_redacted: str
    created_at: datetime
    status: str
