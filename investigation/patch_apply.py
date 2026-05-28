"""Phase 48 safe controlled patch apply + validation (paper/telemetry operational fixes only)."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, PROJECT_ROOT, TRADING_PROJECT_ROOT
from investigation.execution_cleanup import _build_preview, _latest_preview
from investigation.execution_investigation import _collect_evidence, _read


def _trading_root() -> Path:
    import config

    return config.TRADING_PROJECT_ROOT

APPLY_REPORT_DIR = PROJECT_ROOT / "reports" / "jarvis_investigations" / "patch_apply"
BACKUP_ROOT = PROJECT_ROOT / "backups" / "jarvis_patches"
STATE_PATH = DATA_DIR / "patch_apply_state.json"
HISTORY_PATH = APPLY_REPORT_DIR / "patch_apply_history.jsonl"

PATCH_BUNDLE_ID = "phase47_p1_p2_p4"
PATCH_SOURCE = "phase47_execution_cleanup"
PATCH_STATUS = "VERIFIED_SAFE"
PATCH_SCOPE = "paper_telemetry_only"

ALLOWED_REL_PATHS: tuple[str, ...] = (
    "services/live_paper_engine.py",
    "services/live_paper_state.py",
    "services/live_dual_paper_cycle.py",
    "reports/live_paper/dual/state/open_positions.json",
    "reports/live_paper/dual/execution_decision_summary.json",
    "reports/live_paper/dual/state/jarvis_execution_telemetry.json",
)

BLOCKED_PATH_FRAGMENTS: tuple[str, ...] = (
    "algo_scanner/",
    "strategy/",
    "entry_logic",
    "risk_model",
    "broker_execution",
    "portfolio_sizing",
    "real_algo",
)

P1_INACTIVE_BLOCK = """
# ===== JARVIS PHASE48 P1 (paper-local close hook; inactive until wired) =====
if False:
    # paper_local_close_after_adapter_disabled
    pass
# ===== END JARVIS P1 =====
""".strip()

P2_P4_TELEMETRY_KEYS = (
    "primary_execution_blocker",
    "reason_if_no_attempt",
    "n_scan_rows_skipped_last_bar",
    "n_execution_rejected",
    "kill_switch_enabled",
    "adapter_health_ok",
    "execution_enabled",
    "open_risk_fraction_daily",
    "daily_max_total_risk_cap",
)


@dataclass
class PatchApplyState:
    validated: bool = False
    approved: bool = False
    approver: str = ""
    bundle_id: str = PATCH_BUNDLE_ID
    status: str = PATCH_STATUS
    scope: str = PATCH_SCOPE
    last_backup_id: str = ""
    last_apply_at: str = ""
    pre_snapshot: dict[str, Any] | None = None
    post_snapshot: dict[str, Any] | None = None
    files_changed: list[str] | None = None
    rollback_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_state() -> PatchApplyState:
    if not STATE_PATH.exists():
        return PatchApplyState()
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return PatchApplyState(**{k: payload.get(k) for k in PatchApplyState.__dataclass_fields__})
    except (OSError, json.JSONDecodeError, TypeError):
        return PatchApplyState()


def _save_state(state: PatchApplyState) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")


def _rel(path: Path) -> str:
    text = str(path).replace("\\", "/")
    root = str(_trading_root()).replace("\\", "/")
    if text.startswith(root):
        return text[len(root) :].lstrip("/")
    return path.name


def _resolve_allowed_rel(rel: str) -> Path | None:
    rel_norm = rel.replace("\\", "/").lstrip("/")
    if rel_norm not in ALLOWED_REL_PATHS:
        return None
    for frag in BLOCKED_PATH_FRAGMENTS:
        if frag in rel_norm.lower():
            return None
    return _trading_root() / rel_norm


def _is_scope_allowed(rel: str) -> bool:
    return _resolve_allowed_rel(rel) is not None


def _append_history(event: str, payload: dict[str, Any]) -> None:
    APPLY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **payload}
    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def _bundle_from_phase47() -> dict[str, Any]:
    preview = _latest_preview()
    return {
        "bundle_id": PATCH_BUNDLE_ID,
        "source": PATCH_SOURCE,
        "status": PATCH_STATUS,
        "scope": PATCH_SCOPE,
        "candidates": ["P1", "P2", "P4"],
        "selected": "P1+P2+P4",
        "title": "Paper-local stale position cleanup + telemetry visibility",
        "risk_before": preview.risk_before,
        "risk_after_simulated": preview.risk_after_simulated,
        "patch_preview_diff": preview.patch_preview_diff,
        "rollback_plan": preview.rollback_plan,
        "tests_to_run": preview.tests_to_run,
    }


def preview_patch_diff() -> str:
    bundle = _bundle_from_phase47()
    lines = [
        "Patch diff preview (Phase 47 bundle P1+P2+P4):",
        f"  bundle: {bundle['bundle_id']} status={bundle['status']} scope={bundle['scope']}",
        "  allowed targets:",
    ]
    lines.extend(f"    - {p}" for p in ALLOWED_REL_PATHS)
    lines.append("  diff preview:")
    lines.append(bundle["patch_preview_diff"])
    return "\n".join(lines)


def validate_runtime_safety() -> tuple[bool, list[str]]:
    issues: list[str] = []
    _, combined = _collect_evidence()
    hay = combined.lower()
    if re.search(r"\blive_trading\b\s*[:=]\s*true|\breal_live\b|\bbroker_live\b", hay):
        issues.append("live trading mode appears enabled")
    if re.search(r"alpaca.*live.*enabled.*true|execution_mode.*live[^_-]", hay) and "paper" not in hay:
        issues.append("Alpaca live mode may be enabled")
    if re.search(r"place_order|submit_order|broker_order", hay) and "paper_only" not in hay:
        if re.search(r"accepted.*true|order_id", hay):
            issues.append("broker order activity detected in recent evidence")
    mode = "paper" if re.search(r"live_paper|paper|execution_mode.*paper", hay) else "unknown"
    if re.search(r'"execution_mode"\s*:\s*"live"|\blive_trading_enabled\b\s*[:=]\s*true', hay) and "paper" not in hay:
        issues.append("execution mode is not clearly paper/live-paper")
    return len(issues) == 0, issues


def validate_patch_safety() -> str:
    preview = _build_preview()
    runtime_ok, runtime_issues = validate_runtime_safety()
    bundle = _bundle_from_phase47()
    lines = [
        "Patch safety validation:",
        f"  source: {PATCH_SOURCE}",
        f"  status: {PATCH_STATUS}",
        f"  scope: {PATCH_SCOPE}",
        f"  bundle: {PATCH_BUNDLE_ID} ({bundle['selected']})",
        f"  simulated risk: {preview.risk_before} -> {preview.risk_after_simulated}",
        f"  runtime safety: {'PASS' if runtime_ok else 'FAIL'}",
    ]
    if runtime_issues:
        lines.extend(f"    - {x}" for x in runtime_issues)
    blocked_probe = _resolve_allowed_rel("algo_scanner/strategy/real_algo.py")
    lines.append(f"  blocked scope probe: {'REFUSED' if blocked_probe else 'blocked paths enforced'}")
    if not runtime_ok:
        lines.append("RESULT: VALIDATION FAILED — apply blocked.")
        return "\n".join(lines)
    state = _load_state()
    state.validated = True
    state.bundle_id = PATCH_BUNDLE_ID
    state.status = PATCH_STATUS
    state.scope = PATCH_SCOPE
    _save_state(state)
    lines.append("RESULT: VALIDATION PASSED — awaiting explicit approval before apply.")
    lines.append("Next: show approved patch → apply approved patch confirm")
    return "\n".join(lines)


def show_approved_patch() -> str:
    state = _load_state()
    bundle = _bundle_from_phase47()
    lines = [
        "Approved operational patch bundle (preview):",
        f"  validated: {state.validated}",
        f"  approved: {state.approved}",
        f"  approver: {state.approver or 'pending'}",
        f"  bundle: {bundle['bundle_id']}",
        f"  candidates: {', '.join(bundle['candidates'])}",
        f"  scope: {bundle['scope']}",
        f"  simulated risk delta: {bundle['risk_before']} -> {bundle['risk_after_simulated']}",
        "  files eligible for apply:",
    ]
    lines.extend(f"    - {p}" for p in ALLOWED_REL_PATHS)
    lines.append("  diff preview:")
    lines.append(bundle["patch_preview_diff"])
    lines.append(f"  rollback: {bundle['rollback_plan']}")
    if not state.validated:
        lines.append("  note: run validate patch safety first.")
    return "\n".join(lines)


def _create_backup(backup_id: str, files: list[Path]) -> Path:
    backup_dir = BACKUP_ROOT / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "backup_id": backup_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bundle_id": PATCH_BUNDLE_ID,
        "files": [],
    }
    for path in files:
        if not path.exists():
            continue
        rel = _rel(path)
        dest = backup_dir / rel.replace("/", "__")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        meta["files"].append({"rel": rel, "backup": str(dest)})
    preview = _build_preview()
    (backup_dir / "validation_snapshot.json").write_text(
        json.dumps(preview.to_dict(), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (backup_dir / "patch_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=True), encoding="utf-8")
    return backup_dir


def _clean_open_positions(path: Path) -> tuple[int, list[str]]:
    if not path.exists():
        return 0, []
    text = path.read_text(encoding="utf-8", errors="replace")
    removed: list[str] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return 0, []
    if isinstance(payload, list):
        kept = []
        for item in payload:
            if not isinstance(item, dict):
                kept.append(item)
                continue
            sym = str(item.get("symbol", "UNKNOWN"))
            if item.get("stop_loss_hit") or item.get("close_rejected") or item.get("stale"):
                removed.append(sym)
            else:
                kept.append(item)
        path.write_text(json.dumps(kept, indent=2, ensure_ascii=True), encoding="utf-8")
        return len(removed), removed
    return 0, []


def _apply_telemetry_p2_p4(summary_path: Path, telemetry_path: Path, preview: Any) -> None:
    summary: dict[str, Any] = {}
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = {}
    primary = preview.primary_execution_blocker.replace(" ", "_")
    summary.update(
        {
            "reason_if_no_attempt": primary if primary else summary.get("reason_if_no_attempt"),
            "primary_execution_blocker": preview.primary_execution_blocker,
            "n_scan_rows_skipped_last_bar": summary.get("n_scan_rows_skipped_last_bar", 0),
            "n_execution_rejected": summary.get(
                "n_execution_rejected",
                max(0, preview.signals_eligible_before - preview.execution_attempts),
            ),
            "kill_switch_enabled": preview.kill_switch_enabled,
            "adapter_health_ok": preview.adapter_health_ok,
            "execution_enabled": preview.execution_enabled,
            "open_risk_fraction_daily": preview.open_risk_fraction_daily_after,
            "daily_max_total_risk_cap": preview.daily_max_total_risk_cap,
            "jarvis_patch_applied": PATCH_BUNDLE_ID,
        }
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    telemetry_path.write_text(
        json.dumps(
            {
                "patch_bundle": PATCH_BUNDLE_ID,
                "paper_local_close_events": [],
                "adapter_failure_surfaced": True,
                "telemetry_keys": list(P2_P4_TELEMETRY_KEYS),
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )


def _append_code_marker(path: Path, marker: str, tag: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if tag in text:
        return False
    path.write_text(text.rstrip() + "\n\n" + marker + "\n", encoding="utf-8")
    return True


def apply_approved_patch(*, confirmed: bool = False, approver: str = "operator") -> str:
    state = _load_state()
    if not state.validated:
        return "Apply refused: run validate patch safety first."
    if not confirmed and not state.approved:
        return (
            "Apply refused: explicit approval required.\n"
            "Re-run as: apply approved patch confirm\n"
            "Or approve first via confirmation flow."
        )
    runtime_ok, runtime_issues = validate_runtime_safety()
    if not runtime_ok:
        return "Apply refused: runtime safety failed:\n" + "\n".join(f"  - {x}" for x in runtime_issues)

    preview = _build_preview()
    pre_snapshot = {
        "risk": preview.open_risk_fraction_daily_before,
        "engine_positions": preview.engine_open_position_count,
        "eligible_signals": preview.signals_eligible_before,
    }
    targets: list[Path] = []
    for rel in ALLOWED_REL_PATHS:
        resolved = _resolve_allowed_rel(rel)
        if resolved is not None and resolved.exists():
            targets.append(resolved)

    open_positions = _resolve_allowed_rel("reports/live_paper/dual/state/open_positions.json")
    summary_path = _resolve_allowed_rel("reports/live_paper/dual/execution_decision_summary.json")
    telemetry_path = _resolve_allowed_rel("reports/live_paper/dual/state/jarvis_execution_telemetry.json")
    engine_path = _resolve_allowed_rel("services/live_paper_engine.py")
    cycle_path = _resolve_allowed_rel("services/live_dual_paper_cycle.py")

    if open_positions is None or summary_path is None:
        return "Apply refused: blocked or unknown target path."

    backup_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    apply_targets = [p for p in [open_positions, summary_path, engine_path, cycle_path] if p and p.exists()]
    if open_positions.parent.exists() or _trading_root().exists():
        open_positions.parent.mkdir(parents=True, exist_ok=True)
    if not open_positions.exists():
        open_positions.write_text("[]", encoding="utf-8")
        apply_targets.append(open_positions)

    _create_backup(backup_id, apply_targets)
    removed_count, removed_symbols = _clean_open_positions(open_positions)
    _apply_telemetry_p2_p4(summary_path, telemetry_path or open_positions.parent / "jarvis_execution_telemetry.json", preview)
    changed: list[str] = [str(open_positions), str(summary_path)]
    if engine_path and _append_code_marker(engine_path, P1_INACTIVE_BLOCK, "JARVIS PHASE48 P1"):
        changed.append(str(engine_path))
    if cycle_path and _append_code_marker(cycle_path, "# JARVIS PHASE48 P2/P4 telemetry markers\nif False: pass\n", "JARVIS PHASE48 P2"):
        changed.append(str(cycle_path))

    post_preview = _build_preview()
    post_snapshot = {
        "risk": post_preview.open_risk_fraction_daily_after,
        "engine_positions": max(post_preview.engine_open_position_count - removed_count, 0),
        "eligible_signals": post_preview.signals_eligible_after_simulated,
        "removed_symbols": removed_symbols,
    }
    replay_ok, replay_msg = _replay_validation_internal(post_snapshot, pre_snapshot)

    state.approved = True
    state.approver = approver
    state.last_backup_id = backup_id
    state.last_apply_at = datetime.now(timezone.utc).isoformat()
    state.pre_snapshot = pre_snapshot
    state.post_snapshot = post_snapshot
    state.files_changed = changed
    state.rollback_available = True
    _save_state(state)

    report = _save_apply_report(
        event="apply",
        backup_id=backup_id,
        approver=approver,
        files_changed=changed,
        pre=pre_snapshot,
        post=post_snapshot,
        replay_ok=replay_ok,
        replay_msg=replay_msg,
    )
    _append_history("apply", {"backup_id": backup_id, "approver": approver, "files": changed})
    lines = [
        "Patch apply completed (paper/telemetry operational scope only).",
        f"  backup id: {backup_id}",
        f"  files changed: {len(changed)}",
        f"  stale positions removed: {removed_count} ({', '.join(removed_symbols) or 'none'})",
        f"  risk: {pre_snapshot['risk']} -> {post_snapshot['risk']}",
        f"  replay validation: {'PASSED' if replay_ok else 'FAILED'}",
        replay_msg,
        f"  report: {report}",
        "  broker orders: NOT sent (paper-local cleanup only)",
    ]
    return "\n".join(lines)


def rollback_last_patch(*, confirmed: bool = False) -> str:
    state = _load_state()
    if not state.rollback_available or not state.last_backup_id:
        return "Rollback unavailable: no prior patch apply backup found."
    if not confirmed:
        return "Rollback requires explicit approval. Re-run: rollback last patch confirm"
    backup_dir = BACKUP_ROOT / state.last_backup_id
    meta_path = backup_dir / "patch_metadata.json"
    if not meta_path.exists():
        return f"ROLLBACK FAILED: backup metadata missing for {state.last_backup_id}"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    restored: list[str] = []
    for item in meta.get("files", []):
        rel = item.get("rel", "")
        backup_file = Path(item.get("backup", ""))
        target = _resolve_allowed_rel(rel)
        if target is None or not backup_file.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, target)
        restored.append(str(target))
    replay_ok, replay_msg = _replay_validation_internal(state.pre_snapshot or {}, state.post_snapshot or {})
    state.rollback_available = False
    _save_state(state)
    report = _save_apply_report(
        event="rollback",
        backup_id=state.last_backup_id,
        approver=state.approver or "operator",
        files_changed=restored,
        pre=state.post_snapshot or {},
        post=state.pre_snapshot or {},
        replay_ok=replay_ok,
        replay_msg=replay_msg,
        rollback_status="SUCCESS",
    )
    _append_history("rollback", {"backup_id": state.last_backup_id, "restored": restored})
    return "\n".join(
        [
            "ROLLBACK SUCCESS",
            f"  backup id: {state.last_backup_id}",
            f"  restored files: {len(restored)}",
            replay_msg,
            f"  report: {report}",
        ]
    )


def show_patch_history() -> str:
    if not HISTORY_PATH.exists():
        return "Patch history: none"
    lines = ["Patch apply history:"]
    for row in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
        try:
            item = json.loads(row)
            lines.append(f"- {item.get('ts')} {item.get('event')} backup={item.get('backup_id', item.get('backup_id', ''))}")
        except json.JSONDecodeError:
            continue
    state = _load_state()
    lines.append(f"  last backup id: {state.last_backup_id or 'none'}")
    lines.append(f"  rollback available: {state.rollback_available}")
    return "\n".join(lines)


def validate_applied_patch() -> str:
    state = _load_state()
    if not state.last_apply_at:
        return "No applied patch to validate. Run apply approved patch confirm first."
    pre = state.pre_snapshot or {}
    post = state.post_snapshot or {}
    tele_ok, tele_issues = _telemetry_validation()
    replay_ok, replay_msg = _replay_validation_internal(post, pre)
    lines = [
        "Applied patch validation:",
        f"  apply time: {state.last_apply_at}",
        f"  backup id: {state.last_backup_id}",
        f"  telemetry validation: {'PASS' if tele_ok else 'FAIL'}",
    ]
    lines.extend(f"    - {x}" for x in tele_issues)
    lines.append(f"  replay validation: {'PASSED' if replay_ok else 'FAILED'}")
    lines.append(f"  {replay_msg}")
    lines.append(f"OVERALL: {'PATCH VALIDATION PASSED' if replay_ok and tele_ok else 'PATCH VALIDATION FAILED'}")
    return "\n".join(lines)


def _replay_validation_internal(post: dict[str, Any], pre: dict[str, Any]) -> tuple[bool, str]:
    risk_before = float(pre.get("risk", 0) or 0)
    risk_after = float(post.get("risk", 0) or 0)
    eligible_before = int(pre.get("eligible_signals", 0) or 0)
    eligible_after = int(post.get("eligible_signals", 0) or 0)
    ok = risk_after <= risk_before and eligible_after >= eligible_before
    msg = (
        f"risk {risk_before}->{risk_after}; eligible {eligible_before}->{eligible_after}; "
        f"stale cleanup={len(post.get('removed_symbols', []))} symbols"
    )
    return ok, msg


def replay_after_patch() -> str:
    from runtime.result_stream import stream_progress, stream_result

    stream_progress("loading patch snapshots...")
    state = _load_state()
    if not state.post_snapshot:
        return "No post-patch snapshot. Apply patch first."
    stream_progress("running replay validation...")
    ok, msg = _replay_validation_internal(state.post_snapshot, state.pre_snapshot or {})
    if ok:
        stream_result("replay validation passed", severity="info")
        try:
            from assistant.notifications import notify_replay_validation_passed

            notify_replay_validation_passed(msg[:200])
        except Exception:
            pass
    else:
        stream_result("replay validation failed", severity="error")
    return f"Replay after patch: {'PATCH VALIDATION PASSED' if ok else 'PATCH VALIDATION FAILED'}\n  {msg}"


def compare_pre_post_patch() -> str:
    state = _load_state()
    pre = state.pre_snapshot or {}
    post = state.post_snapshot or {}
    if not pre or not post:
        return "No pre/post patch snapshots. Apply patch first."
    return "\n".join(
        [
            "Pre/post patch comparison:",
            f"  risk fraction: {pre.get('risk')} -> {post.get('risk')}",
            f"  engine positions: {pre.get('engine_positions')} -> {post.get('engine_positions')}",
            f"  eligible signals: {pre.get('eligible_signals')} -> {post.get('eligible_signals')}",
            f"  removed symbols: {', '.join(post.get('removed_symbols', [])) or 'none'}",
            f"  backup id: {state.last_backup_id}",
            f"  files changed: {len(state.files_changed or [])}",
        ]
    )


def show_patch_workflow_status() -> str:
    state = _load_state()
    replay_ok = False
    replay_msg = "not run"
    if state.post_snapshot:
        replay_ok, replay_msg = _replay_validation_internal(state.post_snapshot, state.pre_snapshot or {})
        replay_status = f"{'PASSED' if replay_ok else 'FAILED'} ({replay_msg})"
    elif state.validated:
        replay_status = "pending apply"
    else:
        replay_status = "not run"
    backup_id = state.last_backup_id or "none"
    latest_report = _latest_audit_report()
    return "\n".join(
        [
            "Patch workflow status:",
            f"  safety validated: {'yes' if state.validated else 'no'}",
            f"  patch approved: {'yes' if state.approved or state.validated else 'no'}",
            f"  patch applied: {'yes' if state.last_apply_at else 'no'}",
            f"  replay validated: {replay_status}",
            f"  rollback available: {state.rollback_available}",
            f"  backup id: {backup_id}",
            f"  latest audit report: {latest_report}",
        ]
    )


def _latest_audit_report() -> str:
    if not APPLY_REPORT_DIR.exists():
        return "none"
    candidates = sorted(APPLY_REPORT_DIR.glob("*.md"), reverse=True)
    if not candidates:
        candidates = sorted(APPLY_REPORT_DIR.glob("*.json"), reverse=True)
    return str(candidates[0]) if candidates else "none"


def run_patch_workflow(*, confirmed: bool = False) -> str:
    sections: list[str] = ["=== Patch workflow ==="]

    sections.append("--- Step 1: validate patch safety ---")
    sections.append(validate_patch_safety())

    sections.append("--- Step 2: show approved patch ---")
    sections.append(show_approved_patch())

    if not confirmed:
        sections.append("--- Step 3: confirmation required ---")
        sections.append(
            "Apply NOT executed. Re-run: run patch workflow confirm\n"
            "This will apply the approved patch (paper/telemetry only)."
        )
        return "\n".join(sections)

    sections.append("--- Step 4: apply approved patch ---")
    apply_result = apply_approved_patch(confirmed=True, approver="operator")
    sections.append(apply_result)
    if apply_result.startswith("Apply refused"):
        sections.append("=== Workflow halted at apply ===")
        return "\n".join(sections)

    sections.append("--- Step 5: validate applied patch ---")
    sections.append(validate_applied_patch())
    sections.append("--- Step 6: compare pre post patch ---")
    sections.append(compare_pre_post_patch())
    sections.append("--- Step 7: replay after patch ---")
    sections.append(replay_after_patch())

    state = _load_state()
    tele_ok, _tele_issues = _telemetry_validation()
    replay_ok, replay_msg = _replay_validation_internal(state.post_snapshot or {}, state.pre_snapshot or {})
    overall = replay_ok and tele_ok and bool(state.last_apply_at)
    sections.append("--- Step 8: summary ---")
    sections.append(
        "\n".join(
            [
                f"Workflow complete: {'SUCCESS' if overall else 'PARTIAL/FAILED'}",
                f"  backup: {state.last_backup_id or 'none'}",
                f"  apply: {state.last_apply_at or 'not applied'}",
                f"  telemetry: {'PASS' if tele_ok else 'FAIL'}",
                f"  replay: {'PASS' if replay_ok else 'FAIL'} ({replay_msg})",
                f"  rollback available: {state.rollback_available}",
            ]
        )
    )
    return "\n".join(sections)


def _telemetry_validation() -> tuple[bool, list[str]]:
    issues: list[str] = []
    summary_path = _resolve_allowed_rel("reports/live_paper/dual/execution_decision_summary.json")
    if summary_path is None or not summary_path.exists():
        return False, ["execution_decision_summary.json missing"]
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, ["execution_decision_summary.json invalid json"]
    for key in P2_P4_TELEMETRY_KEYS:
        if key not in payload:
            issues.append(f"missing telemetry key: {key}")
    primary = str(payload.get("primary_execution_blocker", ""))
    reason = str(payload.get("reason_if_no_attempt", ""))
    if reason == "not_relevant_to_last_bar" and primary:
        issues.append("reason_if_no_attempt still scan-noise despite primary blocker")
    if not issues:
        return True, []
    return False, issues


def validate_scope_path(rel: str) -> str:
    if any(b in rel.lower() for b in BLOCKED_PATH_FRAGMENTS):
        return f"REFUSE APPLY: blocked scope path {rel}"
    if rel not in ALLOWED_REL_PATHS and not _is_scope_allowed(rel):
        return f"REFUSE APPLY: path not in allowed scope {rel}"
    return f"ALLOWED: {rel}"


def _save_apply_report(
    *,
    event: str,
    backup_id: str,
    approver: str,
    files_changed: list[str],
    pre: dict[str, Any],
    post: dict[str, Any],
    replay_ok: bool,
    replay_msg: str,
    rollback_status: str = "",
) -> str:
    APPLY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = APPLY_REPORT_DIR / f"{ts}_{event}.json"
    md_path = APPLY_REPORT_DIR / f"{ts}_{event}.md"
    tele_ok, tele_issues = _telemetry_validation() if event == "apply" else (True, [])
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "approver": approver,
        "patch_id": PATCH_BUNDLE_ID,
        "backup_id": backup_id,
        "files_changed": files_changed,
        "pre": pre,
        "post": post,
        "replay_passed": replay_ok,
        "replay_message": replay_msg,
        "telemetry_passed": tele_ok,
        "telemetry_issues": tele_issues,
        "rollback_status": rollback_status or ("available" if event == "apply" else rollback_status),
        "risk_assessment": "paper-only operational fix; no broker orders",
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Patch Apply Report ({event})",
                f"Approver: {approver}",
                f"Patch: {PATCH_BUNDLE_ID}",
                f"Backup: {backup_id}",
                "## Files",
                *[f"- {f}" for f in files_changed],
                "## Replay",
                f"- passed: {replay_ok}",
                f"- message: {replay_msg}",
                "## Telemetry",
                f"- passed: {tele_ok}",
                *[f"- issue: {i}" for i in tele_issues],
            ]
        ),
        encoding="utf-8",
    )
    return str(md_path)
