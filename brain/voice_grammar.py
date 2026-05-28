"""Fuzzy English voice command grammar — delegates to command_grammar (Phase 42 v2)."""

from __future__ import annotations

from brain.command_grammar import match_command_grammar_as_request as match_voice_grammar

__all__ = ["match_voice_grammar"]
