"""Autonomous Agent Stack v1 — bounded autonomous executor.

Runs an APPROVED, PINNED plan step-by-step: observe -> act -> observe ->
verify -> log -> recover -> next, stopping on success, limits, exhaustion, or
safety block. Read-only only. No mock success: an unreal provider yields
BLOCKED_UNAVAILABLE.

Hard guarantees enforced here:
  * The plan's hash MUST equal the task's approved_plan_hash, else refuse.
  * Every plan step capability must be in the allowed set, else BLOCKED_FORBIDDEN.
  * Every external action is verified and recorded; nothing is reported as
    success unless it verified against the observed page on a real provider.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from autonomy.capabilities import ALLOWED_CAPABILITIES, Capability
from autonomy import memory, recovery
from autonomy.planner import AutonomousPlan
from autonomy.report import SourceEvidence, build_report, compute_confidence, extract_facts
from autonomy.task import AutonomousTask, StepResult, TaskStatus
from core.logger import setup_logger

logger = setup_logger("jarvis.autonomy.executor")

_SEARCH_HOSTS = ("marginalia.nu", "marginalia-search.com", "duckduckgo.com",
                 "bing.com", "google.com", "microsoft.com", "msn.com")
_MIN_TEXT = 50


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_engine(url: str) -> bool:
    h = _host(url)
    return any(h == e or h.endswith("." + e) for e in _SEARCH_HOSTS)


class AutonomousExecutor:
    def __init__(self, provider) -> None:
        self.provider = provider
        self._attempted: list[str] = []
        self._failures: list[str] = []
        self._safety_skips: list[str] = []
        self._steps_total = 0
        self._steps_verified = 0
        self._external_actions = 0

    # -- verification accounting -----------------------------------------
    def _verify(self, ok: bool) -> bool:
        self._steps_total += 1
        if ok:
            self._steps_verified += 1
        return ok

    def run(self, task: AutonomousTask, plan: AutonomousPlan) -> AutonomousTask:
        # 1. Approval / pinned-plan integrity.
        if not task.approved_plan_hash or task.approved_plan_hash != plan.plan_hash:
            task.status = TaskStatus.FAILED
            task.failure_reason = "unapproved_or_changed_plan (hash mismatch)"
            task.completed_at = time.time()
            return task

        # 2. Defense in depth: only allowed capabilities may appear.
        for s in plan.steps:
            if s.capability not in ALLOWED_CAPABILITIES:
                task.status = TaskStatus.BLOCKED_FORBIDDEN
                task.failure_reason = f"forbidden capability in plan: {s.capability}"
                task.completed_at = time.time()
                return task

        # 3. Real provider required — never mock success.
        task.started_at = time.time()
        task.status = TaskStatus.RUNNING
        if not self.provider.is_real():
            memory.note_provider("autonomous_browser", ok=False)
            task.status = TaskStatus.BLOCKED_UNAVAILABLE
            task.failure_reason = "no real browser provider available (mock not accepted)"
            task.completed_at = time.time()
            task.final_report = build_report(
                goal=task.user_goal, mode=plan.mode, sources=[],
                attempted=["attempted to acquire a real browser provider"],
                failures=["no real provider available"], safety_skips=[], confidence=0.0,
            )
            return task
        memory.note_provider("autonomous_browser", ok=True)

        deadline = task.started_at + plan.limits.max_runtime_seconds
        sources = self._collect_sources(task, plan, deadline)

        # Synthesize.
        self._steps_total += 1  # synthesize step
        confidence = compute_confidence(
            sources_collected=len(sources), sources_planned=plan.limits.max_sources,
            steps_total=max(1, self._steps_total), steps_verified=self._steps_verified,
        )
        self._steps_verified += 1 if sources else 0
        task.final_report = build_report(
            goal=task.user_goal, mode=plan.mode, sources=sources,
            attempted=self._attempted, failures=self._failures,
            safety_skips=self._safety_skips, confidence=confidence,
        )
        task.confidence = confidence
        task.completed_at = time.time()

        if not sources:
            task.status = TaskStatus.EXHAUSTED if self._failures else TaskStatus.FAILED
            task.failure_reason = task.failure_reason or "no sources could be opened and verified"
        elif plan.mode == "compare" and len(sources) < 2:
            task.status = TaskStatus.PARTIAL
            task.failure_reason = "comparison requested but fewer than 2 sources succeeded"
        else:
            task.status = TaskStatus.SUCCESS
        return task

    def _record(self, task: AutonomousTask, **kw) -> None:
        task.step_results.append(StepResult(**kw))
        task.current_step = len(task.step_results)

    def _budget_left(self, deadline: float, plan: AutonomousPlan) -> bool:
        return time.time() < deadline and self._external_actions < plan.limits.max_steps

    def _collect_sources(self, task, plan, deadline) -> list[SourceEvidence]:
        # ---- SEARCH (with bounded query-rewrite recovery) ----
        query = plan.query
        attempt = 0
        searched_ok = False
        while True:
            self._external_actions += 1
            self._attempted.append(f"search: {query!r}")
            self.provider.search(query)
            obs = self.provider.observe()
            organic = [l for l in obs.links if not _is_engine(str(l.get("href", "")))]
            if self._verify(len(organic) >= 1 and not obs.error):
                self._record(task, index=1, capability=Capability.SEARCH.value,
                             status="success", detail=f"{len(organic)} organic results",
                             verification_ok=True, verification_reason="organic results present")
                searched_ok = True
                break
            dec = recovery.plan_search_recovery(query, attempt, max_attempts=plan.limits.max_recovery_per_step)
            self._failures.append(f"search failed (attempt {attempt + 1}); {dec.reason}")
            if not dec.should_retry or not self._budget_left(deadline, plan):
                self._record(task, index=1, capability=Capability.SEARCH.value,
                             status="failed", detail=dec.reason, verification_ok=False,
                             verification_reason="no organic results", recovery_attempts=attempt)
                return []
            memory.note_query_rewrite(query, dec.new_query)
            query = dec.new_query
            attempt += 1

        # ---- OPEN + EXTRACT + SUMMARIZE up to max_sources ----
        results = self.provider.results()
        sources: list[SourceEvidence] = []
        idx = 0
        while results and idx < len(results) and len(sources) < plan.limits.max_sources:
            if not self._budget_left(deadline, plan):
                self._failures.append("stopped: runtime/step budget reached")
                break
            row = results[idx]
            url = str(row.get("url", ""))
            idx += 1
            if memory.is_known_bad_domain(url):
                self._safety_skips.append(f"skipped known-bad domain: {_host(url)}")
                continue

            self._external_actions += 1
            self._attempted.append(f"open: {url}")
            self.provider.open_index(idx - 1)
            obs = self.provider.observe()
            nav_ok = (not _is_engine(obs.url)) and bool(obs.url) and bool((obs.title or "").strip())
            if not self._verify(nav_ok):
                memory.note_failed_domain(url, "navigation_failed")
                self._failures.append(f"open failed: {_host(url)}")
                self._record(task, index=len(task.step_results) + 1,
                             capability=Capability.OPEN_RESULT.value, status="skipped",
                             detail="navigation/verification failed", verification_ok=False,
                             verification_reason="still on engine or empty title", url=url)
                continue

            # extract + summarize (with one re-observe recovery)
            text = (obs.visible_text or "").strip()
            rec_attempts = 0
            if len(text) < _MIN_TEXT and self._budget_left(deadline, plan):
                obs = self.provider.observe()
                text = (obs.visible_text or "").strip()
                rec_attempts = 1
            if not self._verify(len(text) >= _MIN_TEXT):
                memory.note_failed_domain(obs.url or url, "empty_text")
                self._failures.append(f"no usable text: {_host(obs.url or url)}")
                self._record(task, index=len(task.step_results) + 1,
                             capability=Capability.EXTRACT_FACTS.value, status="skipped",
                             detail="no substantial text", verification_ok=False,
                             verification_reason="text below threshold",
                             recovery_attempts=rec_attempts, url=obs.url or url)
                continue

            facts = extract_facts(text)
            summary = self._summarize(obs)
            sources.append(SourceEvidence(url=obs.url or url, title=obs.title, facts=facts, summary=summary))
            memory.note_useful_domain(obs.url or url)
            self._record(task, index=len(task.step_results) + 1,
                         capability=Capability.SUMMARIZE.value, status="success",
                         detail=f"{len(facts)} facts extracted", verification_ok=True,
                         verification_reason=f"{len(text)} chars",
                         recovery_attempts=rec_attempts, url=obs.url or url)
        return sources

    @staticmethod
    def _summarize(obs) -> str:
        parts = []
        if obs.title:
            parts.append(obs.title)
        if obs.headings:
            parts.append(" | ".join(obs.headings[:4]))
        txt = (obs.visible_text or "").strip().replace("\n", " ")
        if txt:
            parts.append(txt[:500])
        return "\n".join(parts)
