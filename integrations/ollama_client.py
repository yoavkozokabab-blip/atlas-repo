"""Ollama HTTP client for LLM intent classification only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from config import LLM_MODEL, LLM_TIMEOUT_SECONDS, OLLAMA_BASE_URL
from core.logger import setup_logger

logger = setup_logger("jarvis.ollama")


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""


class OllamaClient:
    """Minimal Ollama chat client — JSON classification responses only."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or LLM_MODEL
        self.timeout = timeout if timeout is not None else LLM_TIMEOUT_SECONDS

    def classify_intent(self, prompt: str, *, system: str | None = None) -> dict:
        """
        Send classification prompt; return parsed JSON dict from model response.
        Raises OllamaError on failure.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
        }
        url = f"{self.base_url}/api/chat"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            raise OllamaError(
                f"Ollama not reachable at {self.base_url}. Is it running?"
            ) from exc
        except TimeoutError as exc:
            raise OllamaError(f"Ollama request timed out after {self.timeout}s") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Invalid JSON from Ollama: {exc}") from exc

        content = (data.get("message") or {}).get("content") or ""
        if not content.strip():
            raise OllamaError("Empty response from Ollama")
        return _extract_json_object(content)

    def stream_chat_tokens(
        self,
        prompt: str,
        *,
        system: str | None = None,
    ):
        """Yield token deltas from Ollama streaming chat API."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        url = f"{self.base_url}/api/chat"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = (data.get("message") or {}).get("content") or ""
                    if token:
                        yield token
                    if data.get("done"):
                        break
        except urllib.error.URLError as exc:
            raise OllamaError(
                f"Ollama not reachable at {self.base_url}. Is it running?"
            ) from exc
        except TimeoutError as exc:
            raise OllamaError(f"Ollama request timed out after {self.timeout}s") from exc


def _extract_json_object(text: str) -> dict:
    """Parse JSON from model output, tolerating markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise OllamaError("Could not parse JSON from LLM response") from None
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise OllamaError("LLM response is not a JSON object")
    return parsed
