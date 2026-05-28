"""Apply approved patch proposals safely (Phase 21)."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR, PROJECT_ROOT
from task_agent.patch_proposals import (
    PatchProposal,
    validate_diff_text,
    validate_patch_target,
)

PATCH_BACKUP_ROOT = DATA_DIR / "patch_backups"
ALLOWED_PYTEST = ("py", "-3", "-m", "pytest", "-q")


@dataclass
class PatchApplyState:
    apply_id: str = ""
    backup_dir: Path | None = None
    target_files: list[str] = field(default_factory=list)
    git_diff: str = ""
    test_output: str = ""
    applied: bool = False
    rolled_back: bool = False


_last_apply: PatchApplyState | None = None


def get_last_apply() -> PatchApplyState | None:
    return _last_apply


def reset_patch_apply_store() -> None:
    global _last_apply
    _last_apply = None


def _resolve_file(rel: str) -> Path | None:
    from config import TRADING_PROJECT_ROOT

    rel = rel.replace("\\", "/").lstrip("/")
    ok, _ = validate_patch_target(rel)
    if not ok:
        return None
    for base in (PROJECT_ROOT, TRADING_PROJECT_ROOT):
        candidate = (base / rel).resolve()
        try:
            candidate.relative_to(base.resolve())
            return candidate
        except ValueError:
            continue
    return None


def _parse_diff_files(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            files.append(line[6:].strip())
        elif line.startswith("+++ b/") and not files:
            files.append(line[6:].strip())
    return files


def _apply_hunk(lines: list[str], hunk: list[str]) -> list[str] | None:
    """Apply a single unified-diff hunk to lines."""
    if not hunk or not hunk[0].startswith("@@"):
        return None
    m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", hunk[0])
    if not m:
        return None
    start_old = int(m.group(1)) - 1
    new_lines = list(lines[:start_old])
    old_idx = start_old
    for hl in hunk[1:]:
        if hl.startswith(" "):
            if old_idx < len(lines):
                new_lines.append(lines[old_idx])
            old_idx += 1
        elif hl.startswith("-"):
            old_idx += 1
        elif hl.startswith("+"):
            text = hl[1:]
            new_lines.append(text + ("\n" if not text.endswith("\n") else ""))
        elif hl.startswith("\\"):
            continue
    while old_idx < len(lines):
        new_lines.append(lines[old_idx])
        old_idx += 1
    return new_lines


def apply_unified_diff_to_path(path: Path, diff: str) -> tuple[bool, str]:
    """Apply unified diff to one file (Python-only, no shell patch)."""
    ok, msg = validate_diff_text(diff)
    if not ok:
        return False, msg

    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = content.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines = [l + ("\n" if not l.endswith("\n") else "") for l in lines]

    hunks: list[list[str]] = []
    current: list[str] = []
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = [line]
            in_hunk = True
        elif in_hunk and (line.startswith((" ", "+", "-", "\\")) or line == ""):
            current.append(line)
        elif line.startswith("---") or line.startswith("+++"):
            continue
    if current:
        hunks.append(current)

    if not hunks:
        # comment-only preview: prepend marker block
        marker = "# JARVIS applied patch marker\n"
        if marker not in content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(marker + content, encoding="utf-8")
        return True, "Applied preview marker block."

    result_lines = lines
    for hunk in hunks:
        applied = _apply_hunk(result_lines, hunk)
        if applied is None:
            return False, "Failed to apply hunk."
        result_lines = applied

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(result_lines), encoding="utf-8")
    return True, "Applied unified diff."


def backup_targets(targets: list[str], apply_id: str) -> Path:
    backup_dir = PATCH_BACKUP_ROOT / apply_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    for rel in targets:
        src = _resolve_file(rel)
        if src is None or not src.is_file():
            continue
        dest = backup_dir / rel.replace("/", "__")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return backup_dir


def _run_pytest() -> str:
    try:
        proc = subprocess.run(
            list(ALLOWED_PYTEST),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return out[-4000:] if len(out) > 4000 else out
    except Exception as exc:
        return f"pytest failed to run: {exc}"


def _git_diff(paths: list[str]) -> str:
    try:
        rel_paths = [p.replace("\\", "/") for p in paths]
        proc = subprocess.run(
            ["git", "diff", "--"] + rel_paths,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout[-8000:]
    except Exception:
        pass
    return "(git diff unavailable or not a git repo)"


def apply_approved_patch(proposal: PatchProposal) -> tuple[PatchApplyState, str]:
    """Apply an approved proposal: backup, patch, git diff, pytest."""
    global _last_apply
    if proposal.status != "approved":
        return PatchApplyState(), "Patch must be approved before apply."

    ok, msg = validate_diff_text(proposal.unified_diff)
    if not ok:
        return PatchApplyState(), msg

    apply_id = datetime.now(timezone.utc).strftime("apply_%Y%m%d_%H%M%S")
    targets = proposal.target_files or _parse_diff_files(proposal.unified_diff)
    if not targets:
        return PatchApplyState(), "No target files in proposal."

    for t in targets:
        ok_t, reason = validate_patch_target(t)
        if not ok_t:
            return PatchApplyState(), reason

    backup_dir = backup_targets(targets, apply_id)
    errors: list[str] = []
    for rel in targets:
        path = _resolve_file(rel)
        if path is None:
            errors.append(f"Cannot resolve: {rel}")
            continue
        ok_a, detail = apply_unified_diff_to_path(path, proposal.unified_diff)
        if not ok_a:
            errors.append(f"{rel}: {detail}")

    if errors:
        state = PatchApplyState(apply_id=apply_id, backup_dir=backup_dir, target_files=targets)
        _last_apply = state
        return state, "Apply errors: " + "; ".join(errors)

    git_diff = _git_diff(targets)
    test_out = _run_pytest()
    state = PatchApplyState(
        apply_id=apply_id,
        backup_dir=backup_dir,
        target_files=targets,
        git_diff=git_diff,
        test_output=test_out,
        applied=True,
    )
    _last_apply = state
    proposal.status = "applied"
    summary = (
        f"Patch applied (backup: {backup_dir}).\n"
        f"Git diff:\n{git_diff}\n\n"
        f"Pytest output (tail):\n{test_out[-2000:]}\n\n"
        "Rollback: say 'rollback task patch'."
    )
    return state, summary


def rollback_last_patch() -> tuple[bool, str]:
    """Restore files from last backup."""
    global _last_apply
    state = _last_apply
    if state is None or state.backup_dir is None:
        return False, "No patch apply to rollback."
    if state.rolled_back:
        return False, "Already rolled back."

    restored = 0
    for rel in state.target_files:
        backup_file = state.backup_dir / rel.replace("/", "__")
        dest = _resolve_file(rel)
        if dest and backup_file.is_file():
            shutil.copy2(backup_file, dest)
            restored += 1
    state.rolled_back = True
    return True, f"Rolled back {restored} file(s) from {state.backup_dir}."
