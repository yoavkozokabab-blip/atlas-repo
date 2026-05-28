"""Skill system — metadata and help over allowlisted intents."""

from __future__ import annotations

from skills.code_skill import CodeSkill
from skills.diagnostics_skill import DiagnosticsSkill
from skills.computer_control_skill import ComputerControlSkill
from skills.services_skill import ServicesSkill
from skills.workflows_skill import WorkflowsSkill
from skills.files_skill import FilesSkill
from skills.memory_skill import MemorySkill
from skills.productivity_skill import ProductivitySkill
from skills.registry import SkillRegistry, get_skill_registry, reset_skill_registry
from skills.system_skill import SystemSkill
from skills.trading_skill import LogsSkill, TradingSkill
from skills.vision_skill import VisionSkill
from skills.websites_skill import WebsitesSkill


def bootstrap_skills(registry: SkillRegistry) -> None:
    """Register all built-in skills."""
    for skill_cls in (
        TradingSkill,
        LogsSkill,
        CodeSkill,
        FilesSkill,
        SystemSkill,
        ProductivitySkill,
        MemorySkill,
        VisionSkill,
        DiagnosticsSkill,
        WorkflowsSkill,
        ServicesSkill,
        ComputerControlSkill,
        WebsitesSkill,
    ):
        registry.register_skill(skill_cls().metadata())


__all__ = [
    "get_skill_registry",
    "reset_skill_registry",
    "bootstrap_skills",
]
