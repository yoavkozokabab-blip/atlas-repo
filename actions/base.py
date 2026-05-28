"""Base action interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import CommandRequest, CommandResult


class BaseAction(ABC):
    """All actions implement this interface."""

    intent: str

    @abstractmethod
    def execute(self, request: CommandRequest) -> CommandResult:
        """Run the action and return a structured result."""
