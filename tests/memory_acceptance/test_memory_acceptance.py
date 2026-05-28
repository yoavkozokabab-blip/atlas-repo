"""Memory acceptance suite (Phase 65 Track B)."""

from __future__ import annotations

import pytest

from memory.repair import repair_memory_store
from reliability.memory_health import run_memory_acceptance


@pytest.fixture(autouse=True)
def memory_on(monkeypatch):
    monkeypatch.setattr("config.MEMORY_ENABLED", True)


def test_repair_memory_store():
    body = repair_memory_store()
    assert "Memory store repair complete" in body


def test_memory_acceptance_suite():
    score = run_memory_acceptance()
    assert len(score.cases) >= 5
