from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from atlas_desktop import data_paths, persistence


_SEEN_TEST_ROOTS: set[str] = set()


@pytest.mark.parametrize("case", ["first", "second"])
def test_every_test_invocation_receives_a_unique_root(case, isolated_atlas_data_root):
    resolved = os.path.normcase(str(Path(data_paths.desktop_data_dir()).resolve()))
    assert resolved == os.path.normcase(str(isolated_atlas_data_root.resolve()))
    assert resolved not in _SEEN_TEST_ROOTS
    _SEEN_TEST_ROOTS.add(resolved)


def test_test_mode_refuses_missing_override(monkeypatch):
    monkeypatch.delenv("ATLAS_DESKTOP_DATA", raising=False)
    monkeypatch.delenv("JARVIS_DESKTOP_DATA", raising=False)
    data_paths.reset_desktop_data_dir_cache()
    with pytest.raises(RuntimeError, match="requires ATLAS_DESKTOP_DATA"):
        data_paths.desktop_data_dir()


def test_test_mode_refuses_protected_root(monkeypatch):
    protected = data_paths.protected_test_data_root()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", protected)
    monkeypatch.delenv("JARVIS_DESKTOP_DATA", raising=False)
    data_paths.reset_desktop_data_dir_cache()
    with pytest.raises(RuntimeError, match="protected canonical data root"):
        data_paths.desktop_data_dir()


def test_explicit_persistence_path_cannot_bypass_guard(tmp_path, monkeypatch):
    protected = tmp_path / "protected-canonical"
    monkeypatch.setenv("ATLAS_TEST_PROTECTED_DATA_ROOT", str(protected))
    with pytest.raises(RuntimeError, match="protected canonical data root"):
        persistence._registry_path(str(protected))
    assert not protected.exists()


def test_child_process_inherits_isolated_root(isolated_atlas_data_root):
    code = (
        "from atlas_desktop.data_paths import desktop_data_dir; "
        "import os; print(os.environ['ATLAS_TEST_MODE']); print(desktop_data_dir())"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.strip().splitlines()
    assert lines[0] == "1"
    assert os.path.normcase(lines[1]) == os.path.normcase(str(isolated_atlas_data_root))


def test_child_process_refuses_protected_root(tmp_path):
    protected = tmp_path / "protected-canonical"
    env = dict(os.environ)
    env["ATLAS_TEST_MODE"] = "1"
    env["ATLAS_TEST_PROTECTED_DATA_ROOT"] = str(protected)
    env["ATLAS_DESKTOP_DATA"] = str(protected)
    env.pop("JARVIS_DESKTOP_DATA", None)
    code = "from atlas_desktop.data_paths import desktop_data_dir; desktop_data_dir()"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode != 0
    assert "protected canonical data root" in completed.stderr
    assert not protected.exists()
