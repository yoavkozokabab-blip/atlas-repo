"""Deepgram-compatible local HTTP STT abstraction."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from config import DEEPGRAM_LOCAL_URL, STT_SAMPLE_RATE
from voice.stt_engines.base import (
    PartialCallback,
    STTEngine,
    SttEngineCapabilities,
    SttHypothesis,
)


class DeepgramLocalEngine(STTEngine):
    """
    Speaks Deepgram-style JSON over HTTP to a local compatible server
    (e.g. self-hosted streaming endpoint or adapter).
    """

    name = "deepgram_local"

    def is_available(self) -> bool:
        return bool(DEEPGRAM_LOCAL_URL.strip())

    def capabilities(self) -> SttEngineCapabilities:
        return SttEngineCapabilities(streaming=True, offline=False)

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        on_partial: PartialCallback | None = None,
    ) -> SttHypothesis:
        url = DEEPGRAM_LOCAL_URL.rstrip("/")
        if not url.endswith("/listen"):
            url = f"{url}/v1/listen"
        data = audio_path.read_bytes()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": f"audio/wav; rate={STT_SAMPLE_RATE}",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Deepgram local STT unreachable: {exc}") from exc

        channels = payload.get("channels") or []
        alt = (channels[0].get("alternatives") or [{}])[0] if channels else {}
        text = (alt.get("transcript") or payload.get("transcript") or "").strip()
        conf = float(alt.get("confidence", payload.get("confidence", 0.7)))
        if on_partial and text:
            on_partial(text)
        return SttHypothesis(
            text=text,
            engine=self.name,
            confidence=conf,
            language=language,
            metadata={"endpoint": url},
        )
