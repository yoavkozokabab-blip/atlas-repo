"""Computer control data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FocusedAppInfo:
    title: str
    width: int = 0
    height: int = 0
    minimized: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "width": self.width,
            "height": self.height,
            "minimized": self.minimized,
            "error": self.error,
        }


@dataclass
class DetailedWindowInfo:
    title: str
    left: int
    top: int
    width: int
    height: int
    visible: bool
    minimized: bool
    eligible: bool = True
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "visible": self.visible,
            "minimized": self.minimized,
            "eligible": self.eligible,
            "blocked_reason": self.blocked_reason,
        }


@dataclass
class ClipboardSummary:
    text: str
    length: int
    truncated: bool = False
    redacted: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "length": self.length,
            "truncated": self.truncated,
            "redacted": self.redacted,
            "error": self.error,
        }


@dataclass
class WindowActionResult:
    success: bool
    message: str
    matched_title: str | None = None
    candidates: list[str] = field(default_factory=list)
    ambiguous: bool = False
