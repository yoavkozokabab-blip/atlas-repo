"""Atlas Accounts Service — SQLAlchemy ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum,
    ForeignKey, Integer, BigInteger, String, Text, Date, JSON,
)
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for SQLite compat


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Users ──────────────────────────────────────────────────────────────────
USER_STATUSES = ("pending", "active", "beta", "suspended", "banned", "expired")
USER_ROLES = ("user", "admin", "superadmin")


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(254), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    status = Column(SAEnum(*USER_STATUSES, name="user_status"), nullable=False, default="pending")
    role = Column(SAEnum(*USER_ROLES, name="user_role"), nullable=False, default="user")
    beta_flag = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime, nullable=True)
    # nullable admin notes — never in API responses to users
    admin_notes = Column(Text, nullable=True)

    # relationships
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    license = relationship("License", back_populates="user", uselist=False, cascade="all, delete-orphan")
    usage = relationship("UsageDaily", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="user")
    beta_profile = relationship("BetaProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")

    @property
    def device_count(self) -> int:
        return len([device for device in self.devices if device.status == "active"])


# ── Devices ────────────────────────────────────────────────────────────────
DEVICE_STATUSES = ("active", "revoked")


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(36), primary_key=True)  # generated on client
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    app_version = Column(String(32), nullable=False)
    platform = Column(String(32), nullable=False, default="unknown")
    first_seen_at = Column(DateTime, nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=_utcnow)
    status = Column(SAEnum(*DEVICE_STATUSES, name="device_status"), nullable=False, default="active")
    revoked_by = Column(String(36), nullable=True)  # admin user_id

    user = relationship("User", back_populates="devices")
    sessions = relationship("Session", back_populates="device", cascade="all, delete-orphan")


# ── Licenses ───────────────────────────────────────────────────────────────
LICENSE_PLANS = ("beta", "free", "pro", "enterprise")
LICENSE_STATUSES = ("active", "expired", "suspended", "cancelled")


class License(Base):
    __tablename__ = "licenses"

    license_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    plan = Column(SAEnum(*LICENSE_PLANS, name="license_plan"), nullable=False, default="free")
    status = Column(SAEnum(*LICENSE_STATUSES, name="license_status"), nullable=False, default="active")
    expires_at = Column(DateTime, nullable=True)  # NULL = no expiry
    max_devices = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="license")


# ── Beta profile metadata ───────────────────────────────────────────────────
class BetaProfile(Base):
    __tablename__ = "beta_profiles"

    profile_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    currently_developer = Column(Boolean, nullable=False)
    project_use = Column(String(32), nullable=False)
    company_name = Column(String(120), nullable=True)
    company_size = Column(String(32), nullable=False)
    developer_experience = Column(String(32), nullable=False)
    primary_role = Column(String(64), nullable=False)
    coding_tools = Column(JSON, nullable=False, default=list)
    languages_frameworks = Column(Text, nullable=True)
    repo_size = Column(String(32), nullable=False)
    atlas_help = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="beta_profile")


# ── Sessions ───────────────────────────────────────────────────────────────
class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hex of raw token
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(64), nullable=True)

    user = relationship("User", back_populates="sessions")
    device = relationship("Device", back_populates="sessions")


# ── Email tokens ───────────────────────────────────────────────────────────
TOKEN_KINDS = ("email_verification", "password_reset")


class EmailToken(Base):
    __tablename__ = "email_tokens"

    token_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(SAEnum(*TOKEN_KINDS, name="token_kind"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


# ── Usage daily ────────────────────────────────────────────────────────────
class UsageDaily(Base):
    __tablename__ = "usage_daily"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String(36), nullable=False)  # soft FK — device may be revoked
    date = Column(Date, nullable=False, index=True)

    launches = Column(Integer, nullable=False, default=0)
    scans = Column(Integer, nullable=False, default=0)
    change_plans = Column(Integer, nullable=False, default=0)
    debug_runs = Column(Integer, nullable=False, default=0)
    what_breaks_runs = Column(Integer, nullable=False, default=0)
    exports = Column(Integer, nullable=False, default=0)
    estimated_tokens_saved = Column(BigInteger, nullable=False, default=0)

    user = relationship("User", back_populates="usage")

    __table_args__ = (
        # One row per user/device/day — upsert on conflict
        __import__("sqlalchemy").UniqueConstraint("user_id", "device_id", "date", name="uq_usage_user_device_date"),
    )


# ── Feedback ───────────────────────────────────────────────────────────────
FEEDBACK_STATUSES = ("pending", "reviewed", "closed")


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String(64), nullable=False, default="general")
    message_redacted = Column(String(2000), nullable=False)  # stripped of secrets
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    status = Column(SAEnum(*FEEDBACK_STATUSES, name="feedback_status"), nullable=False, default="pending")

    user = relationship("User", back_populates="feedback")


# ── Admin audit log ────────────────────────────────────────────────────────
class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    action_id = Column(String(36), primary_key=True, default=_uuid)
    admin_user_id = Column(String(36), nullable=False)        # denormalised
    admin_email = Column(String(254), nullable=False)          # snapshot
    action = Column(String(64), nullable=False, index=True)
    target_user_id = Column(String(36), nullable=True, index=True)
    target_user_email = Column(String(254), nullable=True)
    target_device_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    metadata_ = Column("metadata", JSON, nullable=True)


# ── Admin intake notifications ───────────────────────────────────────────────
class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    notification_id = Column(String(36), primary_key=True, default=_uuid)
    kind = Column(String(32), nullable=False, default="beta_application", index=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(254), nullable=False)
    summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    read_at = Column(DateTime, nullable=True)
