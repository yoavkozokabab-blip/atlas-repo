"""v1.0.5 malicious-repository hardening matrix.

Hostile repository layouts must never crash the scanner, escape the selected
root, execute repository code, or produce unbounded output. Assertions target
safe *outcomes* (bounded, contained, no side effects) rather than message
text.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache
    reset_desktop_data_dir_cache()
    return str(d)


def _scan(path) -> dict:
    _fresh()
    return api.scan_repository(str(path))


def test_traversal_style_filenames_do_not_escape_root(data_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("import util\n", encoding="utf-8")
    (repo / "util.py").write_text("x = 1\n", encoding="utf-8")
    # Files whose *names* look like traversal must be treated as plain names.
    (repo / "..py").write_text("y = 2\n", encoding="utf-8")
    sentinel = tmp_path / "outside.py"
    sentinel.write_text("SECRET_MARKER_OUTSIDE = 1\n", encoding="utf-8")
    result = _scan(repo)
    assert result.get("ok"), result.get("error")
    # Nothing outside the selected root may enter the scan.
    export = api.current_summary()
    assert "outside.py" not in str(export)


@pytest.mark.skipif(sys.platform != "win32", reason="junction test is Windows-specific")
def test_windows_junction_escape_is_contained(data_dir, tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("import util\n", encoding="utf-8")
    (repo / "util.py").write_text("x = 1\n", encoding="utf-8")
    outside = tmp_path / "outside_tree"
    outside.mkdir()
    (outside / "leaked_module_xyz.py").write_text("LEAK = 1\n", encoding="utf-8")
    junction = repo / "escape"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True, timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip("cannot create junction in this environment")
    result = _scan(repo)
    # Scan must complete (ok or clean refusal) and never crash…
    assert isinstance(result, dict)
    # …and even if the junction is followed, module identities must stay
    # inside the repo namespace (no absolute outside paths in the graph).
    if result.get("ok"):
        summary_text = str(api.current_summary())
        assert str(outside) not in summary_text


def test_recursive_junction_loop_terminates(data_dir, tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    if sys.platform == "win32":
        loop = repo / "loop"
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(loop), str(repo)],
            capture_output=True, timeout=30,
        )
        if proc.returncode != 0:
            pytest.skip("cannot create junction in this environment")
    result = _scan(repo)  # must return, not hang or blow the stack
    assert isinstance(result, dict)


def test_deep_nesting_is_bounded(data_dir, tmp_path):
    repo = tmp_path / "repo"
    current = repo
    # Deep, but built incrementally and kept under the Windows MAX_PATH limit
    # so this exercises the *scanner's* depth handling, not os.mkdir's.
    for i in range(24):
        current = current / f"d{i}"
        current.mkdir(parents=True, exist_ok=True)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    (current / "deep.py").write_text("y = 2\n", encoding="utf-8")
    result = _scan(repo)
    assert isinstance(result, dict)


def test_invalid_encoding_and_binary_files_do_not_crash(data_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("import util\n", encoding="utf-8")
    (repo / "util.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "bad.py").write_bytes(b"\xff\xfe\x00garbage\x80\x81 import os\n")
    (repo / "blob.py").write_bytes(os.urandom(4096))
    result = _scan(repo)
    assert result.get("ok"), result.get("error")


def test_oversized_file_is_bounded(data_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    # 8 MB of one line — parsing must stay bounded and never OOM/hang.
    (repo / "huge.py").write_text("# " + "A" * (8 * 1024 * 1024), encoding="utf-8")
    result = _scan(repo)
    assert isinstance(result, dict)


def test_repository_code_is_never_executed(data_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = tmp_path / "executed.marker"
    payload = (
        "import pathlib\n"
        f"pathlib.Path(r'{marker}').write_text('owned')\n"
    )
    (repo / "app.py").write_text(payload, encoding="utf-8")
    (repo / "setup.py").write_text(payload, encoding="utf-8")
    (repo / "conftest.py").write_text(payload, encoding="utf-8")
    result = _scan(repo)
    assert isinstance(result, dict)
    assert not marker.exists(), "scanning must never execute repository code"


def test_package_scripts_are_never_executed(data_dir, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = tmp_path / "npm.marker"
    (repo / "package.json").write_text(
        '{"name":"evil","scripts":{"preinstall":"echo owned > %s"}}' % str(marker).replace("\\", "\\\\"),
        encoding="utf-8",
    )
    (repo / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
    result = _scan(repo)
    assert isinstance(result, dict)
    assert not marker.exists()
