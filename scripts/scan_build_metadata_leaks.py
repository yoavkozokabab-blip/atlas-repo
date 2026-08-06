"""Release gate: fail if a built artifact leaks the machine it was built on.

The published v1.0.5 installer shipped
`_internal/packaging/installer/build_info.json` containing

    "source_root": "C:\\J.A.R.V.I.S\\atlas-v105-completion"

so every user could read the developer's folder layout, including the
product's former name. That specific field is gone, but the class of defect is
not: any absolute build path, worktree name, local username or temp directory
baked into shipped metadata is the same leak wearing a different hat.

This scans the metadata files inside a staged install tree (or an extracted
one) and exits non-zero on anything that looks machine-specific. It runs from
installer_build.ps1 so a leaking build cannot be packaged at all.

Usage:
    python scripts/scan_build_metadata_leaks.py <path-to-staged-or-install-tree>
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# Metadata/config that ships alongside the binaries. Python sources and
# vendored third-party trees are out of scope: this gate is about what the
# build *wrote*, not what it packaged.
METADATA_SUFFIXES = {".json", ".txt", ".iss", ".md", ".cfg", ".ini", ".toml"}
SKIP_DIR_NAMES = {"__pycache__", "atlas_knowledge", "demo", "certifi", "node_modules"}
# Vendored dist-info/licence noise would otherwise dominate the report.
SKIP_PATH_MARKERS = ("dist-info", "site-packages", "_vendor")

PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("windows absolute path", re.compile(r"[A-Za-z]:\\\\?(?:Users|Program Files|J\.A\.R\.V\.I\.S|Temp|Windows)", re.I)),
    ("source_root field", re.compile(r'"source_root"', re.I)),
    ("legacy product name", re.compile(r"J\.A\.R\.V\.I\.S|jarvis[_-]?desktop", re.I)),
    ("worktree name", re.compile(r"atlas-(?:v1\d{2}|rc\d|hn|release|accounts|impact|desktop)[a-z0-9-]*", re.I)),
    ("posix home path", re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/")),
    ("temp directory", re.compile(r"(?:AppData\\\\?Local\\\\?Temp|/tmp/)", re.I)),
    ("python build location", re.compile(r"(?:site-packages|Python3\d\\|\.phase\d+_packaging_lib)", re.I)),
    ("git repository path", re.compile(r"\.git[\\/](?:worktrees|modules)", re.I)),
]

# The local Windows account name, discovered at scan time rather than
# hardcoded, so this keeps working on any build machine.
_USERNAME = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()
if len(_USERNAME) >= 3:
    PATTERNS.append(("local username", re.compile(re.escape(_USERNAME), re.I)))


def metadata_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in METADATA_SUFFIXES:
            continue
        parts = {part.lower() for part in path.parts}
        if parts & {name.lower() for name in SKIP_DIR_NAMES}:
            continue
        if any(marker in str(path).lower() for marker in SKIP_PATH_MARKERS):
            continue
        yield path


def scan(root: Path) -> List[str]:
    findings: List[str] = []
    for path in metadata_files(root):
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            findings.append(f"{path}: unreadable ({exc})")
            continue
        for label, pattern in PATTERNS:
            match = pattern.search(text)
            if match:
                snippet = match.group(0)[:80]
                findings.append(f"{path.relative_to(root)}: {label} -> {snippet!r}")
    return findings


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"FAIL: not a directory: {root}")
        return 2

    findings = scan(root)
    scanned = sum(1 for _ in metadata_files(root))
    if findings:
        print(f"FAIL: build metadata leaks the build machine ({len(findings)} finding(s)):")
        for line in findings:
            print(f"  - {line}")
        return 1
    print(f"PASS: {scanned} metadata file(s) scanned, no build-machine paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
