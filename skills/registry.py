"""Skill registry — organization and help only; no execution bypass."""

from __future__ import annotations

from skills.base import SkillAction, SkillMetadata


class SkillRegistryError(Exception):
    """Invalid skill registration or lookup."""


class SkillRegistry:
    """Register skills and actions for discovery / help."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillMetadata] = {}
        self._actions: dict[str, SkillAction] = {}
        self._alias_to_skill: dict[str, str] = {}

    def register_skill(self, skill_metadata: SkillMetadata) -> None:
        name = skill_metadata.name
        if name in self._skills:
            raise SkillRegistryError(f"Duplicate skill: {name}")
        self._skills[name] = skill_metadata
        for alias in skill_metadata.aliases:
            key = alias.strip().lower()
            if key in self._alias_to_skill and self._alias_to_skill[key] != name:
                raise SkillRegistryError(f"Duplicate skill alias: {alias}")
            self._alias_to_skill[key] = name
        self._alias_to_skill[name.lower()] = name

        for act in skill_metadata.actions:
            self._register_action(act)

    def _register_action(self, act: SkillAction) -> None:
        if act.name in self._actions:
            raise SkillRegistryError(f"Duplicate skill action name: {act.name}")
        self._actions[act.name] = act

    def list_skills(self) -> list[SkillMetadata]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    def list_actions(self) -> list[SkillAction]:
        return sorted(self._actions.values(), key=lambda a: a.name)

    def get_skill(self, name_or_alias: str) -> SkillMetadata | None:
        key = name_or_alias.strip().lower()
        skill_name = self._alias_to_skill.get(key)
        if skill_name:
            return self._skills.get(skill_name)
        for meta in self._skills.values():
            if key in meta.name.lower():
                return meta
        return None

    def get_action(self, name: str) -> SkillAction | None:
        return self._actions.get(name)

    def validate_skill_action(self, name: str) -> SkillAction:
        act = self.get_action(name)
        if act is None:
            raise SkillRegistryError(f"Unknown skill action: {name}")
        return act

    def actions_for_skill(self, skill_name: str) -> list[SkillAction]:
        meta = self.get_skill(skill_name)
        return list(meta.actions) if meta else []

    def grouped_by_category(self) -> dict[str, list[SkillMetadata]]:
        groups: dict[str, list[SkillMetadata]] = {}
        for meta in self.list_skills():
            groups.setdefault(meta.category, []).append(meta)
        return groups


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Return singleton registry (bootstrapped on first use)."""
    global _registry
    if _registry is None:
        from skills import bootstrap_skills

        _registry = SkillRegistry()
        bootstrap_skills(_registry)
    return _registry


def reset_skill_registry() -> None:
    """Clear registry (tests only)."""
    global _registry
    _registry = None
