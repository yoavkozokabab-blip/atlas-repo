"""No-Atlas benchmark adapter."""

from __future__ import annotations

from .base import AdapterInstructions, AtlasConditionAdapter


class NoAtlasAdapter(AtlasConditionAdapter):
    name = "no_atlas"
    atlas_enabled = False

    def instructions(self) -> AdapterInstructions:
        return AdapterInstructions(
            name=self.name,
            atlas_enabled=False,
            environment={"ATLAS_BENCH_ATLAS_ENABLED": "0"},
            checklist=(
                "Start a fresh agent session.",
                "Disable Atlas MCP before submitting the prompt.",
                "Confirm Atlas tools are absent/unavailable.",
                "Do not expose Atlas-generated context packs, cached answers, or prior Atlas output.",
                "Record proof of the disabled condition in notes or screenshot/log reference.",
            ),
        )
