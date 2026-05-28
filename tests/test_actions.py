"""Tests for action helpers."""

from pathlib import Path

import pytest

from actions.powershell import run_allowlisted_script
from config import ALLOWED_POWERSHELL_SCRIPTS


def test_allowlisted_script_rejects_unknown(tmp_path: Path):
    bad = tmp_path / "evil.ps1"
    bad.write_text("Write-Host bad")
    with pytest.raises(ValueError, match="not allowlisted"):
        run_allowlisted_script(bad)


def test_allowlisted_paths_in_config():
    assert len(ALLOWED_POWERSHELL_SCRIPTS) >= 3
