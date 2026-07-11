"""Atlas condition adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterInstructions:
    name: str
    atlas_enabled: bool
    checklist: tuple[str, ...]
    environment: dict[str, str]


class AtlasConditionAdapter:
    name = "base"
    atlas_enabled = False

    def instructions(self) -> AdapterInstructions:
        raise NotImplementedError
