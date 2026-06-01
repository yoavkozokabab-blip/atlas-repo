"""JARVIS Desktop — Repository Intelligence Platform (Phase 107 product MVP).

An additive product shell around the existing Builder Core engine. It adds a
local desktop web app (stdlib server + static SPA) and a framework-agnostic API
core. It does not modify Builder Core, detectors, the CLI, or existing tests.

Positioning: JARVIS prepares your codebase for AI. It does not replace
Claude/Codex/Cursor — it makes them understand repositories faster, cheaper, and
with better evidence.
"""

from __future__ import annotations

PRODUCT_NAME = "JARVIS"
PRODUCT_TAGLINE = "Repository Intelligence Platform"
PRODUCT_VERSION = "phase107-mvp"

__all__ = ["PRODUCT_NAME", "PRODUCT_TAGLINE", "PRODUCT_VERSION"]
