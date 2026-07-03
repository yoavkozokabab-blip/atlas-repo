"""Atlas Desktop — Repository Intelligence Platform.

Local desktop web app (stdlib server + static SPA) and framework-agnostic API
core around the Builder Core engine.
"""

from __future__ import annotations

from .product_info import PRODUCT_VERSION as PRODUCT_VERSION

PRODUCT_NAME = "ATLAS"
PRODUCT_TAGLINE = "Repository Intelligence Platform"

__all__ = ["PRODUCT_NAME", "PRODUCT_TAGLINE", "PRODUCT_VERSION"]
