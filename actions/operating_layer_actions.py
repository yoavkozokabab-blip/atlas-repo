"""Phases 22–30 operating layer actions."""

from __future__ import annotations

import re

from actions.base import BaseAction
from artifacts.builder import (
    build_presentation_outline,
    create_report_document,
    create_study_summary,
)
from browser.dom_read import read_dom
from computer_control.guided import confirm_pending_ui_action, suggest_ui_target
from core.results import result_blocked, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from reliability.jarvis_status import build_jarvis_status_report
from reliability.startup_health import settings_status_report, startup_health_report
from task_agent.comparison_reports import generate_comparison_report
from task_agent.experiment_planner import build_experiment_plan
from task_agent.findings import format_findings_grouped, merge_findings
from task_agent.queue import enqueue, format_queue, pause_queue, resume_queue
from task_agent.session import get_active_task, reset_task_store, start_task
from task_agent.trading_deep_review import run_deep_review
from workspaces.launcher import workspace_plan


def _topic_from_request(request: CommandRequest) -> str:
    topic = (request.params.get("topic") or request.params.get("subject") or "").strip()
    if topic:
        return topic
    raw = (request.raw_text or "").strip()
    for prefix in (
        r"^build presentation about\s+",
        r"^create report about\s+",
        r"^create study summary about\s+",
    ):
        m = re.sub(prefix, "", raw, flags=re.I).strip()
        if m != raw:
            return m
    return raw


def _ensure_session_with_findings(mode: str, objective: str) -> CommandResult:
    session = get_active_task()
    if session is None:
        session = start_task(objective)
    findings, summary = run_deep_review(mode, objective)
    merge_findings(session.structured_findings, findings)
    body = summary + "\n\n" + format_findings_grouped(session.structured_findings)[:3000]
    return result_success(
        Intent.REVIEW_TRADING_ALGORITHM if mode == "review" else Intent.COMPARE_BACKTEST_TO_PAPER,
        body,
        data={"task_id": session.task_id, "findings": len(findings)},
    )


class ReviewTradingAlgorithmAction(BaseAction):
    intent = Intent.REVIEW_TRADING_ALGORITHM.value

    def execute(self, request: CommandRequest) -> CommandResult:
        obj = request.raw_text or "review trading algorithm"
        return _ensure_session_with_findings("review", obj)


class CompareBacktestToPaperAction(BaseAction):
    intent = Intent.COMPARE_BACKTEST_TO_PAPER.value

    def execute(self, request: CommandRequest) -> CommandResult:
        obj = request.raw_text or "compare backtest to paper"
        session = get_active_task()
        if session is None:
            start_task(obj)
        findings, summary = run_deep_review("compare", obj)
        session = get_active_task()
        if session:
            merge_findings(session.structured_findings, findings)
        path, report = generate_comparison_report()
        return result_success(
            Intent.COMPARE_BACKTEST_TO_PAPER,
            summary + f"\n\nReport: {path}\n\n" + report[:2500],
            data={"path": str(path)},
        )


class FindLiveBacktestMismatchAction(BaseAction):
    intent = Intent.FIND_LIVE_BACKTEST_MISMATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        obj = request.raw_text or "find live backtest mismatch"
        session = get_active_task()
        if session is None:
            start_task(obj)
        findings, summary = run_deep_review("mismatch", obj)
        session = get_active_task()
        if session:
            merge_findings(session.structured_findings, findings)
        return result_success(
            Intent.FIND_LIVE_BACKTEST_MISMATCH,
            summary + "\n\n" + format_findings_grouped(session.structured_findings if session else findings)[:2500],
        )


class GenerateBacktestPaperReportAction(BaseAction):
    intent = Intent.GENERATE_BACKTEST_PAPER_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        path, body = generate_comparison_report()
        return result_success(
            Intent.GENERATE_BACKTEST_PAPER_REPORT,
            f"Report written: {path}\n\n{body[:3000]}",
            data={"path": str(path)},
        )


class PlanExperimentsAction(BaseAction):
    intent = Intent.PLAN_EXPERIMENTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        topic = _topic_from_request(request)
        path, body = build_experiment_plan(topic)
        return result_success(
            Intent.PLAN_EXPERIMENTS,
            f"Experiment plan (not executed): {path}\n\n{body[:2500]}",
            data={"path": str(path)},
        )


class QueueTaskAction(BaseAction):
    intent = Intent.QUEUE_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        obj = (request.params.get("objective") or request.raw_text or "").strip()
        for prefix in ("queue task", "enqueue task"):
            if obj.lower().startswith(prefix):
                obj = obj[len(prefix) :].strip()
        if not obj:
            return result_failed(Intent.QUEUE_TASK, "Provide a task objective to queue.")
        task = enqueue(obj)
        return result_success(
            Intent.QUEUE_TASK,
            f"Queued {task.task_id}: {task.objective[:80]}",
        )


class ShowTaskQueueAction(BaseAction):
    intent = Intent.SHOW_TASK_QUEUE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(Intent.SHOW_TASK_QUEUE, format_queue())


class PauseTaskQueueAction(BaseAction):
    intent = Intent.PAUSE_TASK_QUEUE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(Intent.PAUSE_TASK_QUEUE, pause_queue())


class ResumeTaskQueueAction(BaseAction):
    intent = Intent.RESUME_TASK_QUEUE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(Intent.RESUME_TASK_QUEUE, resume_queue())


class StartTradingWorkspaceAction(BaseAction):
    intent = Intent.START_TRADING_WORKSPACE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        text, _ = workspace_plan("trading")
        return result_success(Intent.START_TRADING_WORKSPACE, text)


class StartStudyWorkspaceAction(BaseAction):
    intent = Intent.START_STUDY_WORKSPACE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        text, _ = workspace_plan("study")
        return result_success(Intent.START_STUDY_WORKSPACE, text)


class StartDevWorkspaceAction(BaseAction):
    intent = Intent.START_DEV_WORKSPACE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        text, _ = workspace_plan("dev")
        return result_success(Intent.START_DEV_WORKSPACE, text)


class SuggestUiClickAction(BaseAction):
    intent = Intent.SUGGEST_UI_CLICK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        target = (request.params.get("target") or "").strip()
        if not target:
            raw = (request.raw_text or "").lower()
            for tid in ("dashboard_refresh", "dashboard_health", "chatgpt_input", "jarvis_tray"):
                if tid.replace("_", " ") in raw or tid in raw:
                    target = tid
                    break
        sug, msg = suggest_ui_target(target)
        if sug is None:
            return result_blocked(Intent.SUGGEST_UI_CLICK, msg)
        return result_success(Intent.SUGGEST_UI_CLICK, msg)


class ConfirmUiClickAction(BaseAction):
    intent = Intent.CONFIRM_UI_CLICK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        ok, msg = confirm_pending_ui_action()
        if not ok:
            return result_failed(Intent.CONFIRM_UI_CLICK, msg)
        return result_success(Intent.CONFIRM_UI_CLICK, msg)


class BrowserDomReadAction(BaseAction):
    intent = Intent.BROWSER_DOM_READ.value

    def execute(self, request: CommandRequest) -> CommandResult:
        site = (request.params.get("site") or "dashboard").strip().lower()
        raw = (request.raw_text or "").lower()
        for key in ("dashboard", "chatgpt", "tradingview", "yohananof"):
            if key in raw:
                site = key
                break
        ok, msg = read_dom(site)
        if not ok:
            return result_blocked(Intent.BROWSER_DOM_READ, msg)
        return result_success(Intent.BROWSER_DOM_READ, msg)


class BuildPresentationAction(BaseAction):
    intent = Intent.BUILD_PRESENTATION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        topic = _topic_from_request(request)
        path, body = build_presentation_outline(topic)
        return result_success(
            Intent.BUILD_PRESENTATION,
            f"Presentation outline: {path}\n\n{body[:2000]}",
            data={"path": str(path)},
        )


class CreateReportDocumentAction(BaseAction):
    intent = Intent.CREATE_REPORT_DOCUMENT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        topic = _topic_from_request(request)
        raw = (request.raw_text or "").lower()
        if "study summary" in raw:
            path, body = create_study_summary(topic)
            intent = Intent.CREATE_REPORT_DOCUMENT
        else:
            path, body = create_report_document(topic)
            intent = Intent.CREATE_REPORT_DOCUMENT
        return result_success(
            intent,
            f"Document: {path}\n\n{body[:2000]}",
            data={"path": str(path)},
        )


class ShowStartupHealthAction(BaseAction):
    intent = Intent.SHOW_STARTUP_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(Intent.SHOW_STARTUP_HEALTH, startup_health_report())


class ShowSettingsStatusAction(BaseAction):
    intent = Intent.SHOW_SETTINGS_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(Intent.SHOW_SETTINGS_STATUS, settings_status_report())


class ShowJarvisStatusAction(BaseAction):
    intent = Intent.SHOW_JARVIS_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = build_jarvis_status_report()
        return result_success(
            Intent.SHOW_JARVIS_STATUS,
            body,
            data={"read_only": True},
        )
