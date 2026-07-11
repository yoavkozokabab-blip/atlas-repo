"""Provider interface for future fully automated runs."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from ..models import Observations, RunnerInfo
from ..tokens import estimated_token_metric


@dataclass
class ProviderRunResult:
    status: str
    response_text: str
    runner: RunnerInfo
    observations: Observations
    notes: str = ""


class Provider:
    name = "provider"
    command_env_json = ""
    command_env = ""

    def configured_command(self) -> list[str] | None:
        raw_json = os.environ.get(self.command_env_json)
        if raw_json:
            command = json.loads(raw_json)
            if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
                raise ValueError(f"{self.command_env_json} must be a JSON array of strings")
            return command
        raw = os.environ.get(self.command_env)
        if raw:
            # This fallback is intentionally simple. Prefer *_COMMAND_JSON for exact quoting.
            return raw.split()
        return None

    def available(self) -> bool:
        return self.configured_command() is not None

    def run(self, *, prompt: str, env: dict[str, str], timeout_seconds: int, atlas_enabled: bool) -> ProviderRunResult:
        command = self.configured_command()
        runner = RunnerInfo(
            agent=self.name,
            atlas_enabled=atlas_enabled,
            provider=self.name,
            adapter="atlas" if atlas_enabled else "no_atlas",
            model=os.environ.get(f"{self.name.upper()}_BENCH_MODEL"),
            tool_version=None,
        )
        observations = Observations()
        observations.token_usage.user_prompt_tokens = estimated_token_metric(prompt)
        observations.telemetry_quality["user_prompt_tokens"] = "estimated"
        if not command:
            observations.errors.append(f"{self.name} command is not configured")
            return ProviderRunResult(
                status="pending_manual_or_external_run",
                response_text="",
                runner=runner,
                observations=observations,
                notes=f"Set {self.command_env_json} or {self.command_env} to enable automated {self.name} runs.",
            )

        process_env = os.environ.copy()
        process_env.update(env)
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=process_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            observations.latency_ms = elapsed_ms
            observations.errors.append(f"timeout after {timeout_seconds}s")
            return ProviderRunResult(
                status="technical_failure",
                response_text=(exc.stdout or "") + (exc.stderr or ""),
                runner=runner,
                observations=observations,
                notes="Provider command timed out.",
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response = completed.stdout or ""
        if completed.stderr:
            observations.errors.append(completed.stderr.strip())
        observations.latency_ms = elapsed_ms
        observations.token_usage.output_tokens = estimated_token_metric(response)
        observations.token_usage.total_tokens = {
            "value": (
                observations.token_usage.user_prompt_tokens["value"]
                + observations.token_usage.output_tokens["value"]
            ),
            "status": "estimated",
        }
        observations.telemetry_quality.update(
            {
                "latency": "exact",
                "output_tokens": "estimated",
                "total_tokens": "estimated",
                "tool_calls": "unavailable",
                "files_opened": "unavailable",
            }
        )
        return ProviderRunResult(
            status="completed" if completed.returncode == 0 else "technical_failure",
            response_text=response,
            runner=runner,
            observations=observations,
            notes=f"exit_code={completed.returncode}",
        )
