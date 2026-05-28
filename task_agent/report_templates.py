"""Engineering report templates for supervised tasks (Phase 20)."""

from __future__ import annotations

from task_agent.findings import format_findings_grouped
from task_agent.models import TaskSession
from task_agent.patch_proposals import PatchProposal, format_patch_proposal


def next_recommended_commands(session: TaskSession) -> list[str]:
    cmds = ["show task findings", "show task status"]
    if session.patch_proposal and session.patch_proposal.status == "draft":
        cmds.extend(["show task patch", "approve task patch", "reject task patch"])
    elif not session.patch_proposal:
        cmds.append("propose task patch")
    if session.report_path:
        cmds.append("show task report")
    if not session.stop_requested and session.plan_approved:
        cmds.append("run task step")
    return cmds


def build_engineering_report(session: TaskSession) -> str:
    lines = [
        f"# Task Report: {session.task_id}",
        "",
        "## Objective",
        session.plan.objective,
        "",
        "## Plan",
        "```",
        session.plan.format_plan(),
        "```",
        "",
        "## Steps completed",
    ]
    for step in session.plan.steps:
        flag = step.status.value
        lines.append(f"- `{step.step_id}` [{flag}] {step.title} ({step.command_key})")
        if step.result_summary:
            lines.append(f"  - {step.result_summary[:350]}")

    lines.extend(["", "## Findings (summary)"])
    if session.findings:
        lines.extend(f"- {f}" for f in session.findings[:30])
    else:
        lines.append("- (none)")

    lines.extend(["", "## Evidence (structured)", ""])
    lines.append(format_findings_grouped(session.structured_findings))

    lines.extend(["", "## Risks"])
    high = [f for f in session.structured_findings if f.severity == "high"]
    if high:
        for f in high:
            lines.append(f"- **{f.category}:** {f.title}")
    else:
        lines.append("- No high-severity findings recorded.")

    lines.extend(["", "## Test plan"])
    proposal: PatchProposal | None = session.patch_proposal
    if proposal and proposal.tests_to_run:
        lines.extend(f"- {t}" for t in proposal.tests_to_run)
    else:
        lines.extend(
            [
                "- py -3 -m pytest -q",
                "- py -3 -m compileall .",
                "- show_dashboard_health (if trading)",
            ]
        )

    lines.extend(["", "## Patch proposal"])
    if proposal:
        lines.append(f"Status: {proposal.status} (preview only — not applied)")
        lines.append("")
        lines.append(format_patch_proposal(proposal))
    else:
        lines.append("- No patch proposed. Use `propose task patch` after findings.")

    if session.git_diff_before or session.git_diff_after:
        lines.extend(["", "## Git diff summary (workspace)"])
        if session.git_diff_before:
            lines.append("### Before task")
            lines.append("```")
            lines.append(session.git_diff_before[:3000])
            lines.append("```")
        if session.git_diff_after:
            lines.append("### After task")
            lines.append("```")
            lines.append(session.git_diff_after[:3000])
            lines.append("```")

    lines.extend(["", "## Next recommended commands"])
    for cmd in next_recommended_commands(session):
        lines.append(f"- {cmd}")

    lines.extend(["", "---", f"**Task status:** {session.status.value}"])
    return "\n".join(lines)
