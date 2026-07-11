"""With-Atlas benchmark adapter."""

from __future__ import annotations

from .base import AdapterInstructions, AtlasConditionAdapter


class AtlasAdapter(AtlasConditionAdapter):
    name = "atlas"
    atlas_enabled = True

    def instructions(self) -> AdapterInstructions:
        return AdapterInstructions(
            name=self.name,
            atlas_enabled=True,
            environment={"ATLAS_BENCH_ATLAS_ENABLED": "1"},
            checklist=(
                "Start a fresh agent session.",
                "Enable Atlas MCP before submitting the prompt.",
                "Confirm Atlas tools are visible/available.",
                "Do not paste Atlas output manually into the prompt.",
                "Record every Atlas MCP call and Atlas latency if visible.",
            ),
        )
