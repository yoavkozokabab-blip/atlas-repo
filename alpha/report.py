"""Alpha session report (Phase 68)."""

from __future__ import annotations

from collections import Counter

from alpha.session_log import alpha_sessions_dir, iter_session_entries


def show_alpha_report() -> str:
    entries = iter_session_entries()
    if not entries:
        return (
            "Alpha report\n"
            "  No alpha session logs yet.\n"
            f"  Sessions folder: {alpha_sessions_dir()}\n"
            "  Run commands with ALPHA_MODE=true to record activity."
        )

    session_ids = {e.get("session_id") for e in entries if e.get("session_id")}
    total = len(entries)
    successes = sum(1 for e in entries if e.get("success"))
    failures = total - successes
    safety_blocks = sum(1 for e in entries if e.get("safety_block"))
    latencies = [int(e.get("latency_ms") or 0) for e in entries if e.get("latency_ms")]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    intent_counts = Counter(str(e.get("intent") or "unknown") for e in entries)
    provider_counts = Counter(str(e.get("provider") or "unknown") for e in entries)
    top_commands = intent_counts.most_common(8)
    fail_entries = [e for e in entries if not e.get("success")][-5:]

    lines = [
        "Alpha report",
        f"  sessions: {len(session_ids)}",
        f"  commands_logged: {total}",
        f"  success_rate: {round(100.0 * successes / total, 1)}% ({successes}/{total})",
        f"  failures: {failures}",
        f"  safety_blocks: {safety_blocks}",
        f"  average_latency_ms: {avg_latency}",
        "",
        "  provider usage:",
    ]
    for prov, cnt in provider_counts.most_common(6):
        lines.append(f"    - {prov}: {cnt}")
    lines.extend(["", "  most_used_commands:"])
    for intent, cnt in top_commands:
        lines.append(f"    - {intent}: {cnt}")
    if fail_entries:
        lines.append("")
        lines.append("  recent_failures:")
        for e in fail_entries:
            lines.append(
                f"    - {e.get('intent')}: {(e.get('error') or e.get('summary_excerpt') or '')[:80]}"
            )
    lines.append("")
    lines.append(f"  log_folder: {alpha_sessions_dir()}")
    return "\n".join(lines)
