"""Fail-closed data isolation for standalone Atlas verification scripts.

Verification and benchmark scripts exercise the real persistence paths.  They
must never inherit a developer's normal ``~/.atlas_desktop`` registry.  Call
``activate_isolated_atlas_data`` before importing :mod:`atlas_desktop`; the
current process and every subsequently spawned child will then share one
unique temporary data root.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Mapping, MutableMapping

_ISOLATION_MARKER = "ATLAS_VERIFICATION_ISOLATED"


def canonical_atlas_data_root(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the real per-user Atlas root without importing product code."""
    source = os.environ if env is None else env
    profile_key = "USERPROFILE" if os.name == "nt" else "HOME"
    profile = source.get(profile_key, "").strip()
    home = Path(profile or Path.home()).expanduser().resolve()
    return (home / ".atlas_desktop").resolve()


def _normalized(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.path.realpath(path)))


def _assert_isolated(root: Path, protected: Path) -> None:
    candidate = _normalized(root)
    protected_path = _normalized(protected)
    try:
        inside_protected = os.path.commonpath([candidate, protected_path]) == protected_path
    except ValueError:
        inside_protected = candidate == protected_path
    if inside_protected:
        raise RuntimeError(
            "Atlas verification refused the canonical user-data tree: "
            f"{protected}"
        )


def isolated_atlas_environment(
    label: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, dict[str, str]]:
    """Return a child environment backed by a unique temporary Atlas root."""
    source = dict(os.environ if environ is None else environ)
    protected = canonical_atlas_data_root(source)
    safe_label = "".join(ch if ch.isalnum() else "-" for ch in label).strip("-") or "proof"
    # tempfile.mkdtemp uses mode 0700.  On some constrained Windows runners
    # that mode is translated into an ACL which even a subsequent worker under
    # the same supervisor cannot write.  Create the unique directory with an
    # explicitly shareable mode so in-process scans and inherited children can
    # both use it.
    temp_root = Path(tempfile.gettempdir())
    while True:
        root = temp_root / f"atlas-{safe_label}-data-{uuid.uuid4().hex}"
        try:
            root.mkdir(mode=0o777)
            break
        except FileExistsError:
            continue
    _assert_isolated(root, protected)

    source["ATLAS_DESKTOP_DATA"] = str(root)
    source["ATLAS_TEST_MODE"] = "1"
    source["ATLAS_TEST_PROTECTED_DATA_ROOT"] = str(protected)
    source[_ISOLATION_MARKER] = "1"
    # The legacy override must not compete with the explicit isolated root.
    source.pop("JARVIS_DESKTOP_DATA", None)
    return root, source


def activate_isolated_atlas_data(
    label: str,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> Path:
    """Activate unique isolation before Atlas imports and child launches."""
    target = os.environ if environ is None else environ
    existing = target.get("ATLAS_DESKTOP_DATA", "").strip()
    if target.get(_ISOLATION_MARKER) == "1" and existing:
        protected = Path(
            target.get("ATLAS_TEST_PROTECTED_DATA_ROOT", "").strip()
            or canonical_atlas_data_root(target)
        )
        root = Path(existing).resolve()
        _assert_isolated(root, protected)
        return root

    root, isolated = isolated_atlas_environment(label, environ=target)
    target.update(
        {
            "ATLAS_DESKTOP_DATA": isolated["ATLAS_DESKTOP_DATA"],
            "ATLAS_TEST_MODE": isolated["ATLAS_TEST_MODE"],
            "ATLAS_TEST_PROTECTED_DATA_ROOT": isolated[
                "ATLAS_TEST_PROTECTED_DATA_ROOT"
            ],
            _ISOLATION_MARKER: "1",
        }
    )
    target.pop("JARVIS_DESKTOP_DATA", None)
    return root
