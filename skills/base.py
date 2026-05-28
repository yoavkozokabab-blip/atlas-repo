"""Skill framework — metadata and grouping over allowlisted intents."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from config import CONFIRMATION_REQUIRED_INTENTS, IMPLEMENTED_INTENTS


class SkillPermissionLevel(str, Enum):
    """How an action may be executed under security rules."""

    READ_ONLY = "read_only"
    CONFIRM_REQUIRED = "confirm_required"
    BLOCKED = "blocked"


def permission_for_intent(intent: str) -> SkillPermissionLevel:
    """Derive permission from global config (single source of truth)."""
    if intent in CONFIRMATION_REQUIRED_INTENTS:
        return SkillPermissionLevel.CONFIRM_REQUIRED
    if intent in IMPLEMENTED_INTENTS:
        return SkillPermissionLevel.READ_ONLY
    return SkillPermissionLevel.BLOCKED


@dataclass
class SkillAction:
    """
    Describes one allowlisted capability.
    Execution always goes through actions.registry + router — never handler directly.
    """

    name: str
    description: str
    examples: list[str] = field(default_factory=list)
    permission_level: SkillPermissionLevel = SkillPermissionLevel.READ_ONLY
    intent: str = ""
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)

    @property
    def handler(self) -> str:
        """Documented route: intent name → ActionRegistry (no direct call)."""
        return self.intent or self.name


@dataclass
class SkillMetadata:
    """Skill grouping for help and discovery."""

    name: str
    description: str
    category: str
    aliases: list[str] = field(default_factory=list)
    actions: list[SkillAction] = field(default_factory=list)


class BaseSkill(ABC):
    """Logical skill grouping."""

    name: str
    description: str
    category: str
    aliases: list[str]

    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            description=self.description,
            category=self.category,
            aliases=list(self.aliases),
            actions=self.build_actions(),
        )

    def build_actions(self) -> list[SkillAction]:
        """Subclasses return skill action definitions."""
        raise NotImplementedError


def action(
    intent: str,
    description: str,
    *,
    examples: list[str] | None = None,
    required_params: list[str] | None = None,
    optional_params: list[str] | None = None,
    permission: SkillPermissionLevel | None = None,
) -> SkillAction:
    """Helper to build SkillAction with permission from config."""
    return SkillAction(
        name=intent,
        intent=intent,
        description=description,
        examples=examples or [],
        permission_level=permission or permission_for_intent(intent),
        required_params=required_params or [],
        optional_params=optional_params or [],
    )
